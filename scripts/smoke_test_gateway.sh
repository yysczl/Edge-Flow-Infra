#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_lib.sh"

GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://127.0.0.1:${GATEWAY_PORT}}"
ASR_TEST_WAV="${ASR_TEST_WAV:-${ASR_MODEL_DIR}/test_wavs/3.wav}"
TMP_DIR="$(mktemp -d)"

cleanup() {
    rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

log() {
    printf '[smoke] %s\n' "$*"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        fail "missing command: $1"
    fi
}

curl_json() {
    local name="$1"
    local output="$2"
    shift 2

    local status
    status="$(curl -sS -o "${output}" -w '%{http_code}' "$@")" || {
        echo "response:" >&2
        tail -c 1000 "${output}" >&2 2>/dev/null || true
        fail "${name} request failed"
    }

    if [[ "${status}" -lt 200 || "${status}" -ge 300 ]]; then
        echo "response:" >&2
        tail -c 1000 "${output}" >&2 2>/dev/null || true
        fail "${name} returned HTTP ${status}"
    fi
}

assert_json() {
    local name="$1"
    local file="$2"
    local check="$3"
    local expected="${4:-}"

    python3 - "$file" "$check" "$expected" <<'PY' || fail "${name} assertion failed"
import json
import sys

path, check, expected = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

ok = False
if check == "health":
    ok = data.get("status") == "ok"
elif check == "model":
    ok = any(m.get("id") == expected for m in data.get("data", []))
elif check == "chat":
    choices = data.get("choices", [{}])
    ok = bool(choices[0].get("message", {}).get("content"))
elif check == "transcript":
    ok = isinstance(data.get("text"), str)
elif check == "conversation_transcript":
    ok = isinstance(data.get("transcript"), str)
elif check == "conversation_reply":
    ok = bool(data.get("reply"))
elif check == "conversation_audio":
    audio = data.get("audio", {})
    ok = bool(audio.get("data")) and audio.get("format") == "wav"

if not ok:
    raise SystemExit(1)
PY
}

require_command curl
require_command python3

if [[ ! -f "${ASR_TEST_WAV}" ]]; then
    fail "missing ASR test WAV: ${ASR_TEST_WAV}"
fi

log "gateway base url: ${GATEWAY_BASE_URL}"

log "health"
health_json="${TMP_DIR}/health.json"
curl_json "health" "${health_json}" "${GATEWAY_BASE_URL}/health"
assert_json "health" "${health_json}" "health"

log "models"
models_json="${TMP_DIR}/models.json"
curl_json "models" "${models_json}" "${GATEWAY_BASE_URL}/v1/models"
assert_json "models rkllm" "${models_json}" "model" "${RKLLM_MODEL_ID}"
assert_json "models tts" "${models_json}" "model" "${TTS_MODEL_ID}"
assert_json "models asr" "${models_json}" "model" "${ASR_MODEL_ID}"

log "chat completions"
chat_json="${TMP_DIR}/chat.json"
curl_json \
    "chat completions" \
    "${chat_json}" \
    "${GATEWAY_BASE_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${RKLLM_MODEL_ID}\",\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}],\"stream\":false}"
assert_json "chat completions" "${chat_json}" "chat"

log "audio speech"
speech_wav="${TMP_DIR}/speech.wav"
speech_status="$(
    curl -sS -o "${speech_wav}" -w '%{http_code}' \
        "${GATEWAY_BASE_URL}/v1/audio/speech" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"${TTS_MODEL_ID}\",\"input\":\"你好，这是一次自动验收。\",\"voice\":\"0\",\"response_format\":\"wav\",\"speed\":1.0}"
)" || fail "audio speech request failed"
if [[ "${speech_status}" -lt 200 || "${speech_status}" -ge 300 ]]; then
    tail -c 1000 "${speech_wav}" >&2 2>/dev/null || true
    fail "audio speech returned HTTP ${speech_status}"
fi
python3 - "${speech_wav}" <<'PY' || fail "audio speech did not return a valid WAV"
import sys
import wave

with wave.open(sys.argv[1], "rb") as wav:
    if wav.getnframes() <= 0:
        raise SystemExit(1)
PY

log "audio transcriptions"
asr_json="${TMP_DIR}/asr.json"
curl_json \
    "audio transcriptions" \
    "${asr_json}" \
    "${GATEWAY_BASE_URL}/v1/audio/transcriptions" \
    -F "model=${ASR_MODEL_ID}" \
    -F "response_format=json" \
    -F "file=@${ASR_TEST_WAV}"
assert_json "audio transcriptions" "${asr_json}" "transcript"

log "audio conversations"
conversation_json="${TMP_DIR}/conversation.json"
curl_json \
    "audio conversations" \
    "${conversation_json}" \
    "${GATEWAY_BASE_URL}/v1/audio/conversations" \
    -F "file=@${ASR_TEST_WAV}" \
    -F "model=${RKLLM_MODEL_ID}" \
    -F "voice=0" \
    -F "speed=1.0"
assert_json "audio conversations transcript" "${conversation_json}" "conversation_transcript"
assert_json "audio conversations reply" "${conversation_json}" "conversation_reply"
assert_json "audio conversations audio" "${conversation_json}" "conversation_audio"

log "all checks passed"
