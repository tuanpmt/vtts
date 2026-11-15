"""Convert the InfoRe1 parquet release into 22.05 kHz wavs + metadata.csv."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf

from .audio import normalize_loudness, resample, trim_silence

SAMPLE_RATE = 22050


@dataclass
class PrepareReport:
    n_in: int = 0
    n_out: int = 0
    hours: float = 0.0
    skipped: list[tuple[int, str]] = field(default_factory=list)


def _decode(audio: dict) -> tuple[np.ndarray, int]:
    x, sr = sf.read(io.BytesIO(audio["bytes"]), dtype="float32", always_2d=True)
    return x.mean(axis=1), sr


def prepare_infore(parquet_dir: Path, out_dir: Path) -> PrepareReport:
    wav_dir = out_dir / "wavs"
    wav_dir.mkdir(parents=True, exist_ok=True)
    report = PrepareReport()
    seconds = 0.0
    rows = []
    index = 0
    for path in sorted(Path(parquet_dir).rglob("*.parquet")):
        for batch in pq.ParquetFile(path).iter_batches(batch_size=256):
            for audio, text in zip(batch.column("audio").to_pylist(),
                                   batch.column("transcription").to_pylist()):
                i, index = index, index + 1
                text = (text or "").strip().replace("|", " ")
                if not text:
                    report.skipped.append((i, "empty_transcript"))
                    continue
                try:
                    x, sr = _decode(audio)
                except Exception:  # noqa: BLE001 - any decoder failure means a bad row
                    report.skipped.append((i, "bad_audio"))
                    continue
                y = normalize_loudness(trim_silence(resample(x, sr, SAMPLE_RATE), SAMPLE_RATE))
                if len(y) == 0:
                    report.skipped.append((i, "bad_audio"))
                    continue
                uid = f"infore_{i:05d}"
                sf.write(wav_dir / f"{uid}.wav", y, SAMPLE_RATE, subtype="PCM_16")
                dur = len(y) / SAMPLE_RATE
                seconds += dur
                rows.append(f"{uid}|{text}|{dur:.3f}")
    (out_dir / "metadata.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    report.n_in, report.n_out, report.hours = index, len(rows), seconds / 3600
    return report
