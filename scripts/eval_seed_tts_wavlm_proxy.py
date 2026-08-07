#!/usr/bin/env python3
"""Paired Seed-TTS speaker-similarity check with the released WavLM checkpoint.

This is a reproducible offline A/B proxy, not the competition's final ASV
score.  It uses the WavLM-large + ECAPA architecture from seed-tts-eval and
the released ``wavlm_large_finetune.pth`` weights.  The upstream shell script
is CUDA-only, so this driver reconstructs the same model on CPU and records
that protocol difference explicitly in the output.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import platform
import random
import statistics
import sys
import types
from pathlib import Path
from typing import Any

import librosa
import torch
import torch.nn.functional as F
import torchaudio
from torchaudio.transforms import Resample


SEED_TTS_EVAL_COMMIT = "752f4297f090c46bb1a55a1f7439e5944ddefe8d"
S3PRL_COMMIT = "7ab62aaf2606d83da6c71ee74e7d16e0979edbc3"
EXPECTED_CHECKPOINT_SHA256 = (
    "51f07e3b94d9e0262a6a675ef5a087be3dd09e8c62e9d886827f44f82fe7f94b"
)
EXPECTED_SOURCE_SHA256 = {
    "WavLM.py": "de2b981038102edafd88f0aa80bf1d9d0ecab8a8da83aff60f3139a58512dcf2",
    "modules.py": "7a06a14a7dc95c5f65cd6b09ed126013821512489dcfec2e58bd8b544ce46656",
    "ecapa_tdnn.py": "847ef748d91acaec8b58859757481f7642772999b1e702680f06dc8dbdd2408d",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--baseline-wav-dir", type=Path, required=True)
    parser.add_argument("--candidate-wav-dir", type=Path, required=True)
    parser.add_argument("--seed-tts-eval-root", type=Path, required=True)
    parser.add_argument("--s3prl-root", type=Path, required=True)
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


def verify_sha256(path: Path, expected: str, label: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(
            f"{label} SHA-256 mismatch: expected {expected}, got {actual}: {path}"
        )
    return actual


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


def source_paths(seed_tts_eval_root: Path, s3prl_root: Path) -> dict[str, Path]:
    return {
        "WavLM.py": s3prl_root / "s3prl" / "upstream" / "wavlm" / "WavLM.py",
        "modules.py": s3prl_root / "s3prl" / "upstream" / "wavlm" / "modules.py",
        "ecapa_tdnn.py": (
            seed_tts_eval_root
            / "thirdparty"
            / "UniSpeech"
            / "downstreams"
            / "speaker_verification"
            / "models"
            / "ecapa_tdnn.py"
        ),
    }


def environment_versions() -> dict[str, str]:
    versions = {
        "python": platform.python_version(),
        "torch": str(torch.__version__),
        "torchaudio": str(torchaudio.__version__),
        "librosa": str(librosa.__version__),
        "torch_num_threads": str(torch.get_num_threads()),
        "torch_num_interop_threads": str(torch.get_num_interop_threads()),
    }
    try:
        versions["scipy"] = importlib.metadata.version("scipy")
    except importlib.metadata.PackageNotFoundError:
        versions["scipy"] = "not-installed"
    return versions


def build_input_manifest(
    indexed_rows: list[tuple[int, dict[str, str]]],
    dataset_root: Path,
    baseline_wav_dir: Path,
    candidate_wav_dir: Path,
) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for index, row in indexed_rows:
        prompt_path = dataset_root / "en" / row["prompt_wav"]
        baseline_path = expected_wav_path(
            baseline_wav_dir, index, row["utterance_id"]
        )
        candidate_path = expected_wav_path(
            candidate_wav_dir, index, row["utterance_id"]
        )
        entries: dict[str, Any] = {
            "index": index,
            "utterance_id": row["utterance_id"],
        }
        for name, path in (
            ("prompt", prompt_path),
            ("baseline", baseline_path),
            ("candidate", candidate_path),
        ):
            if not path.is_file():
                raise FileNotFoundError(path)
            entries[f"{name}_wav"] = str(path.resolve())
            entries[f"{name}_wav_sha256"] = sha256_file(path)
        manifest.append(entries)
    return manifest


def fingerprint_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def wavlm_large_config() -> dict[str, Any]:
    """Configuration of Microsoft's released WavLM-Large checkpoint.

    Dropout and masking values do not alter evaluation mode, but are retained
    to match the published model configuration.  ``max_distance`` corresponds
    to Hugging Face's ``max_bucket_distance`` field.
    """

    return {
        "extractor_mode": "layer_norm",
        "encoder_layers": 24,
        "encoder_embed_dim": 1024,
        "encoder_ffn_embed_dim": 4096,
        "encoder_attention_heads": 16,
        "activation_fn": "gelu",
        "layer_norm_first": True,
        "conv_feature_layers": (
            "[(512,10,5)] + [(512,3,2)] * 4 + [(512,2,2)] * 2"
        ),
        "conv_bias": False,
        "feature_grad_mult": 1.0,
        "normalize": True,
        "dropout": 0.1,
        "attention_dropout": 0.1,
        "activation_dropout": 0.0,
        "encoder_layerdrop": 0.1,
        "dropout_input": 0.0,
        "dropout_features": 0.0,
        "mask_length": 10,
        "mask_prob": 0.65,
        "mask_selection": "static",
        "mask_other": 0,
        "no_mask_overlap": False,
        "mask_min_space": 1,
        "mask_channel_length": 10,
        "mask_channel_prob": 0.0,
        "mask_channel_selection": "static",
        "mask_channel_other": 0,
        "no_mask_channel_overlap": False,
        "mask_channel_min_space": 1,
        "conv_pos": 128,
        "conv_pos_groups": 16,
        "relative_position_embedding": True,
        "num_buckets": 320,
        "max_distance": 800,
        "gru_rel_pos": True,
    }


def build_model(
    checkpoint: Path, seed_tts_eval_root: Path, s3prl_root: Path
) -> tuple[torch.nn.Module, dict[str, list[str]]]:
    """Build seed-tts-eval's WavLM-large ECAPA model without network access."""

    for root in (seed_tts_eval_root, s3prl_root):
        if not root.is_dir():
            raise FileNotFoundError(root)
        sys.path.insert(0, str(root))

    speaker_root = (
        seed_tts_eval_root
        / "thirdparty"
        / "UniSpeech"
        / "downstreams"
        / "speaker_verification"
    )
    if not speaker_root.is_dir():
        raise FileNotFoundError(speaker_root)
    sys.path.insert(0, str(speaker_root))

    from models.ecapa_tdnn import ECAPA_TDNN_SMALL
    from torch.nn.utils.rnn import pad_sequence

    # Import only the vendored WavLM implementation.  Importing the historical
    # s3prl package itself eagerly imports every upstream expert (including
    # fairseq), although WavLM does not depend on fairseq.
    wavlm_dir = s3prl_root / "s3prl" / "upstream" / "wavlm"
    wavlm_source = wavlm_dir / "WavLM.py"
    if not wavlm_source.is_file():
        raise FileNotFoundError(wavlm_source)
    package_name = "_seed_tts_asv_wavlm"
    package = types.ModuleType(package_name)
    package.__path__ = [str(wavlm_dir)]
    sys.modules[package_name] = package
    module_name = f"{package_name}.WavLM"
    spec = importlib.util.spec_from_file_location(module_name, wavlm_source)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {wavlm_source}")
    wavlm_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = wavlm_module
    spec.loader.exec_module(wavlm_module)
    WavLM = wavlm_module.WavLM
    WavLMConfig = wavlm_module.WavLMConfig

    class LocalWavLMUpstream(torch.nn.Module):
        """Minimal equivalent of s3prl's WavLM UpstreamExpert."""

        def __init__(self) -> None:
            super().__init__()
            self.cfg = WavLMConfig(wavlm_large_config())
            self.model = WavLM(self.cfg)
            self._hidden_states: list[torch.Tensor] = []
            for layer in self.model.encoder.layers:
                layer.register_forward_hook(self._capture_layer_input)
            self.model.encoder.register_forward_hook(self._capture_encoder_output)

        def _capture_layer_input(
            self,
            module: torch.nn.Module,
            inputs: tuple[torch.Tensor, ...],
            output: Any,
        ) -> None:
            self._hidden_states.append(inputs[0].transpose(0, 1))

        def _capture_encoder_output(
            self,
            module: torch.nn.Module,
            inputs: tuple[torch.Tensor, ...],
            output: Any,
        ) -> None:
            self._hidden_states.append(output[0])

        def forward(self, wavs: list[torch.Tensor]) -> dict[str, Any]:
            self._hidden_states.clear()
            if self.cfg.normalize:
                wavs = [F.layer_norm(wav, wav.shape) for wav in wavs]
            device = wavs[0].device
            lengths = torch.tensor(
                [len(wav) for wav in wavs], dtype=torch.long, device=device
            )
            padding_mask = ~torch.lt(
                torch.arange(max(lengths), device=device).unsqueeze(0),
                lengths.unsqueeze(1),
            )
            padded = pad_sequence(wavs, batch_first=True)
            self.model.extract_features(
                padded, padding_mask=padding_mask, mask=False
            )
            return {"hidden_states": tuple(self._hidden_states)}

    def local_upstream() -> torch.nn.Module:
        return LocalWavLMUpstream()

    original_hub_load = torch.hub.load

    def patched_hub_load(repo_or_dir: str, model_name: str, *args: Any, **kwargs: Any):
        if model_name != "wavlm_large":
            raise ValueError(f"unexpected torch.hub model: {model_name}")
        return local_upstream()

    torch.hub.load = patched_hub_load
    try:
        model = ECAPA_TDNN_SMALL(
            feat_dim=1024, feat_type="wavlm_large", config_path=None
        )
    finally:
        torch.hub.load = original_hub_load

    payload = torch.load(
        checkpoint, map_location="cpu", weights_only=True, mmap=True
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("model"), dict):
        raise ValueError("checkpoint does not contain a model state_dict")
    incompatible = model.load_state_dict(payload["model"], strict=False)
    missing = list(incompatible.missing_keys)
    unexpected = list(incompatible.unexpected_keys)
    allowed_unexpected = ["loss_calculator.projection.weight"]
    if missing or unexpected != allowed_unexpected:
        raise RuntimeError(
            "checkpoint/model mismatch: "
            f"missing={missing}, unexpected={unexpected}"
        )
    model.eval()
    return model, {"missing_keys": missing, "unexpected_keys": unexpected}


