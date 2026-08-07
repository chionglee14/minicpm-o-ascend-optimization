#!/usr/bin/env python3
"""Compare two vLLM-Omni benchmark JSON files without hiding failed requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


LOWER_IS_BETTER = (
    "mean_ttft_ms",
    "mean_audio_ttfp_ms",
    "mean_audio_rtf",
    "mean_e2el_ms",
)
HIGHER_IS_BETTER = ("request_throughput",)


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def status(name: str, data: dict) -> str:
    return (
        f"{name}: completed={data.get('completed')}/{data.get('num_prompts')}, "
        f"failed={data.get('failed')}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()

    baseline = load(args.baseline)
    candidate = load(args.candidate)
    print(status("baseline", baseline))
    print(status("candidate", candidate))

    valid = True
    for data in (baseline, candidate):
        valid &= data.get("completed") == data.get("num_prompts")
        valid &= data.get("failed") == 0
    if not valid:
        raise SystemExit("Comparison invalid: at least one run has failed requests")

    print("metric,baseline,candidate,relative_change")
    for key in LOWER_IS_BETTER:
        old = float(baseline[key])
        new = float(candidate[key])
        improvement = (old - new) / old * 100.0
        print(f"{key},{old:.6f},{new:.6f},{improvement:+.2f}% lower-is-better")
    for key in HIGHER_IS_BETTER:
        old = float(baseline[key])
        new = float(candidate[key])
        improvement = (new - old) / old * 100.0
        print(f"{key},{old:.6f},{new:.6f},{improvement:+.2f}% higher-is-better")

    if baseline.get("input_lens") != candidate.get("input_lens"):
        print("WARNING: input_lens differ; this is not a fixed-input A/B")
    if baseline.get("generated_texts") != candidate.get("generated_texts"):
        print("WARNING: generated texts differ; inspect sampling and precision")


if __name__ == "__main__":
    main()

