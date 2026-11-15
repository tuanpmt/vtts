from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

pytestmark = pytest.mark.slow

SAMPLE = Path(__file__).parents[1] / "fixtures" / "sample_vi.wav"


def test_asr_transcribes_sample():
    from vtts.eval.asr import AsrTranscriber

    out = AsrTranscriber().transcribe([SAMPLE])
    assert len(out) == 1 and out[0].strip()


def test_dnsmos_range():
    from vtts.eval.mos import dnsmos

    x, sr = sf.read(SAMPLE, dtype="float32")
    scores = dnsmos(x, sr)
    assert set(scores) == {"sig", "bak", "ovrl"}
    assert all(1.0 <= v <= 5.0 for v in scores.values())


def test_utmos_range():
    from vtts.eval.mos import utmos

    x, sr = sf.read(SAMPLE, dtype="float32")
    assert 1.0 <= utmos(x, sr) <= 5.0
    assert np.isfinite(utmos(x, sr))
