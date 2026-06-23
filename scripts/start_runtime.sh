#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_lib.sh"

mkdir_runtime_dirs
rm -f "${STOP_REQUEST_FILE}"
remove_stale_pid_file "${SUPERVISOR_PID_FILE}"

if is_pid_file_running "${SUPERVISOR_PID_FILE}"; then
    echo "runtime supervisor already running pid=$(read_pid_file "${SUPERVISOR_PID_FILE}")"
    "${SCRIPT_DIR}/status_runtime.sh"
    exit 0
fi

preflight_runtime

nohup "${SCRIPT_DIR}/runtime_supervisor.sh" >> "${LOG_DIR}/runtime-supervisor.log" 2>&1 &
echo "$!" > "${SUPERVISOR_PID_FILE}"

sleep 1
"${SCRIPT_DIR}/status_runtime.sh"

echo
echo "logs: ${LOG_DIR}"
echo "gateway: http://${GATEWAY_HOST}:${GATEWAY_PORT}"
