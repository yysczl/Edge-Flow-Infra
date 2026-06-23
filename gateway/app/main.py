import base64
import binascii
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, Iterator

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

from .audio_utils import AudioFormatError, wav_pcm16_chunks
from .openai_compat import (
    build_prompt,
    chat_completion_chunk,
    chat_completion_response,
    model_list,
)
from .unit_manager_client import UnitManagerClient, UnitManagerError


UNIT_MANAGER_HOST = os.getenv("UNIT_MANAGER_HOST", "127.0.0.1")
UNIT_MANAGER_PORT = int(os.getenv("UNIT_MANAGER_PORT", "10001"))
RKLLM_MODEL_ID = os.getenv("RKLLM_MODEL_ID", "rkllm-local")
TTS_MODEL_ID = os.getenv("TTS_MODEL_ID", "tts-local")
ASR_MODEL_ID = os.getenv("ASR_MODEL_ID", "asr-local")
RKLLM_TIMEOUT_SECONDS = float(os.getenv("RKLLM_TIMEOUT_SECONDS", "300"))
TTS_TIMEOUT_SECONDS = float(os.getenv("TTS_TIMEOUT_SECONDS", "180"))
ASR_TIMEOUT_SECONDS = float(os.getenv("ASR_TIMEOUT_SECONDS", "60"))
CORS_ALLOW_ORIGINS = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "https://edge-infra.ianyys.com",
).split(",")

app = FastAPI(title="Edge LLM OpenAI-compatible Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rkllm_lock = threading.Lock()
tts_lock = threading.Lock()
asr_lock = threading.Lock()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "unit_manager": {
            "host": UNIT_MANAGER_HOST,
            "port": UNIT_MANAGER_PORT,
        },
        "rkllm": {
            "model": RKLLM_MODEL_ID,
            "busy": rkllm_lock.locked(),
        },
        "tts": {
            "model": TTS_MODEL_ID,
            "busy": tts_lock.locked(),
        },
        "asr": {
            "model": ASR_MODEL_ID,
            "busy": asr_lock.locked(),
        },
    }


