#!/usr/bin/env bash
set -euo pipefail

ARCHIVE="${ARCHIVE:-/workspace/shared_assets/datasets/CowboyZ/seed-tts-eval/seedtts_testset.tar}"
DATASET_ROOT="${DATASET_ROOT:-/workspace/user_data/minicpm-vllm-omni/datasets/seed-tts-mini}"

test -r "$ARCHIVE"
mkdir -p "$DATASET_ROOT/en/prompt-wavs"

# Select the four smoke-test rows from the read-only competition archive at
# runtime. Keeping the metadata out of this repository avoids redistributing a
# benchmark-data excerpt while preserving deterministic request selection.
tar -xOf "$ARCHIVE" seedtts_testset/en/meta.lst \
  | awk -F'|' '
      BEGIN {
        keep["common_voice_en_10119832-common_voice_en_10119840"] = 1
        keep["common_voice_en_10119832-common_voice_en_10119847"] = 1
        keep["common_voice_en_103675-common_voice_en_103676"] = 1
        keep["common_voice_en_103675-common_voice_en_103677"] = 1
      }
      $1 in keep { print }
    ' > "$DATASET_ROOT/en/meta.lst"

tar -xf "$ARCHIVE" \
  --strip-components=3 \
  -C "$DATASET_ROOT/en/prompt-wavs" \
  seedtts_testset/en/prompt-wavs/common_voice_en_10119832.wav \
  seedtts_testset/en/prompt-wavs/common_voice_en_103675.wav

test -s "$DATASET_ROOT/en/meta.lst"
test "$(wc -l < "$DATASET_ROOT/en/meta.lst")" -eq 4
test -s "$DATASET_ROOT/en/prompt-wavs/common_voice_en_10119832.wav"
test -s "$DATASET_ROOT/en/prompt-wavs/common_voice_en_103675.wav"

echo "Prepared read-only-derived 4-row dataset slice at $DATASET_ROOT"
