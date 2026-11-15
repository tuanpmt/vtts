"""Small audio utilities: resampling, silence trim, loudness normalization."""

from __future__ import annotations

from math import gcd

import numpy as np
from scipy.signal import resample_poly


def resample(x: np.ndarray, sr_in: int, sr_out: int = 22050) -> np.ndarray:
    if sr_in == sr_out:
        return x.astype(np.float32, copy=False)
    g = gcd(sr_in, sr_out)
    return resample_poly(x, sr_out // g, sr_in // g).astype(np.float32)


def trim_silence(x: np.ndarray, sr: int, top_db: float = 40.0, pad_ms: float = 50.0) -> np.ndarray:
    win, hop = int(0.025 * sr), int(0.010 * sr)
    if len(x) < win:
        return x
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    rms = np.sqrt(np.mean(x[idx].astype(np.float64) ** 2, axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-10))
    keep = np.flatnonzero(db >= db.max() - top_db)
    pad = int(pad_ms / 1000 * sr)
    start = max(0, keep[0] * hop - pad)
    end = min(len(x), keep[-1] * hop + win + pad)
    return x[start:end]


def normalize_loudness(x: np.ndarray, target_rms_db: float = -23.0,
                       peak_db: float = -1.0) -> np.ndarray:
    x = x.astype(np.float32)
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    peak = float(np.abs(x).max())
    if rms == 0.0 or peak == 0.0:
        return x
    gain = min(10 ** (target_rms_db / 20) / rms, 10 ** (peak_db / 20) / peak)
    return (x * gain).astype(np.float32)