@app.get("/v1/models")
def models() -> Dict[str, Any]:
    return model_list([RKLLM_MODEL_ID, TTS_MODEL_ID, ASR_MODEL_ID])


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise openai_http_error(400, "messages must be a non-empty array")

    model_id = body.get("model") or RKLLM_MODEL_ID
    if model_id != RKLLM_MODEL_ID:
        raise openai_http_error(404, f"model '{model_id}' is not available")

    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        prompt = build_prompt(messages)

    if body.get("stream", False):
        return StreamingResponse(
            stream_chat_completion(prompt),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        content = await run_in_threadpool(run_chat_completion, prompt)
    except UnitManagerError as exc:
        status_code = exc.code if 400 <= exc.code <= 599 else 502
        raise openai_http_error(status_code, exc.message)
    return chat_completion_response(RKLLM_MODEL_ID, content)


@app.post("/v1/audio/speech")
async def audio_speech(request: Request):
    body = await request.json()
    model_id = body.get("model") or TTS_MODEL_ID
    if model_id != TTS_MODEL_ID:
        raise openai_http_error(404, f"model '{model_id}' is not available")

    text = body.get("input")
    if not isinstance(text, str) or not text.strip():
        raise openai_http_error(400, "input must be a non-empty string")

    response_format = body.get("response_format", "wav")
    if response_format != "wav":
        raise openai_http_error(400, "only response_format='wav' is supported")

    speaker_id = parse_voice(body.get("voice", "0"))
    length_scale = parse_positive_float(body.get("speed", 1.0), "speed")

    try:
        wav = await run_in_threadpool(
            run_tts_speech,
            text,
            speaker_id,
            length_scale,
        )
    except UnitManagerError as exc:
        status_code = exc.code if 400 <= exc.code <= 599 else 502
        raise openai_http_error(status_code, exc.message)

    return Response(
        content=wav,
        media_type="audio/wav",
        headers={
            "Content-Disposition": 'attachment; filename="speech.wav"',
        },
    )


@app.post("/v1/audio/transcriptions")
async def audio_transcriptions(
    file: UploadFile = File(...),
    model: str = Form(ASR_MODEL_ID),
    response_format: str = Form("json"),
):
    if model != ASR_MODEL_ID:
        raise openai_http_error(404, f"model '{model}' is not available")
    if response_format not in ("json", "text"):
        raise openai_http_error(400, "only response_format='json' or 'text' is supported")

    wav_bytes = await file.read()
    if not wav_bytes:
        raise openai_http_error(400, "file must not be empty")

    try:
        text = await run_in_threadpool(run_asr_transcription, wav_bytes)
    except AudioFormatError as exc:
        raise openai_http_error(400, str(exc))
    except UnitManagerError as exc:
        status_code = exc.code if 400 <= exc.code <= 599 else 502
        raise openai_http_error(status_code, exc.message)

    if response_format == "text":
        return Response(content=text, media_type="text/plain; charset=utf-8")
    return {"text": text}


@app.post("/v1/audio/conversations")
async def audio_conversations(
    file: UploadFile = File(...),
    model: str = Form(RKLLM_MODEL_ID),
    voice: str = Form("0"),
    speed: str = Form("1.0"),
    response_format: str = Form("json"),
    system_prompt: str = Form("你是运行在边缘设备上的本地语音助手，回答要简洁。"),
):
    if model != RKLLM_MODEL_ID:
        raise openai_http_error(404, f"model '{model}' is not available")
    if response_format != "json":
        raise openai_http_error(400, "only response_format='json' is supported")

    speaker_id = parse_voice(voice)
    length_scale = parse_positive_float(speed, "speed")

    wav_bytes = await file.read()
    if not wav_bytes:
        raise openai_http_error(400, "file must not be empty")

    try:
        result = await run_in_threadpool(
            run_voice_chat,
            wav_bytes,
            system_prompt,
            speaker_id,
            length_scale,
        )
    except AudioFormatError as exc:
        raise openai_http_error(400, str(exc))
    except UnitManagerError as exc:
        status_code = exc.code if 400 <= exc.code <= 599 else 502
        raise openai_http_error(status_code, exc.message)

    return result


def run_voice_chat(
    wav_bytes: bytes,
    system_prompt: str,
    speaker_id: int,
    length_scale: float,
) -> Dict[str, Any]:
    transcript = run_asr_transcription(wav_bytes)
    if not transcript:
        raise UnitManagerError("asr returned empty transcript", code=422)

    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": transcript})

    reply = run_chat_completion(build_prompt(messages)).strip()
    if not reply:
        raise UnitManagerError("rkllm returned empty reply", code=502)

    audio = run_tts_speech(reply, speaker_id, length_scale)
    return {
        "id": f"audconv-{uuid.uuid4().hex}",
        "object": "audio.conversation",
        "created": int(time.time()),
        "model": RKLLM_MODEL_ID,
        "transcript": transcript,
        "reply": reply,
        "audio": {
            "format": "wav",
            "data": base64.b64encode(audio).decode("ascii"),
        },
    }


def run_chat_completion(prompt: str) -> str:
    chunks = []
    for data in run_rkllm_stream(prompt):
        delta = data.get("delta", "")
        if delta:
            chunks.append(delta)
    return "".join(chunks)


def run_tts_speech(text: str, speaker_id: int, length_scale: float) -> bytes:
    acquired = tts_lock.acquire(timeout=1)
    if not acquired:
        raise UnitManagerError("tts is busy; retry later", code=429)

    work_id = None
    try:
        with UnitManagerClient(
            UNIT_MANAGER_HOST,
            UNIT_MANAGER_PORT,
            TTS_TIMEOUT_SECONDS,
        ) as client:
            work_id = client.setup("tts")
            data = client.inference_once(
                work_id,
                "tts.input",
                {
                    "text": text,
                    "speaker_id": speaker_id,
                    "length_scale": length_scale,
                    "format": "wav",
                    "play": False,
                },
                "tts.audio",
                "tts_speech",
            )
            audio_base64 = data.get("audio_base64")
            if not isinstance(audio_base64, str) or not audio_base64:
                raise UnitManagerError("tts response did not include audio_base64")
            try:
                return base64.b64decode(audio_base64)
            except (binascii.Error, ValueError) as exc:
                raise UnitManagerError(f"tts returned invalid base64 audio: {exc}")
    finally:
        try:
            if work_id:
                with UnitManagerClient(
                    UNIT_MANAGER_HOST,
                    UNIT_MANAGER_PORT,
                    10,
                ) as cleanup_client:
                    cleanup_client.exit(work_id, "tts")
        finally:
            tts_lock.release()


def run_asr_transcription(wav_bytes: bytes) -> str:
    acquired = asr_lock.acquire(timeout=1)
    if not acquired:
        raise UnitManagerError("asr is busy; retry later", code=429)

    work_id = None
    try:
        chunks = list(wav_pcm16_chunks(wav_bytes))
        if not chunks:
            raise AudioFormatError("WAV must contain audio samples")

        with UnitManagerClient(
            UNIT_MANAGER_HOST,
            UNIT_MANAGER_PORT,
            ASR_TIMEOUT_SECONDS,
        ) as client:
            work_id = client.setup("asr")
            return client.asr_transcribe(work_id, chunks)
    finally:
        try:
            if work_id:
                with UnitManagerClient(
                    UNIT_MANAGER_HOST,
                    UNIT_MANAGER_PORT,
                    10,
                ) as cleanup_client:
                    cleanup_client.exit(work_id, "asr")
        finally:
            asr_lock.release()


def stream_chat_completion(prompt: str) -> Iterator[str]:
    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    try:
        yield sse(
            chat_completion_chunk(
                RKLLM_MODEL_ID,
                "",
                request_id,
                role="assistant",
            )
        )
        for data in run_rkllm_stream(prompt):
            delta = data.get("delta", "")
            finish = bool(data.get("finish", False))
            if delta:
                yield sse(chat_completion_chunk(RKLLM_MODEL_ID, delta, request_id))
            if finish:
                yield sse(chat_completion_chunk(RKLLM_MODEL_ID, "", request_id, finish=True))
                yield "data: [DONE]\n\n"
                break
    except UnitManagerError as exc:
        yield sse(
            {
                "error": {
                    "message": exc.message,
                    "type": "unit_manager_error",
                    "code": exc.code,
                }
            }
        )
        yield "data: [DONE]\n\n"


def run_rkllm_stream(prompt: str) -> Iterator[Dict[str, Any]]:
    acquired = rkllm_lock.acquire(timeout=1)
    if not acquired:
        raise UnitManagerError("rkllm is busy; retry later", code=429)

    work_id = None
    try:
        with UnitManagerClient(
            UNIT_MANAGER_HOST,
            UNIT_MANAGER_PORT,
            RKLLM_TIMEOUT_SECONDS,
        ) as client:
            work_id = client.setup("rkllm")
            for data in client.rkllm_stream(work_id, prompt):
                yield data
    finally:
        try:
            if work_id:
                with UnitManagerClient(
                    UNIT_MANAGER_HOST,
                    UNIT_MANAGER_PORT,
                    10,
                ) as cleanup_client:
                    cleanup_client.exit(work_id, "rkllm")
        finally:
            rkllm_lock.release()


def sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def parse_voice(voice: Any) -> int:
    if isinstance(voice, int):
        return voice
    if isinstance(voice, str):
        try:
            return int(voice)
        except ValueError:
            raise openai_http_error(400, "voice must be a numeric speaker id")
    raise openai_http_error(400, "voice must be a numeric speaker id")


def parse_positive_float(value: Any, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise openai_http_error(400, f"{name} must be a number")
    if parsed <= 0:
        raise openai_http_error(400, f"{name} must be positive")
    return parsed


def openai_http_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "code": status_code,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": str(exc.detail),
                "type": "invalid_request_error",
                "code": exc.status_code,
            }
        },
    )
