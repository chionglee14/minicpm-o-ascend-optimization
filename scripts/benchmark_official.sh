#!/usr/bin/env bash
set -euo pipefail

WORK_ROOT="${WORK_ROOT:-/workspace/user_data/minicpm-vllm-omni}"
REPO_DIR="${REPO_DIR:-${WORK_ROOT}/vllm-omni-challenge}"
PYTHON_BIN="${PYTHON_BIN:-/usr/local/python3.12.13/bin/python3}"
BENCHMARK_DIR="${BENCHMARK_DIR:-${WORK_ROOT}/results/benchmark_official}"

mkdir -p "$BENCHMARK_DIR"
cd "$REPO_DIR"

if curl --silent --fail http://127.0.0.1:8091/health >/dev/null; then
  echo "Port 8091 still has a live service. Stop it before the official harness starts another model." >&2
  exit 2
fi

export VLLM_WORKER_MULTIPROC_METHOD="${VLLM_WORKER_MULTIPROC_METHOD:-spawn}"
export BENCHMARK_DIR

"$PYTHON_BIN" -m pytest -s -v \
  tests/dfx/perf/scripts/run_benchmark.py \
  --test-config-file tests/dfx/perf/tests/test_minicpmo_4_5.json

