# Runtime scripts

Lightweight process management for the first OpenAI-compatible RKLLM gateway
stage.

## Start

```bash
./scripts/start_runtime.sh
```

This starts and watches:

- `unit-manager/build/unit_manager`
- `node/llm/build/rkllm_node`
- `node/tts/build/tts_node`
- `node/asr/build/asr_node`
- `python3 -m uvicorn gateway.app.main:app`

Runtime files are written under `runtime/`, which is ignored by git:

- `runtime/pids`
- `runtime/logs`

## Stop

```bash
./scripts/stop_runtime.sh
```

## Status

```bash
./scripts/status_runtime.sh
```

## Smoke Test

```bash
./scripts/smoke_test_gateway.sh
```

This checks:

- `/health`
- `/v1/models`
- `/v1/chat/completions`
- `/v1/audio/speech`
- `/v1/audio/transcriptions`
- `/v1/audio/conversations`

Optional overrides:

```bash
GATEWAY_BASE_URL=http://127.0.0.1:8000 ASR_TEST_WAV=node/asr/models/zipformer/test_wavs/3.wav ./scripts/smoke_test_gateway.sh
```

## Configuration

Environment variables:

- `RKLLM_MODEL_PATH`, default `node/llm/model/Qwen3-1.7B.rkllm`
- `TTS_MODEL_PATH`, default `node/tts/models/single_speaker_fast.bin`
- `TTS_ALSA_DEVICE`, default `default`
- `ASR_MODEL_DIR`, default `node/asr/models/zipformer`
- `GATEWAY_HOST`, default `0.0.0.0`
- `GATEWAY_PORT`, default `8000`
- `UNIT_MANAGER_HOST`, default `127.0.0.1`
- `UNIT_MANAGER_PORT`, default `10001`
- `RKLLM_MODEL_ID`, default `rkllm-local`
- `TTS_MODEL_ID`, default `tts-local`
- `ASR_MODEL_ID`, default `asr-local`

Example:

```bash
RKLLM_MODEL_PATH=/models/qwen.rkllm TTS_MODEL_PATH=/models/tts.bin GATEWAY_PORT=8001 ./scripts/start_runtime.sh
```
