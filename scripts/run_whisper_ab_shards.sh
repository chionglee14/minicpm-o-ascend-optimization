#!/usr/bin/env bash
set -euo pipefail

WORK_ROOT="${WORK_ROOT:-/workspace/user_data/minicpm-vllm-omni}"
PYTHON_BIN="${PYTHON_BIN:-/usr/local/python3.12.13/bin/python3}"
SCRIPT_DIR="${SCRIPT_DIR:-${WORK_ROOT}/submission/scripts}"
MODEL_DIR="${MODEL_DIR:-${WORK_ROOT}/eval_models/openai-whisper}"
DATASET_ROOT="${DATASET_ROOT:-${WORK_ROOT}/datasets/seedtts_testset}"
BASELINE_WAV_DIR="${BASELINE_WAV_DIR:-${WORK_ROOT}/results/accuracy/baseline/wavs}"
CANDIDATE_WAV_DIR="${CANDIDATE_WAV_DIR:-${WORK_ROOT}/results/accuracy/steps9/wavs}"
OUT_DIR="${OUT_DIR:-${WORK_ROOT}/results/accuracy/whisper_shards}"
NUM_PROMPTS="${NUM_PROMPTS:-32}"
SHARD_SIZE="${SHARD_SIZE:-4}"
THREADS_PER_SHARD="${THREADS_PER_SHARD:-32}"

if (( NUM_PROMPTS % SHARD_SIZE != 0 )); then
  echo "NUM_PROMPTS must be divisible by SHARD_SIZE" >&2
  exit 2
fi

mkdir -p "$OUT_DIR/logs"
pids=()
shards=()
for ((start = 0; start < NUM_PROMPTS; start += SHARD_SIZE)); do
  end=$((start + SHARD_SIZE))
  shard="$OUT_DIR/shard_${start}_${end}.json"
  log="$OUT_DIR/logs/shard_${start}_${end}.log"
  shards+=("$shard")
  "$PYTHON_BIN" "$SCRIPT_DIR/eval_seed_tts_openai_whisper.py" \
    --model-dir "$MODEL_DIR" \
    --dataset-root "$DATASET_ROOT" \
    --baseline-wav-dir "$BASELINE_WAV_DIR" \
    --candidate-wav-dir "$CANDIDATE_WAV_DIR" \
    --output "$shard" \
    --num-prompts "$NUM_PROMPTS" \
    --seed 0 \
    --threads "$THREADS_PER_SHARD" \
    --start-index "$start" \
    --end-index "$end" \
    >"$log" 2>&1 &
  pid="$!"
  pids+=("$pid")
  echo "started shard [$start,$end) pid=$pid log=$log"
done

failed=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    failed=1
  fi
done
if (( failed != 0 )); then
  echo "one or more Whisper shards failed; inspect $OUT_DIR/logs" >&2
  exit 1
fi

"$PYTHON_BIN" "$SCRIPT_DIR/merge_seed_tts_wer_shards.py" \
  --output "$OUT_DIR/whisper_ab_c1_n${NUM_PROMPTS}.json" \
  "${shards[@]}"
