#!/usr/bin/env bash
set -euo pipefail

WORK_ROOT="${WORK_ROOT:-/workspace/user_data/minicpm-vllm-omni}"
PROJECT_ROOT="${PROJECT_ROOT:-${WORK_ROOT}/submission}"
PYTHON_BIN="${PYTHON_BIN:-/usr/local/python3.12.13/bin/python3}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8091}"
CONFIG="${CONFIG:-${PROJECT_ROOT}/configs/experiment_steps9.yaml}"
DEMO_DIR="${DEMO_DIR:-${WORK_ROOT}/results/demo}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="${RUN_DIR:-${DEMO_DIR}/${RUN_ID}}"
WAV_DIR="${WAV_DIR:-${RUN_DIR}/wavs}"

test -r "$CONFIG"
mkdir -p "$RUN_DIR" "$WAV_DIR"
curl --fail --silent --show-error "http://${HOST}:${PORT}/health" >/dev/null

{
  echo "MiniCPM-o 4.5 Ascend vLLM-Omni demo"
  date -Ins
  echo "run_dir=$RUN_DIR"
  echo "config=$CONFIG"
  sha256sum "$CONFIG"
  echo "health=OK"
  curl --fail --silent --show-error "http://${HOST}:${PORT}/v1/models"
  echo
  npu-smi info
  OUT_DIR="$WAV_DIR" bash "${PROJECT_ROOT}/scripts/smoke_audio.sh"
  "$PYTHON_BIN" "${PROJECT_ROOT}/scripts/inspect_wavs.py" "$WAV_DIR"
  echo "DEMO_OK"
} 2>&1 | tee "$RUN_DIR/demo_terminal.log"
