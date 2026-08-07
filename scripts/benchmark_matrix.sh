#!/usr/bin/env bash
set -euo pipefail

WORK_ROOT="${WORK_ROOT:-/workspace/user_data/minicpm-vllm-omni}"
PROJECT_ROOT="${PROJECT_ROOT:-${WORK_ROOT}/submission}"
DATASET_ROOT="${DATASET_ROOT:-${WORK_ROOT}/datasets/seedtts_testset}"
OUT_DIR="${OUT_DIR:-${WORK_ROOT}/results/benchmark_matrix}"
LABEL_PREFIX="${LABEL_PREFIX:-candidate_matrix}"

test -r "${DATASET_ROOT}/en/meta.lst"
curl --fail --silent --show-error http://127.0.0.1:8091/health >/dev/null
mkdir -p "$OUT_DIR"

# Same request-count/concurrency matrix as the challenge configuration.  The
# model service is kept alive across all three rows so only the explicit two
# warmups in benchmark_quick.sh precede each measured row.
for specification in "1:32" "4:64" "8:128"; do
  IFS=: read -r concurrency prompts <<<"$specification"
  echo "Running c${concurrency}/n${prompts}"
  DATASET_ROOT="$DATASET_ROOT" \
  NUM_PROMPTS="$prompts" \
  MAX_CONCURRENCY="$concurrency" \
  DISABLE_SHUFFLE=0 \
  LABEL="$LABEL_PREFIX" \
  OUT_DIR="$OUT_DIR" \
    bash "${PROJECT_ROOT}/scripts/benchmark_quick.sh"
done

