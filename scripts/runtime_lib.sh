#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RUNTIME_DIR="${RUNTIME_DIR:-${REPO_ROOT}/runtime}"
PID_DIR="${PID_DIR:-${RUNTIME_DIR}/pids}"
LOG_DIR="${LOG_DIR:-${RUNTIME_DIR}/logs}"
STOP_REQUEST_FILE="${RUNTIME_DIR}/stop-requested"

SUPERVISOR_PID_FILE="${PID_DIR}/runtime-supervisor.pid"
UNIT_MANAGER_PID_FILE="${PID_DIR}/unit-manager.pid"
RKLLM_PID_FILE="${PID_DIR}/rkllm-node.pid"
TTS_PID_FILE="${PID_DIR}/tts-node.pid"
ASR_PID_FILE="${PID_DIR}/asr-node.pid"
GATEWAY_PID_FILE="${PID_DIR}/gateway.pid"

UNIT_MANAGER_BIN="${UNIT_MANAGER_BIN:-${REPO_ROOT}/unit-manager/build/unit_manager}"
RKLLM_NODE_BIN="${RKLLM_NODE_BIN:-${REPO_ROOT}/node/llm/build/rkllm_node}"
RKLLM_MODEL_PATH="${RKLLM_MODEL_PATH:-${REPO_ROOT}/node/llm/model/Qwen3-1.7B.rkllm}"
TTS_NODE_BIN="${TTS_NODE_BIN:-${REPO_ROOT}/node/tts/build/tts_node}"
TTS_MODEL_PATH="${TTS_MODEL_PATH:-${REPO_ROOT}/node/tts/models/single_speaker_fast.bin}"
TTS_ALSA_DEVICE="${TTS_ALSA_DEVICE:-default}"
ASR_NODE_BIN="${ASR_NODE_BIN:-${REPO_ROOT}/node/asr/build/asr_node}"
ASR_MODEL_DIR="${ASR_MODEL_DIR:-${REPO_ROOT}/node/asr/models/zipformer}"

GATEWAY_HOST="${GATEWAY_HOST:-0.0.0.0}"
GATEWAY_PORT="${GATEWAY_PORT:-8000}"
UNIT_MANAGER_HOST="${UNIT_MANAGER_HOST:-127.0.0.1}"
UNIT_MANAGER_PORT="${UNIT_MANAGER_PORT:-10001}"
RKLLM_MODEL_ID="${RKLLM_MODEL_ID:-rkllm-local}"
TTS_MODEL_ID="${TTS_MODEL_ID:-tts-local}"
ASR_MODEL_ID="${ASR_MODEL_ID:-asr-local}"
RKLLM_TIMEOUT_SECONDS="${RKLLM_TIMEOUT_SECONDS:-300}"
TTS_TIMEOUT_SECONDS="${TTS_TIMEOUT_SECONDS:-180}"
ASR_TIMEOUT_SECONDS="${ASR_TIMEOUT_SECONDS:-60}"

mkdir_runtime_dirs() {
    mkdir -p "${PID_DIR}" "${LOG_DIR}"
}

read_pid_file() {
    local pid_file="$1"
    if [[ -f "${pid_file}" ]]; then
        tr -d '[:space:]' < "${pid_file}"
    fi
}

