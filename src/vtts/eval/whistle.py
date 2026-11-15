"""Whistle score: density of long, narrow, stationary tonal ridges in 2-8 kHz.

A cell (bin, frame) is tonal when it is >= 15 dB above the median of its +-20
neighbouring bins in the same frame. Cells that belong to a run of >= 8
consecutive tonal frames in the same bin are counted; the score is that count
per second of audio. Clean speech scores low; the "radio tuning" whistle of
an under-trained decoder scores high.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import median_filter

N_FFT, HOP = 2048, 256
LO_HZ, HI_HZ = 2000.0, 8000.0
NEIGHBOURS, THRESH_DB, MIN_RUN = 20, 15.0, 8


def whistle_score(x: np.ndarray, sr: int) -> float:
    x = np.asarray(x, dtype=np.float64)
    if len(x) < N_FFT:
        return 0.0
    win = np.hanning(N_FFT)
    n = 1 + (len(x) - N_FFT) // HOP
    frames = np.stack([x[i * HOP: i * HOP + N_FFT] * win for i in range(n)])
    db = 20 * np.log10(np.abs(np.fft.rfft(frames, axis=1)) + 1e-9)  # [frames, bins]
    freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
    local = median_filter(db, size=(1, 2 * NEIGHBOURS + 1), mode="nearest")
    band = (freqs >= LO_HZ) & (freqs <= HI_HZ)
    tonal = ((db - local) >= THRESH_DB)[:, band]
    count = 0
    for col in tonal.T:
        run = 0
        for v in np.append(col, False):
            if v:
                run += 1
            else:
                if run >= MIN_RUN:
                    count += run
                run = 0
    return count / (len(x) / sr)
