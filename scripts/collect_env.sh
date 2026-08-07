#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/workspace/user_data/minicpm-vllm-omni/submission}"
PYTHON_BIN="${PYTHON_BIN:-/usr/local/python3.12.13/bin/python3}"
OUT_DIR="${OUT_DIR:-${PROJECT_ROOT}/results/environment}"

mkdir -p "$OUT_DIR"
date -Ins >"$OUT_DIR/timestamp.txt"
uname -a >"$OUT_DIR/uname.txt"
"$PYTHON_BIN" --version >"$OUT_DIR/python.txt" 2>&1
"$PYTHON_BIN" -m pip freeze >"$OUT_DIR/pip-freeze.txt"
npu-smi info >"$OUT_DIR/npu-smi.txt" 2>&1

if [[ -d /workspace/user_data/minicpm-vllm-omni/vllm-omni-challenge/.git ]]; then
  git -C /workspace/user_data/minicpm-vllm-omni/vllm-omni-challenge \
    rev-parse HEAD >"$OUT_DIR/vllm-omni-commit.txt"
fi

echo "Environment fingerprint saved to $OUT_DIR"

