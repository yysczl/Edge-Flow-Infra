#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_lib.sh"

RESTART_INTERVAL_SECONDS="${RESTART_INTERVAL_SECONDS:-2}"
STOPPING=0

log() {
    printf '[%(%Y-%m-%d %H:%M:%S)T] %s\n' -1 "$*"
}

start_service() {
    local name="$1"
    local pid_file="$2"
    local log_file="$3"
    shift 3

    remove_stale_pid_file "${pid_file}"
    if is_pid_file_running "${pid_file}"; then
        return 0
    fi

    log "starting ${name}"
    (
        cd "${REPO_ROOT}"
        exec "$@"
    ) >> "${log_file}" 2>&1 &
    echo "$!" > "${pid_file}"
}

start_port_service() {
    local name="$1"
    local pid_file="$2"
    local log_file="$3"
    local host="$4"
    local port="$5"
    shift 5

    remove_stale_pid_file "${pid_file}"
    if is_pid_file_running "${pid_file}"; then
        return 0
    fi

    if port_in_use "${host}" "${port}"; then
        log "skip ${name}: port $(port_label "${host}" "${port}") is already in use"
        return 0
    fi

    start_service "${name}" "${pid_file}" "${log_file}" "$@"
}

stop_all() {
    if [[ "${STOPPING}" -eq 1 ]]; then
        return 0
    fi
    STOPPING=1
    log "stopping runtime services"
    stop_pid_file "gateway" "${GATEWAY_PID_FILE}" 10
    stop_pid_file "asr-node" "${ASR_PID_FILE}" 10
    stop_pid_file "tts-node" "${TTS_PID_FILE}" 10
    stop_pid_file "rkllm-node" "${RKLLM_PID_FILE}" 10
    stop_pid_file "unit-manager" "${UNIT_MANAGER_PID_FILE}" 10
    rm -f "${SUPERVISOR_PID_FILE}"
}

trap stop_all INT TERM EXIT

mkdir_runtime_dirs
echo "$$" > "${SUPERVISOR_PID_FILE}"
log "runtime supervisor started pid=$$"

while true; do
    if [[ -f "${STOP_REQUEST_FILE}" ]]; then
        log "stop requested; supervisor exiting"
        exit 0
    fi

    start_port_service \
        "unit-manager" \
        "${UNIT_MANAGER_PID_FILE}" \
        "${LOG_DIR}/unit-manager.log" \
        "0.0.0.0" \
        "${UNIT_MANAGER_PORT}" \
        "${UNIT_MANAGER_BIN}"

    start_service \
        "rkllm-node" \
        "${RKLLM_PID_FILE}" \
        "${LOG_DIR}/rkllm-node.log" \
        "${RKLLM_NODE_BIN}" \
        "${RKLLM_MODEL_PATH}"

    start_service \
        "tts-node" \
        "${TTS_PID_FILE}" \
        "${LOG_DIR}/tts-node.log" \
        "${TTS_NODE_BIN}" \
        "${TTS_MODEL_PATH}" \
        "${TTS_ALSA_DEVICE}"

    start_service \
        "asr-node" \
        "${ASR_PID_FILE}" \
        "${LOG_DIR}/asr-node.log" \
        "${ASR_NODE_BIN}" \
        "${ASR_MODEL_DIR}"

    start_port_service \
        "gateway" \
        "${GATEWAY_PID_FILE}" \
        "${LOG_DIR}/gateway.log" \
        "${GATEWAY_HOST}" \
        "${GATEWAY_PORT}" \
        env \
        "UNIT_MANAGER_HOST=${UNIT_MANAGER_HOST}" \
        "UNIT_MANAGER_PORT=${UNIT_MANAGER_PORT}" \
        "RKLLM_MODEL_ID=${RKLLM_MODEL_ID}" \
        "RKLLM_TIMEOUT_SECONDS=${RKLLM_TIMEOUT_SECONDS}" \
        "TTS_MODEL_ID=${TTS_MODEL_ID}" \
        "TTS_TIMEOUT_SECONDS=${TTS_TIMEOUT_SECONDS}" \
        "ASR_MODEL_ID=${ASR_MODEL_ID}" \
        "ASR_TIMEOUT_SECONDS=${ASR_TIMEOUT_SECONDS}" \
        python3 -m uvicorn gateway.app.main:app --host "${GATEWAY_HOST}" --port "${GATEWAY_PORT}"

    sleep "${RESTART_INTERVAL_SECONDS}"
done
