#!/usr/bin/env python3
"""Offline structural and evidence checks for the submission directory."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STRICT_ASV_FINGERPRINT = (
    "97bb7c4af9ead07bf1c94aff9093b0f669866036d5d23663a0a80f763b5485dc"
)


class Validation:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes: list[str] = []
        self.warnings: list[str] = []

    def check(self, condition: bool, message: str) -> None:
        if condition:
            self.passes.append(message)
        else:
            self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def load_json(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def functional_yaml_lines(path: Path) -> list[str]:
    return [
        line.rstrip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lower_is_better(base: float, candidate: float) -> float:
    return 100.0 * (base - candidate) / base


def higher_is_better(base: float, candidate: float) -> float:
    return 100.0 * (candidate - base) / base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    validation = Validation()

    required = [
        ".gitattributes",
        ".gitignore",
        ".github/workflows/offline-ci.yml",
        "LICENSE",
        "README.md",
        "RESULT_MANIFEST.sha256",
        "THIRD_PARTY.md",
        "configs/baseline_minicpmo_4_5.yaml",
        "configs/experiment_steps9.yaml",
        "configs/experiment_codec20.yaml",
        "scripts/start_server.sh",
        "scripts/run_demo.sh",
        "scripts/inspect_wavs.py",
        "scripts/build_pdf_report.py",
        "scripts/benchmark_matrix.sh",
        "scripts/eval_seed_tts_openai_whisper.py",
        "scripts/eval_seed_tts_wavlm_proxy.py",
        "reports/BASELINE.md",
        "reports/EXPERIMENTS.md",
        "reports/ASV_PROXY.md",
        "reports/EXECUTIVE_SUMMARY.md",
        "reports/SUBMISSION_CHECKLIST.md",
        "results/accuracy/asv_ab_c1_n32_strict.json",
        "evidence/README.md",
        "evidence/RUN_PROVENANCE.md",
        "evidence/environment/npu-smi.txt",
        "evidence/environment/pip-freeze.txt",
        "evidence/environment/python.txt",
        "evidence/environment/runtime-versions.txt",
        "evidence/environment/timestamp.txt",
        "evidence/environment/uname.txt",
        "evidence/environment/vllm-omni-commit.txt",
        "output/pdf/MiniCPM-o_4.5_Ascend_vLLM-Omni_Optimization_Report.pdf",
    ]
    for relative in required:
        validation.check((ROOT / relative).is_file(), f"required file: {relative}")

    for line in (ROOT / "RESULT_MANIFEST.sha256").read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = ROOT / relative
        validation.check(
            path.is_file() and sha256_file(path) == expected,
            f"manifest hash: {relative}",
        )

    baseline_lines = functional_yaml_lines(
        ROOT / "configs/baseline_minicpmo_4_5.yaml"
    )
    candidate_lines = functional_yaml_lines(ROOT / "configs/experiment_steps9.yaml")
    added = collections.Counter(candidate_lines) - collections.Counter(baseline_lines)
    removed = collections.Counter(baseline_lines) - collections.Counter(candidate_lines)
    validation.check(
        added == collections.Counter({"      token2wav_n_timesteps: 9": 1})
        and not removed,
        "steps9 has exactly one functional config addition",
    )

    performance_files = [
        "results/performance/baseline_repeat_full_c1_n32.json",
        "results/performance/codec20_full_c1_n32.json",
        "results/performance/steps9_full_c1_n32.json",
        "results/performance/steps9_repeat_c1_n32.json",
        "results/performance/steps9_matrix_c4_n64.json",
        "results/performance/steps9_matrix_c8_n128.json",
    ]
    performance: dict[str, dict[str, Any]] = {}
    for relative in performance_files:
        payload = load_json(relative)
        performance[relative] = payload
        complete = int(payload.get("completed", -1))
        requested = int(payload.get("num_prompts", -2))
        failed = int(payload.get("failed", -1))
        validation.check(
            complete == requested and failed == 0,
            f"complete performance result: {Path(relative).name}",
        )
        for key in (
            "mean_ttft_ms",
            "mean_audio_ttfp_ms",
            "mean_audio_rtf",
            "mean_e2el_ms",
            "request_throughput",
            "median_audio_ttfp_ms",
            "p99_audio_ttfp_ms",
            "median_audio_rtf",
            "p99_audio_rtf",
            "median_e2el_ms",
            "p99_e2el_ms",
        ):
            validation.check(
                finite_number(payload.get(key)),
                f"finite {key}: {Path(relative).name}",
            )

    baseline = performance[performance_files[0]]
    codec20 = performance[performance_files[1]]
    steps9_run1 = performance[performance_files[2]]
    steps9_run2 = performance[performance_files[3]]
    validation.check(
        float(codec20["mean_audio_rtf"]) > float(baseline["mean_audio_rtf"]),
        "codec20 rejection is supported by worse RTF",
    )
    for name, candidate in (("steps9 run1", steps9_run1), ("steps9 run2", steps9_run2)):
        validation.check(
            float(candidate["mean_audio_rtf"]) < float(baseline["mean_audio_rtf"]),
            f"{name} improves RTF",
        )
        validation.check(
            float(candidate["mean_audio_ttfp_ms"])
            < float(baseline["mean_audio_ttfp_ms"]),
            f"{name} improves TTFP",
        )
        validation.check(
            float(candidate["mean_e2el_ms"]) < float(baseline["mean_e2el_ms"]),
            f"{name} improves E2E",
        )
        validation.check(
            float(candidate["request_throughput"])
            > float(baseline["request_throughput"]),
            f"{name} improves throughput",
        )

    matrix_completed = sum(
        int(performance[relative]["completed"])
        for relative in (
            performance_files[3],
            performance_files[4],
            performance_files[5],
        )
    )
    validation.check(matrix_completed == 224, "three-row matrix contains 224 requests")

    whisper = load_json("results/accuracy/whisper_ab_c1_n32.json")
    asv = load_json("results/accuracy/asv_ab_c1_n32.json")
    strict_asv_path = ROOT / "results/accuracy/asv_ab_c1_n32_strict.json"
    strict_asv = (
        load_json("results/accuracy/asv_ab_c1_n32_strict.json")
        if strict_asv_path.is_file()
        else {}
    )
    proxy_results = [("WER", whisper), ("ASV legacy", asv)]
    if strict_asv:
        proxy_results.append(("ASV strict v2", strict_asv))
    for name, payload in proxy_results:
        summary = payload.get("summary", {})
        validation.check(payload.get("official_protocol") is False, f"{name} is proxy-labelled")
        validation.check(
            int(summary.get("requested", -1)) == 32
            and int(summary.get("evaluated_pairs", -2)) == 32
            and int(summary.get("failed_pairs", -1)) == 0,
            f"{name} proxy contains 32 complete pairs",
        )

    whisper_summary = whisper["summary"]
    validation.check(
        math.isclose(
            float(whisper_summary["baseline_mean_wer"]),
            float(whisper_summary["candidate_mean_wer"]),
            rel_tol=0.0,
            abs_tol=1e-15,
        ),
        "candidate and baseline proxy WER are identical",
    )

    strict_asv_source = (
        ROOT / "scripts/eval_seed_tts_wavlm_proxy.py"
    ).read_text(encoding="utf-8")
    for marker in (
        "EXPECTED_CHECKPOINT_SHA256",
        "EXPECTED_SOURCE_SHA256",
        "run_fingerprint",
        "allow_nan=False",
        "quality_gate_passed",
    ):
        validation.check(marker in strict_asv_source, f"strict ASV safeguard: {marker}")

    if strict_asv:
        validation.check(
            strict_asv.get("run_fingerprint") == STRICT_ASV_FINGERPRINT,
            "bundled strict ASV run fingerprint",
        )
        validation.check(
            strict_asv.get("summary", {}).get("quality_gate_passed") is True,
            "bundled strict ASV quality gate",
        )
        descriptor = strict_asv.get("run_descriptor", {})
        input_manifest = descriptor.get("input_manifest", [])
        validation.check(
            len(input_manifest) == 32
            and all(
                is_sha256(item.get(hash_key))
                for item in input_manifest
                for hash_key in (
                    "prompt_wav_sha256",
                    "baseline_wav_sha256",
                    "candidate_wav_sha256",
                )
            ),
            "strict ASV binds 96 input WAV hashes",
        )
        verified_sources = strict_asv.get("verified_sources", {})
        validation.check(
            len(verified_sources) == 3
            and all(
                is_sha256(source.get("sha256"))
                for source in verified_sources.values()
            ),
            "strict ASV binds three source hashes",
        )
        strict_summary = strict_asv["summary"]
        legacy_summary = asv["summary"]
        compared_keys = (
            "baseline_mean_similarity",
            "candidate_mean_similarity",
            "candidate_minus_baseline_similarity",
            "candidate_relative_change",
        )
        validation.check(
            all(
                math.isclose(
                    float(strict_summary[key]),
                    float(legacy_summary[key]),
                    rel_tol=0.0,
                    abs_tol=1e-15,
                )
                for key in compared_keys
            ),
            "strict and legacy ASV summary metrics match",
        )
    else:
        validation.warn(
            "strict ASV v2 raw JSON is not bundled; strict run provenance cannot "
            "be validated locally"
        )

    scorecard = {
        "c1_steps9_repeat": {
            "ttft_improvement_percent": lower_is_better(
                float(baseline["mean_ttft_ms"]), float(steps9_run2["mean_ttft_ms"])
            ),
            "ttfp_improvement_percent": lower_is_better(
                float(baseline["mean_audio_ttfp_ms"]),
                float(steps9_run2["mean_audio_ttfp_ms"]),
            ),
            "rtf_improvement_percent": lower_is_better(
                float(baseline["mean_audio_rtf"]),
                float(steps9_run2["mean_audio_rtf"]),
            ),
            "e2e_improvement_percent": lower_is_better(
                float(baseline["mean_e2el_ms"]), float(steps9_run2["mean_e2el_ms"])
            ),
            "throughput_improvement_percent": higher_is_better(
                float(baseline["request_throughput"]),
                float(steps9_run2["request_throughput"]),
            ),
        },
        "matrix_completed_requests": matrix_completed,
        "matrix_tail_latency": {
            "c4_p99_ttfp_ms": float(
                performance[performance_files[4]]["p99_audio_ttfp_ms"]
            ),
            "c4_p99_rtf": float(
                performance[performance_files[4]]["p99_audio_rtf"]
            ),
            "c4_p99_e2e_ms": float(
                performance[performance_files[4]]["p99_e2el_ms"]
            ),
            "c8_p99_ttfp_ms": float(
                performance[performance_files[5]]["p99_audio_ttfp_ms"]
            ),
            "c8_p99_rtf": float(
                performance[performance_files[5]]["p99_audio_rtf"]
            ),
            "c8_p99_e2e_ms": float(
                performance[performance_files[5]]["p99_e2el_ms"]
            ),
        },
        "proxy_wer_delta": float(whisper_summary["candidate_minus_baseline_wer"]),
        "proxy_asv_relative_change": float(
            (strict_asv or asv)["summary"]["candidate_relative_change"]
        ),
    }
    output = {
        "valid": not validation.failures,
        "passes": validation.passes,
        "warnings": validation.warnings,
        "failures": validation.failures,
        "scorecard": scorecard,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    for message in validation.passes:
        print(f"PASS: {message}")
    for message in validation.warnings:
        print(f"WARN: {message}")
    for message in validation.failures:
        print(f"FAIL: {message}", file=sys.stderr)
    print(json.dumps(scorecard, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if not validation.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
