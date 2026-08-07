#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-/usr/local/python3.12.13/bin/python3}"
WORK_ROOT="${WORK_ROOT:-/workspace/user_data/minicpm-vllm-omni}"
REPO_DIR="${REPO_DIR:-${WORK_ROOT}/vllm-omni-challenge}"
REPO_URL="${REPO_URL:-https://github.com/vllm-project/vllm-omni.git}"
BRANCH="${BRANCH:-minicpm-challenge}"

mkdir -p "$WORK_ROOT/baseline/environment"
"$PYTHON_BIN" -m pip freeze >"$WORK_ROOT/baseline/environment/pip-before-install.txt"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$REPO_DIR"
fi

"$PYTHON_BIN" -m pip install "stepaudio2-minicpmo==0.1.1"
"$PYTHON_BIN" -m pip install "step-audio2==1.0.0" --no-deps
"$PYTHON_BIN" -m pip install "onnxruntime-cann==1.24.4"

cd "$REPO_DIR"
SETUPTOOLS_SCM_PRETEND_VERSION=0.25.0 \
  "$PYTHON_BIN" -m pip install -e .

"$PYTHON_BIN" -m pip freeze >"$WORK_ROOT/baseline/environment/pip-after-install.txt"
git rev-parse HEAD >"$WORK_ROOT/baseline/environment/vllm-omni-commit.txt"

echo "Installed challenge branch at $REPO_DIR"
echo "Review pip-before-install.txt and pip-after-install.txt before benchmarking."

