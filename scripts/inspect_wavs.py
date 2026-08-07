#!/usr/bin/env python3
"""Validate generated PCM WAV files and print recording-friendly summaries."""

from __future__ import annotations

import argparse
import hashlib
import wave
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    paths = sorted(args.directory.glob("*.wav"))
    if not paths:
        raise FileNotFoundError(f"no WAV files in {args.directory}")

    total_duration = 0.0
    for path in paths:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_rate = handle.getframerate()
            frames = handle.getnframes()
            sample_width = handle.getsampwidth()
        if channels != 1 or sample_rate != 24000 or frames <= 0:
            raise ValueError(
                f"unexpected WAV format: {path}: channels={channels}, "
                f"sample_rate={sample_rate}, frames={frames}"
            )
        duration = frames / sample_rate
        total_duration += duration
        print(
            f"WAV_OK path={path} duration_s={duration:.3f} rate={sample_rate} "
            f"channels={channels} sample_width={sample_width} "
            f"sha256={sha256_file(path)}"
        )
    print(f"WAV_SUMMARY files={len(paths)} total_duration_s={total_duration:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