def load_audio_16k(path: Path) -> torch.Tensor:
    # Match seed-tts-eval/verification.py's librosa + torchaudio path.
    audio, sample_rate = librosa.load(path, sr=None, mono=False)
    if audio.ndim == 2:
        audio = audio[0, :]
    waveform = torch.from_numpy(audio).unsqueeze(0).float()
    if sample_rate != 16000:
        waveform = Resample(orig_freq=sample_rate, new_freq=16000)(waveform)
    return waveform


def embedding(model: torch.nn.Module, path: Path) -> torch.Tensor:
    waveform = load_audio_16k(path)
    with torch.inference_mode():
        return model(waveform).cpu()


def cosine_similarity(left: torch.Tensor, right: torch.Tensor) -> float:
    value = float(F.cosine_similarity(left, right).item())
    if not math.isfinite(value) or not -1.000001 <= value <= 1.000001:
        raise ValueError(f"invalid cosine similarity: {value!r}")
    return value


def summarize(
    items: list[dict[str, Any]], expected_pairs: int | None = None
) -> dict[str, Any]:
    complete = [item for item in items if not item.get("error")]
    baseline = [float(item["baseline_similarity"]) for item in complete]
    candidate = [float(item["candidate_similarity"]) for item in complete]
    deltas = [right - left for left, right in zip(baseline, candidate)]
    baseline_mean = statistics.fmean(baseline) if baseline else None
    candidate_mean = statistics.fmean(candidate) if candidate else None
    delta_mean = statistics.fmean(deltas) if deltas else None
    requested = len(items) if expected_pairs is None else expected_pairs
    all_pairs_complete = len(items) == requested and len(complete) == requested
    summary: dict[str, Any] = {
        "requested": requested,
        "evaluated_pairs": len(complete),
        "failed_pairs": len(items) - len(complete),
        "all_pairs_complete": all_pairs_complete,
        "quality_gate_passed": all_pairs_complete,
        "quality_gate_definition": (
            "all selected pairs produced finite CPU proxy scores; this is not "
            "the competition ASV threshold"
        ),
        "baseline_mean_similarity": baseline_mean,
        "baseline_median_similarity": (
            statistics.median(baseline) if baseline else None
        ),
        "candidate_mean_similarity": candidate_mean,
        "candidate_median_similarity": (
            statistics.median(candidate) if candidate else None
        ),
        "candidate_minus_baseline_similarity": delta_mean,
        "candidate_relative_change": (
            delta_mean / baseline_mean
            if delta_mean is not None and baseline_mean not in (None, 0.0)
            else None
        ),
        "candidate_better_pairs": sum(delta > 0 for delta in deltas),
        "equal_pairs": sum(delta == 0 for delta in deltas),
        "candidate_worse_pairs": sum(delta < 0 for delta in deltas),
    }
    if len(deltas) < 2:
        summary["paired_statistics"] = {
            "available": False,
            "reason": "at least two completed pairs are required",
        }
        return summary

    delta_stddev = statistics.stdev(deltas)
    summary["candidate_minus_baseline_similarity_stddev"] = delta_stddev
    try:
        from scipy import stats

        standard_error = delta_stddev / len(deltas) ** 0.5
        critical_value = float(stats.t.ppf(0.975, len(deltas) - 1))
        paired_t = stats.ttest_1samp(deltas, popmean=0.0)
        wilcoxon = stats.wilcoxon(deltas, alternative="two-sided")
        inferential_values = (
            critical_value,
            float(paired_t.statistic),
            float(paired_t.pvalue),
            float(wilcoxon.statistic),
            float(wilcoxon.pvalue),
        )
        if not all(math.isfinite(value) for value in inferential_values):
            raise ValueError("non-finite paired-statistics result")
        summary["paired_statistics"] = {
            "available": True,
            "delta_definition": "candidate_similarity - baseline_similarity",
            "mean_delta_ci95": {
                "method": "two-sided paired t interval",
                "confidence": 0.95,
                "degrees_of_freedom": len(deltas) - 1,
                "lower": delta_mean - critical_value * standard_error,
                "upper": delta_mean + critical_value * standard_error,
            },
            "paired_t_test": {
                "method": "one-sample t-test on paired deltas",
                "null_mean_delta": 0.0,
                "alternative": "two-sided",
                "statistic": float(paired_t.statistic),
                "pvalue": float(paired_t.pvalue),
            },
            "wilcoxon_signed_rank_test": {
                "method": "Wilcoxon signed-rank test on paired deltas",
                "null_median_delta": 0.0,
                "alternative": "two-sided",
                "statistic": float(wilcoxon.statistic),
                "pvalue": float(wilcoxon.pvalue),
            },
        }
    except Exception as error:
        # scipy is optional: raw per-pair scores and the primary summary remain
        # valid even when inferential statistics cannot be calculated.
        summary["paired_statistics"] = {
            "available": False,
            "reason": f"{type(error).__name__}: {error}",
            "fallback": (
                "Per-pair deltas, mean delta, and sample standard deviation "
                "remain available; install scipy to reproduce CI and tests."
            ),
        }
    return summary