is_pid_running() {
    local pid="${1:-}"
    [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

is_pid_file_running() {
    local pid
    pid="$(read_pid_file "$1")"
    is_pid_running "${pid}"
}

remove_stale_pid_file() {
    local pid_file="$1"
    if [[ -f "${pid_file}" ]] && ! is_pid_file_running "${pid_file}"; then
        rm -f "${pid_file}"
    fi
}

stop_pid_file() {
    local name="$1"
    local pid_file="$2"
    local timeout="${3:-10}"
    local pid

    pid="$(read_pid_file "${pid_file}")"
    if ! is_pid_running "${pid}"; then
        rm -f "${pid_file}"
        return 0
    fi

    echo "stopping ${name} pid=${pid}"
    kill "${pid}" >/dev/null 2>&1 || true

    local elapsed=0
    while is_pid_running "${pid}" && [[ "${elapsed}" -lt "${timeout}" ]]; do
        sleep 1
        elapsed=$((elapsed + 1))
    done

    if is_pid_running "${pid}"; then
        echo "force stopping ${name} pid=${pid}"
        kill -9 "${pid}" >/dev/null 2>&1 || true
    fi

    rm -f "${pid_file}"
}

stop_matching_processes() {
    local name="$1"
    local pattern="$2"
    local timeout="${3:-10}"
    local pids

    pids="$(pgrep -f "${pattern}" 2>/dev/null || true)"
    if [[ -z "${pids}" ]]; then
        return 0
    fi

    echo "stopping ${name} matching: ${pattern}"
    for pid in ${pids}; do
        if [[ "${pid}" != "$$" ]]; then
            kill "${pid}" >/dev/null 2>&1 || true
        fi
    done

    local elapsed=0
    while [[ "${elapsed}" -lt "${timeout}" ]]; do
        pids="$(pgrep -f "${pattern}" 2>/dev/null || true)"
        if [[ -z "${pids}" ]]; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    pids="$(pgrep -f "${pattern}" 2>/dev/null || true)"
    if [[ -n "${pids}" ]]; then
        echo "force stopping ${name} matching: ${pattern}"
        for pid in ${pids}; do
            if [[ "${pid}" != "$$" ]]; then
                kill -9 "${pid}" >/dev/null 2>&1 || true
            fi
        done
    fi
}

port_in_use() {
    local host="$1"
    local port="$2"

python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except OSError:
    sys.exit(2)

try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
except OSError:
    sock.close()
    sys.exit(0)

sock.close()
sys.exit(1)
PY
}

port_label() {
    local host="$1"
    local port="$2"
    printf '%s:%s' "${host}" "${port}"
}

check_port_available_for_service() {
    local name="$1"
    local pid_file="$2"
    local host="$3"
    local port="$4"

    if is_pid_file_running "${pid_file}"; then
        return 0
    fi

    if port_in_use "${host}" "${port}"; then
        echo "${name} port $(port_label "${host}" "${port}") is already in use by an unmanaged process"
        echo "stop the existing process first, or change the configured port"
        return 1
    fi
}

preflight_runtime() {
    local missing=0

    if [[ ! -x "${UNIT_MANAGER_BIN}" ]]; then
        echo "missing executable: ${UNIT_MANAGER_BIN}"
        echo "build it with: cmake -S unit-manager -B unit-manager/build && cmake --build unit-manager/build -j\$(nproc)"
        missing=1
    fi

    if [[ ! -x "${RKLLM_NODE_BIN}" ]]; then
        echo "missing executable: ${RKLLM_NODE_BIN}"
        echo "build it with: cmake -S node/llm -B node/llm/build && cmake --build node/llm/build -j\$(nproc)"
        missing=1
    fi

    if [[ ! -f "${RKLLM_MODEL_PATH}" ]]; then
        echo "missing RKLLM model: ${RKLLM_MODEL_PATH}"
        echo "override with: RKLLM_MODEL_PATH=/path/to/model.rkllm ./scripts/start_runtime.sh"
        missing=1
    fi

    if [[ ! -x "${TTS_NODE_BIN}" ]]; then
        echo "missing executable: ${TTS_NODE_BIN}"
        echo "build it with: cmake -S node/tts -B node/tts/build && cmake --build node/tts/build -j\$(nproc)"
        missing=1
    fi

    if [[ ! -f "${TTS_MODEL_PATH}" ]]; then
        echo "missing TTS model: ${TTS_MODEL_PATH}"
        echo "override with: TTS_MODEL_PATH=/path/to/model.bin ./scripts/start_runtime.sh"
        missing=1
    fi

    if [[ ! -x "${ASR_NODE_BIN}" ]]; then
        echo "missing executable: ${ASR_NODE_BIN}"
        echo "build it with: cmake -S node/asr -B node/asr/build && cmake --build node/asr/build -j\$(nproc)"
        missing=1
    fi

    if [[ ! -d "${ASR_MODEL_DIR}" ]]; then
        echo "missing ASR model dir: ${ASR_MODEL_DIR}"
        echo "override with: ASR_MODEL_DIR=/path/to/model_dir ./scripts/start_runtime.sh"
        missing=1
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        echo "missing python3"
        missing=1
    fi

    check_port_available_for_service "unit-manager" "${UNIT_MANAGER_PID_FILE}" "0.0.0.0" "${UNIT_MANAGER_PORT}" || missing=1
    check_port_available_for_service "gateway" "${GATEWAY_PID_FILE}" "${GATEWAY_HOST}" "${GATEWAY_PORT}" || missing=1

    return "${missing}"
}

print_status_line() {
    local name="$1"
    local pid_file="$2"
    local pid
    pid="$(read_pid_file "${pid_file}")"

    if is_pid_running "${pid}"; then
        printf "%-18s running pid=%s\n" "${name}" "${pid}"
    else
        printf "%-18s stopped\n" "${name}"
    fi
}

print_port_status_line() {
    local name="$1"
    local pid_file="$2"
    local host="$3"
    local port="$4"

    if is_pid_file_running "${pid_file}"; then
        return 0
    fi

    if port_in_use "${host}" "${port}"; then
        printf "%-18s unmanaged port=%s\n" "${name}" "$(port_label "${host}" "${port}")"
    fi
}

print_matching_process_status_line() {
    local name="$1"
    local pid_file="$2"
    local pattern="$3"
    local managed_pid
    local pids

    managed_pid="$(read_pid_file "${pid_file}")"
    pids="$(pgrep -f "${pattern}" 2>/dev/null || true)"
    if [[ -z "${pids}" ]]; then
        return 0
    fi

    for pid in ${pids}; do
        if [[ "${pid}" != "$$" && "${pid}" != "${managed_pid}" ]]; then
            printf "%-18s unmanaged pid=%s\n" "${name}" "${pid}"
        fi
    done
}
