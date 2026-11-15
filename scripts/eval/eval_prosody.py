"""Prosody statistics of rendered clips: F0 std / range (semitones) and duration per clip.

Usage: uv run python scripts/eval/eval_prosody.py --set eval/sets/heldout.jsonl --dirs NAME=DIR [NAME=DIR ...] [--n 30]
Speech that sounds flat has a smaller F0 std/range than the reference recordings.
"""

import argparse
import json
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


def clip_stats(path: Path) -> tuple[float, float, float] | None:
    y, sr = sf.read(path, dtype="float32")
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = librosa.resample(y, orig_sr=sr, target_sr=16000)
    f0, voiced, _ = librosa.pyin(y, fmin=70, fmax=400, sr=16000, frame_length=1024, hop_length=160)
    f = f0[voiced & ~np.isnan(f0)]
    if len(f) < 10:
        return None
    st = 12 * np.log2(f / np.median(f))
    return float(np.std(st)), float(np.percentile(st, 95) - np.percentile(st, 5)), len(y) / 16000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--dirs", nargs="+", required=True, help="NAME=DIR")
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    ids = [json.loads(x)["id"] for x in a.set.read_text(encoding="utf-8").splitlines() if x][: a.n]
    out = {}
    for spec in a.dirs:
        name, d = spec.split("=", 1)
        rows = np.array([r for r in (clip_stats(Path(d) / f"{i}.wav") for i in ids) if r])
        out[name] = {"f0_std_st": rows[:, 0].mean(), "f0_range_st": rows[:, 1].mean(), "dur_s": rows[:, 2].mean()}
        print(f"{name:34s} F0 std {rows[:,0].mean():.2f} st | range {rows[:,1].mean():.2f} st | mean dur {rows[:,2].mean():.2f} s")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
