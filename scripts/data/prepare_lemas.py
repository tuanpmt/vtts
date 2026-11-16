"""Convert a LEMAS pick (from select_lemas.py) into 22.05 kHz wavs + train.csv for the teacher.

Audio gets the same resample / silence trim / loudness normalisation as the Bible corpus.

Usage: uv run python scripts/data/prepare_lemas.py --pick pick.tsv --mp3-root data/lemas/pick \
       --out data/lemas [--workers 8]
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import librosa
import soundfile as sf

from vtts.data.audio import normalize_loudness, trim_silence

SR = 22050


def convert(job: tuple[str, str, str, str]) -> tuple[str, str, float] | None:
    key, src, dst, text = job
    try:
        x, _ = librosa.load(src, sr=SR, mono=True)
        y = normalize_loudness(trim_silence(x, SR))
    except Exception:  # noqa: BLE001 -- skip clips the decoder cannot read
        return None
    if len(y) < SR:
        return None
    sf.write(dst, y, SR, subtype="PCM_16")
    return key, text, len(y) / SR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", type=Path, required=True)
    ap.add_argument("--mp3-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    wavs = a.out / "wavs"
    wavs.mkdir(parents=True, exist_ok=True)
    jobs = []
    for ln in a.pick.open(encoding="utf-8"):
        key, audio, _, text = ln.rstrip("\n").split("\t")
        jobs.append((key, str(a.mp3_root / audio), str(wavs / f"{key}.wav"), text))
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(convert, jobs, chunksize=64):
            if r is not None:
                rows.append(r)
    (a.out / "pre").mkdir(exist_ok=True)
    with (a.out / "pre" / "train.csv").open("w", encoding="utf-8") as o:
        for key, text, dur in rows:
            o.write(f"{key}|{text}|{dur:.3f}\n")
    print(f"{len(rows)}/{len(jobs)} clips, {sum(r[2] for r in rows) / 3600:.1f} h")


if __name__ == "__main__":
    main()
