"""Frame-level prosody targets from teacher audio: log-F0 (interpolated through unvoiced
frames), voicing flag and log energy, on the student's hop-256 frame grid."""

from __future__ import annotations

import numpy as np

SR, HOP = 22050, 256
F0_FLOOR, F0_CEIL = 60.0, 500.0


def frame_prosody(audio_int16: np.ndarray, n_frames: int, sr: int = SR,
                  hop: int = HOP) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import pyworld

    x = audio_int16.astype(np.float64) / 32768.0
    period_ms = 1000.0 * hop / sr
    f0, t = pyworld.dio(x, sr, f0_floor=F0_FLOOR, f0_ceil=F0_CEIL, frame_period=period_ms)
    f0 = pyworld.stonemask(x, f0, t, sr)
    # align to the student grid: frame i covers samples [i*hop, (i+1)*hop)
    centers = (np.arange(n_frames) + 0.5) * hop / sr
    idx = np.clip(np.round(centers / (period_ms / 1000.0)).astype(int), 0, len(f0) - 1)
    f = f0[idx]
    vuv = (f > 0).astype(np.float32)
    lf0 = np.zeros(n_frames, np.float32)
    if vuv.any():
        voiced = np.flatnonzero(vuv)
        lf0 = np.interp(np.arange(n_frames), voiced, np.log(f[voiced])).astype(np.float32)
    else:
        lf0[:] = np.log(150.0)
    frames = np.zeros((n_frames, hop), np.float64)
    n = min(len(x) // hop, n_frames)
    frames[:n] = x[: n * hop].reshape(n, hop)
    energy = np.log(np.sqrt((frames ** 2).mean(axis=1)) + 1e-5).astype(np.float32)
    return lf0, vuv, energy
