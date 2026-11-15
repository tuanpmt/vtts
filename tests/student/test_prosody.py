import numpy as np

from vtts.student.prosody import frame_prosody


def _tone(f0_hz, seconds=1.0, sr=22050):
    t = np.arange(int(sr * seconds)) / sr
    return (0.3 * np.sin(2 * np.pi * f0_hz * t) * 32767).astype(np.int16)


def test_pitch_of_a_tone():
    audio = _tone(200.0)
    n = len(audio) // 256
    lf0, vuv, energy = frame_prosody(audio, n)
    assert lf0.shape == vuv.shape == energy.shape == (n,)
    mid = slice(n // 4, 3 * n // 4)
    assert vuv[mid].mean() > 0.9
    assert np.allclose(np.exp(lf0[mid]), 200.0, rtol=0.03)


def test_silence_is_unvoiced_and_quiet():
    audio = np.zeros(22050, np.int16)
    n = len(audio) // 256
    lf0, vuv, energy = frame_prosody(audio, n)
    assert vuv.max() == 0
    assert np.all(np.isfinite(lf0)) and np.all(np.isfinite(energy))
    assert energy.max() < -10


def test_unvoiced_frames_are_interpolated():
    audio = np.concatenate([_tone(150.0, 0.5), np.zeros(5512, np.int16), _tone(250.0, 0.5)])
    n = len(audio) // 256
    lf0, vuv, _ = frame_prosody(audio, n)
    gap = (vuv == 0)
    assert gap.any()
    lo, hi = np.log(150.0), np.log(250.0)
    assert np.all(lf0[gap] >= lo - 0.1) and np.all(lf0[gap] <= hi + 0.1)
