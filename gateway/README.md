# Edge LLM Gateway

OpenAI-compatible API gateway for the local `unit-manager` RKLLM runtime.

## Run

```bash
python3 -m uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000
```

Environment variables:

- `UNIT_MANAGER_HOST`, default `127.0.0.1`
- `UNIT_MANAGER_PORT`, default `10001`
- `RKLLM_MODEL_ID`, default `rkllm-local`
- `TTS_MODEL_ID`, default `tts-local`
- `ASR_MODEL_ID`, default `asr-local`
- `RKLLM_TIMEOUT_SECONDS`, default `300`
- `TTS_TIMEOUT_SECONDS`, default `180`
- `ASR_TIMEOUT_SECONDS`, default `60`

## OpenAI-compatible endpoints

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/audio/speech`
- `POST /v1/audio/transcriptions`
- `POST /v1/audio/conversations`

The first version intentionally serializes RKLLM requests with a global lock
because the current `rkllm_node` accepts one active task.

## Test
- curl http://127.0.0.1:8000/health
- curl http://127.0.0.1:8000/v1/models
- curl http://127.0.0.1:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model": "rkllm-local", "messages": [{"role": "user", "content": "hello"}],
"stream": false}'
- curl http://127.0.0.1:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model": "rkllm-local", "messages": [{"role": "user", "content": "今天是哪一天？"}], "stream": true}'
- curl http://127.0.0.1:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-local","input":"你好，我是本地语音合成。","voice":"0","response_format":"wav","speed":1.0}' \
  --output out.wav
- curl http://127.0.0.1:8000/v1/audio/transcriptions \
  -F model=asr-local \
  -F response_format=json \
  -F file=@node/asr/models/zipformer/test_wavs/3.wav
- curl http://127.0.0.1:8000/v1/audio/conversations \
  -F file=@node/asr/models/zipformer/test_wavs/3.wav \
  -F model=rkllm-local \
  -F voice=0 \
  -F speed=1.0
