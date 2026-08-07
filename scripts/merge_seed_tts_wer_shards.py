#!/usr/bin/env python3
"""Merge non-overlapping outputs from eval_seed_tts_openai_whisper.py."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("shards", type=Path, nargs="+")
    return parser.parse_args()


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
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in args.shards]
    if not payloads:
        raise ValueError("no shards supplied")
    first = payloads[0]
    checkpoint_sha256 = first["checkpoint_sha256"]
    seed = first["seed"]
    num_prompts = int(first["num_prompts"])
    items_by_index: dict[int, dict[str, Any]] = {}
    for path, payload in zip(args.shards, payloads, strict=True):
        if payload["checkpoint_sha256"] != checkpoint_sha256:
            raise ValueError(f"checkpoint mismatch in {path}")
        if payload["seed"] != seed or int(payload["num_prompts"]) != num_prompts:
            raise ValueError(f"dataset selection mismatch in {path}")
        for item in payload["items"]:
            index = int(item["index"])
            if index in items_by_index:
                raise ValueError(f"duplicate item index {index} in {path}")
            items_by_index[index] = item
    expected = set(range(num_prompts))
    if set(items_by_index) != expected:
        missing = sorted(expected - set(items_by_index))
        extra = sorted(set(items_by_index) - expected)
        raise ValueError(f"shard coverage mismatch: missing={missing}, extra={extra}")
    items = [items_by_index[index] for index in range(num_prompts)]
    output = {
        "protocol": first["protocol"],
        "official_protocol": False,
        "note": first["note"],
        "checkpoint": first["checkpoint"],
        "checkpoint_sha256": checkpoint_sha256,
        "dataset_meta": first["dataset_meta"],
        "seed": seed,
        "num_prompts": num_prompts,
        "summary": summarize(items),
        "items": items,
        "merged_shards": [str(path) for path in args.shards],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output["summary"], indent=2))
    return 0 if output["summary"]["failed_pairs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
