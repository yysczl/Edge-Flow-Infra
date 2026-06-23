#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_lib.sh"

mkdir_runtime_dirs

remove_stale_pid_file "${SUPERVISOR_PID_FILE}"
remove_stale_pid_file "${UNIT_MANAGER_PID_FILE}"
remove_stale_pid_file "${RKLLM_PID_FILE}"
remove_stale_pid_file "${TTS_PID_FILE}"
remove_stale_pid_file "${ASR_PID_FILE}"
remove_stale_pid_file "${GATEWAY_PID_FILE}"

print_status_line "supervisor" "${SUPERVISOR_PID_FILE}"
print_status_line "unit-manager" "${UNIT_MANAGER_PID_FILE}"
print_status_line "rkllm-node" "${RKLLM_PID_FILE}"
print_status_line "tts-node" "${TTS_PID_FILE}"
print_status_line "asr-node" "${ASR_PID_FILE}"
print_status_line "gateway" "${GATEWAY_PID_FILE}"
print_matching_process_status_line "unit-manager" "${UNIT_MANAGER_PID_FILE}" "${REPO_ROOT}/unit-manager/build/unit_manager"
print_matching_process_status_line "rkllm-node" "${RKLLM_PID_FILE}" "${REPO_ROOT}/node/llm/build/rkllm_node"
print_matching_process_status_line "tts-node" "${TTS_PID_FILE}" "${REPO_ROOT}/node/tts/build/tts_node"
print_matching_process_status_line "asr-node" "${ASR_PID_FILE}" "${REPO_ROOT}/node/asr/build/asr_node"
print_matching_process_status_line "gateway" "${GATEWAY_PID_FILE}" "uvicorn gateway.app.main:app"
print_port_status_line "unit-manager" "${UNIT_MANAGER_PID_FILE}" "0.0.0.0" "${UNIT_MANAGER_PORT}"
print_port_status_line "gateway" "${GATEWAY_PID_FILE}" "${GATEWAY_HOST}" "${GATEWAY_PORT}"

echo
echo "model: ${RKLLM_MODEL_PATH}"
echo "tts model: ${TTS_MODEL_PATH}"
echo "asr model: ${ASR_MODEL_DIR}"
echo "logs: ${LOG_DIR}"
