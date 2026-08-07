#!/usr/bin/env python3
"""Paired Seed-TTS WER check with the official OpenAI Whisper large-v3 weights.

This is an offline A/B quality gate.  It uses the same large-v3 checkpoint as
the published Seed-TTS protocol, but OpenAI Whisper's decoder instead of the
official Transformers decoder, so the result must be labelled as a proxy and
must not be presented as the final official WER.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import string
from pathlib import Path
from typing import Any

import jiwer
import numpy as np
import scipy.signal
import soundfile as sf
import torch
import whisper
from zhon.hanzi import punctuation as zh_punctuation


EXPECTED_LARGE_V3_SHA256 = (
    "e5b1a55b89c1367dacf97e3e19bfd829a01529dbfdeefa8caeb59b3f1b81dadb"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--baseline-wav-dir", type=Path, required=True)
    parser.add_argument("--candidate-wav-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--num-prompts", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threads", type=int, default=32)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(meta_path: Path, seed: int, count: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(
        meta_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        fields = line.split("|")
        if len(fields) != 4:
            raise ValueError(f"{meta_path}:{line_number}: expected 4 fields")
        utterance_id, prompt_text, prompt_wav, target_text = fields
        rows.append(
            {
                "utterance_id": utterance_id,
                "prompt_text": prompt_text,
                "prompt_wav": prompt_wav,
                "target_text": target_text,
            }
        )
    random.Random(seed).shuffle(rows)
    if len(rows) < count:
        raise ValueError(f"requested {count} rows, dataset only has {len(rows)}")
    return rows[:count]


def expected_wav_path(directory: Path, index: int, utterance_id: str) -> Path:
    return directory / f"{index:05d}_{utterance_id}_en.wav"


def load_audio_16k(path: Path) -> np.ndarray:
    audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if sample_rate != 16000:
        divisor = int(np.gcd(sample_rate, 16000))
        mono = scipy.signal.resample_poly(
            mono, 16000 // divisor, sample_rate // divisor
        )
    return np.ascontiguousarray(mono, dtype=np.float32)


def normalize_english(text: str) -> str:
    normalized = text
    for character in zh_punctuation + string.punctuation:
        if character != "'":
            normalized = normalized.replace(character, "")
    return normalized.lower()


def word_error_rate(reference: str, hypothesis: str) -> float:
    result = jiwer.process_words(
        normalize_english(reference), normalize_english(hypothesis)
    )
    return float(result.wer)


def transcribe(model: Any, path: Path) -> str:
    audio = load_audio_16k(path)
    result = model.transcribe(
        audio,
        language="en",
        task="transcribe",
        fp16=False,
        temperature=0.0,
        condition_on_previous_text=False,
        verbose=False,
    )
    return str(result["text"]).strip()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [item for item in items if not item.get("error")]
    baseline_wers = [float(item["baseline_wer"]) for item in complete]
    candidate_wers = [float(item["candidate_wer"]) for item in complete]
    baseline_mean = statistics.fmean(baseline_wers) if baseline_wers else None
    candidate_mean = statistics.fmean(candidate_wers) if candidate_wers else None
    delta = (
        candidate_mean - baseline_mean
        if baseline_mean is not None and candidate_mean is not None
        else None
    )
    relative = (
        delta / baseline_mean
        if delta is not None and baseline_mean not in (None, 0.0)
        else None
    )
    return {
        "requested": len(items),
        "evaluated_pairs": len(complete),
        "failed_pairs": len(items) - len(complete),
        "baseline_mean_wer": baseline_mean,
        "baseline_median_wer": (
            statistics.median(baseline_wers) if baseline_wers else None
        ),
        "candidate_mean_wer": candidate_mean,
        "candidate_median_wer": (
            statistics.median(candidate_wers) if candidate_wers else None
        ),
        "candidate_minus_baseline_wer": delta,
        "candidate_relative_change": relative,
    }


def main() -> int:
    args = parse_args()
    checkpoint = args.model_dir / "large-v3.pt"
    meta_path = args.dataset_root / "en" / "meta.lst"
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if not meta_path.is_file():
        raise FileNotFoundError(meta_path)

    checkpoint_sha256 = sha256_file(checkpoint)
    if checkpoint_sha256 != EXPECTED_LARGE_V3_SHA256:
        raise ValueError(
            "large-v3 checkpoint checksum mismatch: "
            f"expected {EXPECTED_LARGE_V3_SHA256}, got {checkpoint_sha256}"
        )

    rows = load_rows(meta_path, args.seed, args.num_prompts)
    end_index = args.num_prompts if args.end_index is None else args.end_index
    if not 0 <= args.start_index < end_index <= args.num_prompts:
        raise ValueError(
            "require 0 <= start-index < end-index <= num-prompts, got "
            f"{args.start_index}, {end_index}, {args.num_prompts}"
        )
    indexed_rows = list(enumerate(rows))[args.start_index:end_index]
    selected_indices = {index for index, _ in indexed_rows}
    for index, row in indexed_rows:
        for directory in (args.baseline_wav_dir, args.candidate_wav_dir):
            path = expected_wav_path(directory, index, row["utterance_id"])
            if not path.is_file():
                raise FileNotFoundError(path)

    torch.set_num_threads(max(1, args.threads))
    print(f"Loading Whisper large-v3 on CPU from {checkpoint}", flush=True)
    model = whisper.load_model(
        "large-v3", device="cpu", download_root=str(args.model_dir)
    )

    progress_path = args.output.with_suffix(args.output.suffix + ".progress")
    items_by_index: dict[int, dict[str, Any]] = {}
    if progress_path.is_file():
        previous = json.loads(progress_path.read_text(encoding="utf-8"))
        for item in previous.get("items", []):
            index = int(item["index"])
            if index in selected_indices:
                items_by_index[index] = item
        print(f"Resuming with {len(items_by_index)} completed pairs", flush=True)

    for index, row in indexed_rows:
        if index in items_by_index and not items_by_index[index].get("error"):
            continue
        baseline_path = expected_wav_path(
            args.baseline_wav_dir, index, row["utterance_id"]
        )
        candidate_path = expected_wav_path(
            args.candidate_wav_dir, index, row["utterance_id"]
        )
        print(
            f"[{index + 1:02d}/{args.num_prompts:02d}] {row['utterance_id']}",
            flush=True,
        )
        item: dict[str, Any] = {
            "index": index,
            "utterance_id": row["utterance_id"],
            "reference": row["target_text"],
            "baseline_wav": str(baseline_path),
            "candidate_wav": str(candidate_path),
        }
        try:
            baseline_hypothesis = transcribe(model, baseline_path)
            candidate_hypothesis = transcribe(model, candidate_path)
            item.update(
                {
                    "baseline_hypothesis": baseline_hypothesis,
                    "candidate_hypothesis": candidate_hypothesis,
                    "baseline_wer": word_error_rate(
                        row["target_text"], baseline_hypothesis
                    ),
                    "candidate_wer": word_error_rate(
                        row["target_text"], candidate_hypothesis
                    ),
                }
            )
        except Exception as error:  # Keep progress if one malformed item fails.
            item["error"] = f"{type(error).__name__}: {error}"
        items_by_index[index] = item
        ordered = [items_by_index[i] for i in sorted(items_by_index)]
        write_json(
            progress_path,
            {
                "protocol": "openai-whisper-large-v3-proxy",
                "checkpoint_sha256": checkpoint_sha256,
                "items": ordered,
                "summary": summarize(ordered),
            },
        )

    items = [items_by_index[i] for i in sorted(selected_indices)]
    payload = {
        "protocol": "openai-whisper-large-v3-proxy",
        "official_protocol": False,
        "note": (
            "Uses the official large-v3 checkpoint with OpenAI Whisper decoding; "
            "final competition WER must still be measured by the official evaluator."
        ),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "dataset_meta": str(meta_path),
        "seed": args.seed,
        "num_prompts": args.num_prompts,
        "start_index": args.start_index,
        "end_index": end_index,
        "summary": summarize(items),
        "items": items,
    }
    write_json(args.output, payload)
    print(json.dumps(payload["summary"], indent=2), flush=True)
    return 0 if payload["summary"]["failed_pairs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