def main() -> int:
    args = parse_args()
    meta_path = args.dataset_root / "en" / "meta.lst"
    for path in (args.checkpoint, meta_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    rows = load_rows(meta_path, args.seed, args.num_prompts)
    end_index = args.num_prompts if args.end_index is None else args.end_index
    if not 0 <= args.start_index < end_index <= args.num_prompts:
        raise ValueError(
            "require 0 <= start-index < end-index <= num-prompts, got "
            f"{args.start_index}, {end_index}, {args.num_prompts}"
        )
    indexed_rows = list(enumerate(rows))[args.start_index:end_index]
    selected_indices = {index for index, _ in indexed_rows}
    input_manifest = build_input_manifest(
        indexed_rows,
        args.dataset_root,
        args.baseline_wav_dir,
        args.candidate_wav_dir,
    )

    torch.set_num_threads(max(1, args.threads))
    torch.set_num_interop_threads(1)
    checkpoint_sha256 = verify_sha256(
        args.checkpoint,
        EXPECTED_CHECKPOINT_SHA256,
        "released WavLM checkpoint",
    )
    meta_sha256 = sha256_file(meta_path)
    verified_sources: dict[str, dict[str, str]] = {}
    for name, path in source_paths(
        args.seed_tts_eval_root, args.s3prl_root
    ).items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = verify_sha256(path, EXPECTED_SOURCE_SHA256[name], name)
        verified_sources[name] = {
            "path": str(path.resolve()),
            "sha256": actual,
        }

    run_descriptor = {
        "protocol": "seed-tts-wavlm-large-cpu-paired-proxy-v2",
        "checkpoint_sha256": checkpoint_sha256,
        "dataset_meta_sha256": meta_sha256,
        "verified_sources": verified_sources,
        "seed": args.seed,
        "num_prompts": args.num_prompts,
        "start_index": args.start_index,
        "end_index": end_index,
        "input_manifest": input_manifest,
    }
    run_fingerprint = fingerprint_payload(run_descriptor)
    print("Building WavLM-large + ECAPA on CPU", flush=True)
    model, load_report = build_model(
        args.checkpoint, args.seed_tts_eval_root, args.s3prl_root
    )
    print(f"Model loaded: {load_report}", flush=True)

    progress_path = args.output.with_suffix(args.output.suffix + ".progress")
    manifest_by_index = {int(entry["index"]): entry for entry in input_manifest}
    items_by_index: dict[int, dict[str, Any]] = {}
    if progress_path.is_file():
        previous = json.loads(progress_path.read_text(encoding="utf-8"))
        if previous.get("run_fingerprint") != run_fingerprint:
            raise RuntimeError(
                f"refusing stale progress with a different or missing run "
                f"fingerprint: {progress_path}"
            )
        for item in previous.get("items", []):
            index = int(item["index"])
            if index not in selected_indices or index in items_by_index:
                raise RuntimeError(f"invalid or duplicate progress index: {index}")
            expected_entry = manifest_by_index[index]
            for key, expected_value in expected_entry.items():
                if item.get(key) != expected_value:
                    raise RuntimeError(
                        f"progress item {index} does not match input manifest field {key}"
                    )
            items_by_index[index] = item
        print(f"Resuming with {len(items_by_index)} completed pairs", flush=True)

    prompt_embeddings: dict[str, torch.Tensor] = {}
    for index, row in indexed_rows:
        if index in items_by_index and not items_by_index[index].get("error"):
            continue
        prompt_path = args.dataset_root / "en" / row["prompt_wav"]
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
        item: dict[str, Any] = dict(manifest_by_index[index])
        try:
            prompt_key = str(prompt_path.resolve())
            if prompt_key not in prompt_embeddings:
                prompt_embeddings[prompt_key] = embedding(model, prompt_path)
            prompt_embedding = prompt_embeddings[prompt_key]
            baseline_similarity = cosine_similarity(
                embedding(model, baseline_path), prompt_embedding
            )
            candidate_similarity = cosine_similarity(
                embedding(model, candidate_path), prompt_embedding
            )
            item.update(
                {
                    "baseline_similarity": baseline_similarity,
                    "candidate_similarity": candidate_similarity,
                    "candidate_minus_baseline_similarity": (
                        candidate_similarity - baseline_similarity
                    ),
                }
            )
        except Exception as error:  # Preserve progress if one WAV is malformed.
            item["error"] = f"{type(error).__name__}: {error}"
        items_by_index[index] = item
        ordered = [items_by_index[i] for i in sorted(items_by_index)]
        write_json(
            progress_path,
            {
                "protocol": "seed-tts-wavlm-large-cpu-paired-proxy-v2",
                "official_protocol": False,
                "run_fingerprint": run_fingerprint,
                "run_descriptor": run_descriptor,
                "checkpoint_sha256": checkpoint_sha256,
                "items": ordered,
                "summary": summarize(ordered, len(selected_indices)),
            },
        )

    items = [items_by_index[i] for i in sorted(selected_indices)]
    payload = {
        "protocol": "seed-tts-wavlm-large-cpu-paired-proxy-v2",
        "official_protocol": False,
        "note": (
            "Uses seed-tts-eval WavLM-large + ECAPA weights on CPU. The "
            "upstream cal_sim.sh is CUDA-only and the competition evaluator "
            "may differ, so this is a paired proxy rather than official ASV."
        ),
        "seed_tts_eval_commit": SEED_TTS_EVAL_COMMIT,
        "s3prl_commit": S3PRL_COMMIT,
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "expected_checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
        "dataset_meta": str(meta_path),
        "dataset_meta_sha256": meta_sha256,
        "verified_sources": verified_sources,
        "run_fingerprint": run_fingerprint,
        "run_descriptor": run_descriptor,
        "environment": environment_versions(),
        "model_load_report": load_report,
        "device": "cpu",
        "threads": args.threads,
        "seed": args.seed,
        "num_prompts": args.num_prompts,
        "start_index": args.start_index,
        "end_index": end_index,
        "summary": summarize(items, len(selected_indices)),
        "items": items,
    }
    write_json(args.output, payload)
    print(json.dumps(payload["summary"], indent=2, allow_nan=False), flush=True)
    return 0 if payload["summary"]["quality_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
