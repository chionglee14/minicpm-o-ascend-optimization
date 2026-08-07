#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/workspace/user_data/minicpm-vllm-omni/submission}"
ARCHIVE="${ARCHIVE:-/workspace/shared_assets/datasets/CowboyZ/seed-tts-eval/seedtts_testset.tar}"
DATASET_ROOT="${DATASET_ROOT:-/workspace/user_data/minicpm-vllm-omni/datasets/seed-tts-mini}"

test -r "$ARCHIVE"
test -r "$PROJECT_ROOT/tests/data/seed_tts_mini/en/meta.lst"
mkdir -p "$DATASET_ROOT/en/prompt-wavs"
cp "$PROJECT_ROOT/tests/data/seed_tts_mini/en/meta.lst" "$DATASET_ROOT/en/meta.lst"

tar -xf "$ARCHIVE" \
  --strip-components=3 \
  -C "$DATASET_ROOT/en/prompt-wavs" \
  seedtts_testset/en/prompt-wavs/common_voice_en_10119832.wav \
  seedtts_testset/en/prompt-wavs/common_voice_en_103675.wav

test -s "$DATASET_ROOT/en/meta.lst"
test -s "$DATASET_ROOT/en/prompt-wavs/common_voice_en_10119832.wav"
test -s "$DATASET_ROOT/en/prompt-wavs/common_voice_en_103675.wav"

echo "Prepared read-only-derived 4-row dataset at $DATASET_ROOT"

