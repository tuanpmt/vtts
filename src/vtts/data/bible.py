"""Convert the VietBibleVox release (one zip of NAME.mp3 + NAME.txt pairs, single male narrator,
from the open.bible Vietnamese audio Bible, CC BY-SA 4.0) into 22.05 kHz wavs + metadata.csv.

The zip may be a local path or an https URL (read with HTTP range requests via `remotezip`,
so the 9 GB archive never has to be stored).
"""

from __future__ import annotations

import io
import re
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

from .audio import normalize_loudness, resample, trim_silence
from .infore import SAMPLE_RATE, PrepareReport


def clean_bible_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("|", " ")).strip()


def _open(src: str | Path):
    s = str(src)
    if s.startswith(("http://", "https://")):
        from remotezip import RemoteZip

        return RemoteZip(s)
    return zipfile.ZipFile(s)


def _decode(data: bytes) -> tuple[np.ndarray, int]:
    try:
        x, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
        return x.mean(axis=1), sr
    except Exception:  # noqa: BLE001 - libsndfile without mp3 support: fall back to audioread
        import librosa

        x, sr = librosa.load(io.BytesIO(data), sr=None, mono=True)
        return x.astype(np.float32), sr


def _work(args: tuple[str, list[str], str]) -> tuple[list[tuple[str, str, float]], list[tuple[str, str]]]:
    src, names, out = args
    wav_dir = Path(out) / "wavs"
    rows, skipped = [], []
    with _open(src) as z:
        for name in names:
            text = clean_bible_text(z.read(f"{name}.txt").decode("utf-8", "replace"))
            if not text:
                skipped.append((name, "empty_transcript"))
                continue
            try:
                x, sr = _decode(z.read(f"{name}.mp3"))
                y = normalize_loudness(trim_silence(resample(x, sr, SAMPLE_RATE), SAMPLE_RATE))
            except Exception:  # noqa: BLE001 - any decoder failure means a bad item
                y = np.zeros(0, np.float32)
            if len(y) == 0:
                skipped.append((name, "bad_audio"))
                continue
            uid = f"bible_{name}"
            sf.write(wav_dir / f"{uid}.wav", y, SAMPLE_RATE, subtype="PCM_16")
            rows.append((uid, text, len(y) / SAMPLE_RATE))
    return rows, skipped


def prepare_bible(src: str | Path, out_dir: Path, workers: int = 8,
                  limit: int | None = None) -> PrepareReport:
    out_dir = Path(out_dir)
    (out_dir / "wavs").mkdir(parents=True, exist_ok=True)
    with _open(src) as z:
        names = sorted(n[:-4] for n in z.namelist() if n.endswith(".mp3"))
    if limit is not None:
        names = names[:limit]
    shards = [names[i::workers] for i in range(workers)]
    rows, skipped = [], []
    with ProcessPoolExecutor(workers) as ex:
        for r, s in ex.map(_work, [(str(src), sh, str(out_dir)) for sh in shards if sh]):
            rows += r
            skipped += s
    rows.sort()
    (out_dir / "metadata.csv").write_text(
        "".join(f"{u}|{t}|{d:.3f}\n" for u, t, d in rows), encoding="utf-8")
    return PrepareReport(n_in=len(names), n_out=len(rows),
                         hours=sum(d for *_, d in rows) / 3600, skipped=sorted(skipped))
