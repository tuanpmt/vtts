import numpy as np

from vtts.data.audio import normalize_loudness, resample, trim_silence


def _sine(freq, sr, seconds, amp=0.5):
    t = np.arange(int(sr * seconds)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_resample_44100_to_22050():
    y = resample(_sine(1000, 44100, 1.0), 44100, 22050)
    assert abs(len(y) - 22050) <= 1
    spec = np.abs(np.fft.rfft(y))
    peak = np.fft.rfftfreq(len(y), 1 / 22050)[spec.argmax()]
    assert abs(peak - 1000) <= 5


def test_trim_silence():
    sr = 22050
    x = np.concatenate([np.zeros(sr // 2), _sine(440, sr, 1.0), np.zeros(sr // 2)]).astype(np.float32)
    y = trim_silence(x, sr)
    assert abs(len(y) / sr - 1.1) <= 0.05


def test_loudness():
    y = normalize_loudness(_sine(440, 22050, 1.0, amp=0.01))
    rms_db = 20 * np.log10(np.sqrt(np.mean(y**2)))
    peak_db = 20 * np.log10(np.abs(y).max())
    assert abs(rms_db + 23) <= 0.5
    assert peak_db <= -1.0 + 1e-6


def test_loudness_peak_cap_wins():
    x = np.zeros(22050, dtype=np.float32)
    x[100] = 1.0  # one click: reaching -23 dB RMS would clip
    y = normalize_loudness(x)
    assert 20 * np.log10(np.abs(y).max()) <= -1.0 + 1e-6
