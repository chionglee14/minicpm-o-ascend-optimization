#!/usr/bin/env bash
set -euo pipefail

WORK_ROOT="${WORK_ROOT:-/workspace/user_data/minicpm-vllm-omni}"
PROJECT_ROOT="${PROJECT_ROOT:-${WORK_ROOT}/submission}"
REPO_DIR="${REPO_DIR:-${WORK_ROOT}/vllm-omni-challenge}"
MODEL_DIR="${MODEL_DIR:-/workspace/shared_assets/models/OpenBMB/MiniCPM-o-4_5}"
CONFIG="${CONFIG:-${PROJECT_ROOT}/configs/baseline_minicpmo_4_5.yaml}"
VLLM_BIN="${VLLM_BIN:-/usr/local/python3.12.13/bin/vllm}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8091}"
LOG_DIR="${LOG_DIR:-${WORK_ROOT}/results/server}"

test -r "$MODEL_DIR/config.json"
test -r "$CONFIG"
test -d "$REPO_DIR"
mkdir -p "$LOG_DIR"

export VLLM_WORKER_MULTIPROC_METHOD="${VLLM_WORKER_MULTIPROC_METHOD:-spawn}"
export PYTHONUNBUFFERED=1

cd "$REPO_DIR"
"$VLLM_BIN" serve "$MODEL_DIR" \
  --omni \
  --served-model-name openbmb/MiniCPM-o-4_5 \
  --trust-remote-code \
  --deploy-config "$CONFIG" \
  --stage-init-timeout 600 \
  --host "$HOST" \
  --port "$PORT" \
  2>&1 | tee "$LOG_DIR/server.log"

