#!/usr/bin/env bash
set -euo pipefail

WORK_ROOT="${WORK_ROOT:-/workspace/user_data/minicpm-vllm-omni}"
DATASET_ROOT="${DATASET_ROOT:-${WORK_ROOT}/datasets/seed-tts-mini}"
MODEL_DIR="${MODEL_DIR:-/workspace/shared_assets/models/OpenBMB/MiniCPM-o-4_5}"
VLLM_BIN="${VLLM_BIN:-/usr/local/python3.12.13/bin/vllm}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8091}"
NUM_PROMPTS="${NUM_PROMPTS:-4}"
MAX_CONCURRENCY="${MAX_CONCURRENCY:-1}"
LABEL="${LABEL:-baseline}"
DISABLE_SHUFFLE="${DISABLE_SHUFFLE:-1}"
OUT_DIR="${OUT_DIR:-${WORK_ROOT}/results/benchmark_quick}"

test -r "$DATASET_ROOT/en/meta.lst"
test -r "$MODEL_DIR/config.json"
mkdir -p "$OUT_DIR"
curl --fail --silent --show-error "http://${HOST}:${PORT}/health" >/dev/null

# The served model name is the API identifier. The tokenizer is loaded from the
# shared local weights so the benchmark never depends on Hugging Face access.
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

SHUFFLE_ARGS=()
if [[ "$DISABLE_SHUFFLE" == "1" ]]; then
  SHUFFLE_ARGS+=(--disable-shuffle)
fi

"$VLLM_BIN" bench serve --omni \
  --host "$HOST" \
  --port "$PORT" \
  --model openbmb/MiniCPM-o-4_5 \
  --tokenizer "$MODEL_DIR" \
  --dataset-name seed-tts \
  --dataset-path "$DATASET_ROOT" \
  "${SHUFFLE_ARGS[@]}" \
  --backend openai-chat-omni \
  --endpoint /v1/chat/completions \
  --num-prompts "$NUM_PROMPTS" \
  --max-concurrency "$MAX_CONCURRENCY" \
  --request-rate inf \
  --seed 0 \
  --temperature 0 \
  --num-warmups 2 \
  --no-oversample \
  --trust-remote-code \
  --seed-tts-locale en \
  --extra-body '{"modalities":["text","audio"],"chat_template_kwargs":{"enable_thinking":false,"use_tts_template":true}}' \
  --percentile-metrics ttft,e2el,audio_ttfp,audio_rtf,audio_duration \
  --save-result \
  --save-detailed \
  --label "$LABEL" \
  --result-dir "$OUT_DIR" \
  --result-filename "${LABEL}_c${MAX_CONCURRENCY}_n${NUM_PROMPTS}.json"
