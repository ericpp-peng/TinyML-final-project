#!/usr/bin/env python3
"""Prepare personal hard-negative clips for Speech Commands training."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from pathlib import Path


MAX_NUM_WAVS_PER_CLASS = 2**27 - 1


def which_set(filename: str, validation_percentage: int = 10, testing_percentage: int = 10) -> str:
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


def name_for_set(prefix: str, index: int, target_set: str) -> str:
    candidate = index
    while True:
        name = f"{prefix}_{candidate:04d}.wav"
        if which_set(name) == target_set:
            return name
        candidate += 10000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recorded-root", default="recorded_audio")
    parser.add_argument("--dataset-root", default="dataset")
    parser.add_argument("--label", default="hard_negative")
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--latest", action="store_true", help="Use the latest clips instead of the earliest clips.")
    args = parser.parse_args()

    source_dir = Path(args.recorded_root) / args.label
    target_dir = Path(args.dataset_root) / args.label
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    for path in target_dir.glob("eric_hard_negative_*.wav"):
        path.unlink()

    all_sources = sorted(source_dir.glob("*.wav"))
    sources = all_sources[-args.count :] if args.latest else all_sources[: args.count]
    if len(sources) != args.count:
        raise RuntimeError(f"Expected {args.count} clips, found {len(sources)} in {source_dir}")

    split_plan = (["training"] * 32) + (["validation"] * 4) + (["testing"] * 4)
    if len(split_plan) != args.count:
        raise ValueError("The current split plan expects exactly 40 clips")

    counts = {"training": 0, "validation": 0, "testing": 0}
    for index, (source, target_set) in enumerate(zip(sources, split_plan), start=1):
        counts[target_set] += 1
        target_name = name_for_set("eric_hard_negative", index, target_set)
        shutil.copy2(source, target_dir / target_name)

    print(f"Copied {len(sources)} {args.label} clips into {target_dir}")
    print("Split:", counts)
    print("First source:", sources[0])
    print("Last source:", sources[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
