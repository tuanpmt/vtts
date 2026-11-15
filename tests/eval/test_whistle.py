import numpy as np

from vtts.eval.whistle import whistle_score


def test_whistle_detects_tone():
    sr = 22050
    rng = np.random.default_rng(0)
    noise = (0.1 * rng.standard_normal(2 * sr)).astype(np.float32)
    t = np.arange(2 * sr) / sr
    tone = (0.14 * np.sin(2 * np.pi * 4000 * t)).astype(np.float32)  # ~28 dB above per-bin noise
    assert whistle_score(noise, sr) < 5
    assert whistle_score(noise + tone, sr) > 50
