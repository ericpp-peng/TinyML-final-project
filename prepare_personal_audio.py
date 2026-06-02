#!/usr/bin/env python3
"""Copy locally recorded Nano audio clips into Speech Commands dataset folders."""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import shutil
import struct
import wave
from pathlib import Path


MAX_NUM_WAVS_PER_CLASS = 2**27 - 1


def which_set(filename: str, validation_percentage: int, testing_percentage: int) -> str:
    base_name = Path(filename).name
    hash_name = re.sub(r"_nohash_.*$", "", base_name)
    percentage_hash = (
        (int(hashlib.sha1(hash_name.encode("utf-8")).hexdigest(), 16) % (MAX_NUM_WAVS_PER_CLASS + 1))
        * (100.0 / MAX_NUM_WAVS_PER_CLASS)
    )
    if percentage_hash < validation_percentage:
        return "validation"
    if percentage_hash < testing_percentage + validation_percentage:
        return "testing"
    return "training"


def wav_stats(path: Path) -> tuple[int, float]:
    with wave.open(str(path), "rb") as wav:
        frames = wav.readframes(wav.getnframes())
    if not frames:
        return 0, 0.0
    samples = struct.unpack("<" + "h" * (len(frames) // 2), frames)
    peak = max(abs(sample) for sample in samples)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    return peak, rms


def training_name(prefix: str, index: int, suffix: str = ".wav") -> str:
    candidate_index = index
    while True:
        name = f"{prefix}_{candidate_index:04d}{suffix}"
        if which_set(name, 10, 10) == "training":
            return name
        candidate_index += 10000


def clean_existing(directory: Path, pattern: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.glob(pattern):
        path.unlink()


def copy_stop(recorded_root: Path, dataset_root: Path, min_peak: int, min_rms: float) -> tuple[int, int]:
    source_dir = recorded_root / "stop"
    target_dir = dataset_root / "stop"
    clean_existing(target_dir, "eric_stop_*.wav")

    copied = 0
    skipped = 0
    for source in sorted(source_dir.glob("*.wav")):
        peak, rms = wav_stats(source)
        if peak < min_peak or rms < min_rms:
            skipped += 1
            continue
        copied += 1
        target_name = training_name("eric_stop", copied)
        shutil.copy2(source, target_dir / target_name)
    return copied, skipped


def copy_unknown(recorded_root: Path, dataset_root: Path) -> int:
    source_dir = recorded_root / "unknown"
    target_dir = dataset_root / "eric_unknown"
    clean_existing(target_dir, "eric_unknown_*.wav")

    copied = 0
    for source in sorted(source_dir.glob("*.wav")):
        copied += 1
        target_name = training_name("eric_unknown", copied)
        shutil.copy2(source, target_dir / target_name)
    return copied


def copy_background(recorded_root: Path, dataset_root: Path) -> int:
    source_dir = recorded_root / "_background_noise_"
    target_dir = dataset_root / "_background_noise_"
    clean_existing(target_dir, "eric_background_*.wav")

    sources = sorted(source_dir.glob("*.wav"))
    if not sources:
        return 0

    output_path = target_dir / "eric_background_combined.wav"
    pcm_chunks = []
    params = None
    for source in sources:
        with wave.open(str(source), "rb") as wav:
            current_params = wav.getparams()
            if params is None:
                params = current_params
            elif current_params[:3] != params[:3]:
                raise ValueError(f"Background WAV format mismatch: {source}")
            pcm_chunks.append(wav.readframes(wav.getnframes()))

    with wave.open(str(output_path), "wb") as wav:
        wav.setparams(params)
        for chunk in pcm_chunks:
            wav.writeframes(chunk)

    copied = len(sources)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recorded-root", default="recorded_audio")
    parser.add_argument("--dataset-root", default="dataset")
    parser.add_argument("--min-stop-peak", type=int, default=300)
    parser.add_argument("--min-stop-rms", type=float, default=50.0)
    args = parser.parse_args()

    recorded_root = Path(args.recorded_root)
    dataset_root = Path(args.dataset_root)

    stop_copied, stop_skipped = copy_stop(
        recorded_root, dataset_root, args.min_stop_peak, args.min_stop_rms
    )
    unknown_copied = copy_unknown(recorded_root, dataset_root)
    background_copied = copy_background(recorded_root, dataset_root)

    print(f"Copied stop clips: {stop_copied} (skipped quiet clips: {stop_skipped})")
    print(f"Copied unknown clips: {unknown_copied}")
    print(f"Copied background clips: {background_copied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
