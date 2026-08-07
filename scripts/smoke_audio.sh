#!/usr/bin/env bash
set -euo pipefail

WORK_ROOT="${WORK_ROOT:-/workspace/user_data/minicpm-vllm-omni}"
REPO_DIR="${REPO_DIR:-${WORK_ROOT}/vllm-omni-challenge}"
PYTHON_BIN="${PYTHON_BIN:-/usr/local/python3.12.13/bin/python3}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8091}"
OUT_DIR="${OUT_DIR:-${WORK_ROOT}/results/smoke_audio}"

mkdir -p "$OUT_DIR"
curl --fail --silent --show-error "http://${HOST}:${PORT}/health" >/dev/null

cd "$OUT_DIR"
"$PYTHON_BIN" \
  "$REPO_DIR/examples/online_serving/minicpmo/openai_chat_completion_client_for_multimodal_generation.py" \
  --query-type text \
  --prompt '请用一句简短的中文介绍你自己。' \
  --modalities text,audio \
  --host "$HOST" \
  --port "$PORT" \
  --model openbmb/MiniCPM-o-4_5 \
  --stream

find "$OUT_DIR" -maxdepth 1 -type f -name '*.wav' -size +44c -print

