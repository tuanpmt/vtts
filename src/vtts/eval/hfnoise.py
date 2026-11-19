"""High-band noise metrics: the broadband 5-10 kHz "buzz" layer of the students.

The clip is cut into non-overlapping 250 ms windows. A window counts when it is voiced (at
least VOICED_SHARE of its STFT frames are periodic) and not near-silent. In each counted window:

- flatness: mean over frames of the spectral flatness (geometric / arithmetic mean of the power)
  of the bins in [lo_hz, hi_hz]. 1 = white noise, near 0 = a few strong partials. In voiced
  speech the 5-10 kHz band is mostly aspiration with some harmonic structure; a noise layer
  raises its flatness.
- hf_ratio_db: 10 log10(power in [lo_hz, hi_hz] / total power) over the window. A noise layer
  raises it.

Voicing per frame: the peak of the normalized autocorrelation (of the band below 1.5 kHz,
corrected for the window's own autocorrelation) at lags of 60-500 Hz is >= VOICING_THRESHOLD.
"""

from __future__ import annotations

import numpy as np

N_FFT, HOP = 1024, 256
WINDOW_S = 0.25
LO_HZ, HI_HZ = 5000.0, 10000.0
F0_MIN, F0_MAX = 60.0, 500.0
VOICING_LP_HZ = 1500.0
VOICING_THRESHOLD = 0.5
VOICED_SHARE = 0.5
SILENCE_DB = -45.0  # window power relative to the loudest window of the clip


def _frames_power(x: np.ndarray) -> np.ndarray:
    win = np.hanning(N_FFT)
    n = 1 + (len(x) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    return np.abs(np.fft.rfft(x[idx] * win, axis=1)) ** 2  # [frames, bins]


def _voiced(power: np.ndarray, sr: int) -> np.ndarray:
    freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
    lp = np.where(freqs <= VOICING_LP_HZ, power, 0.0)
    r = np.fft.irfft(lp, n=N_FFT, axis=1)
    w = np.fft.irfft(np.abs(np.fft.rfft(np.hanning(N_FFT))) ** 2, n=N_FFT)
    lo, hi = int(sr / F0_MAX), min(int(sr / F0_MIN), N_FFT // 2)
    norm = r[:, lo:hi] / np.maximum(r[:, :1], 1e-12) / (w[lo:hi] / w[0])
    return norm.max(axis=1) >= VOICING_THRESHOLD


def hf_noise(x: np.ndarray, sr: int, lo_hz: float = LO_HZ, hi_hz: float = HI_HZ) -> dict:
    """Per-window metrics of one clip: {"flatness": [...], "hf_ratio_db": [...]} over the
    counted windows (empty lists when none), plus "windows" (all windows) for reference."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if len(x) < N_FFT:
        return {"flatness": [], "hf_ratio_db": [], "windows": 0}
    p = _frames_power(x)
    voiced = _voiced(p, sr)
    freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
    band = (freqs >= lo_hz) & (freqs <= min(hi_hz, sr / 2))
    per_win = max(1, round(WINDOW_S * sr / HOP))
    n_win = len(p) // per_win
    if n_win == 0:
        return {"flatness": [], "hf_ratio_db": [], "windows": 0}
    pw = p[: n_win * per_win].reshape(n_win, per_win, -1)
    total = pw.sum(axis=(1, 2))
    loud = 10 * np.log10(total / max(total.max(), 1e-20) + 1e-20) > SILENCE_DB
    vshare = voiced[: n_win * per_win].reshape(n_win, per_win).mean(axis=1)
    keep = loud & (vshare >= VOICED_SHARE)
    pb = pw[:, :, band] + 1e-12
    flat = (np.exp(np.log(pb).mean(axis=2)) / pb.mean(axis=2)).mean(axis=1)
    ratio = 10 * np.log10(pb.sum(axis=(1, 2)) / np.maximum(total, 1e-20))
    return {"flatness": flat[keep].tolist(), "hf_ratio_db": ratio[keep].tolist(),
            "windows": int(n_win)}


def summarize(clips: dict[str, dict]) -> dict:
    """Pool the counted windows of many clips: mean / median of both metrics."""
    fl = np.array([v for c in clips.values() for v in c["flatness"]])
    hr = np.array([v for c in clips.values() for v in c["hf_ratio_db"]])
    if len(fl) == 0:
        return {"voiced_windows": 0, "flatness_mean": None, "flatness_median": None,
                "hf_ratio_db_mean": None, "hf_ratio_db_median": None}
    return {"voiced_windows": len(fl),
            "flatness_mean": float(fl.mean()), "flatness_median": float(np.median(fl)),
            "hf_ratio_db_mean": float(hr.mean()), "hf_ratio_db_median": float(np.median(hr))}
