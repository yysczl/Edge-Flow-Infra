#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_lib.sh"

mkdir_runtime_dirs
touch "${STOP_REQUEST_FILE}"

stop_pid_file "runtime-supervisor" "${SUPERVISOR_PID_FILE}" 10
stop_pid_file "gateway" "${GATEWAY_PID_FILE}" 10
stop_pid_file "asr-node" "${ASR_PID_FILE}" 10
stop_pid_file "tts-node" "${TTS_PID_FILE}" 10
stop_pid_file "rkllm-node" "${RKLLM_PID_FILE}" 10
stop_pid_file "unit-manager" "${UNIT_MANAGER_PID_FILE}" 10

for _ in 1 2 3; do
    stop_matching_processes "orphan gateway" "uvicorn gateway.app.main:app" 3
    stop_matching_processes "orphan asr-node" "${REPO_ROOT}/node/asr/build/asr_node" 5
    stop_matching_processes "orphan tts-node" "${REPO_ROOT}/node/tts/build/tts_node" 5
    stop_matching_processes "orphan rkllm-node" "${REPO_ROOT}/node/llm/build/rkllm_node" 5
    stop_matching_processes "orphan unit-manager" "${REPO_ROOT}/unit-manager/build/unit_manager" 3
    stop_matching_processes "orphan runtime-supervisor" "${REPO_ROOT}/scripts/runtime_supervisor.sh" 3
    sleep 1
done

rm -f "${SUPERVISOR_PID_FILE}" "${GATEWAY_PID_FILE}" "${ASR_PID_FILE}" "${TTS_PID_FILE}" "${RKLLM_PID_FILE}" "${UNIT_MANAGER_PID_FILE}" "${STOP_REQUEST_FILE}"

echo "runtime stopped"
