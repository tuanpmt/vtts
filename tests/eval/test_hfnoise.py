import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from vtts.eval.hfnoise import hf_noise, summarize

SR = 22050
ROOT = Path(__file__).resolve().parents[2]


def _voice(seconds: float = 2.0, f0: float = 150.0) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    ph = 2 * np.pi * np.cumsum(f0 * (1 + 0.05 * np.sin(2 * np.pi * 1.5 * t))) / SR
    return 0.3 * sum(np.sin(k * ph) / k for k in range(1, 70) if k * f0 < 8000)


def _band_noise(n: int, lo: float, hi: float) -> np.ndarray:
    spec = np.fft.rfft(np.random.default_rng(0).standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / np.sqrt((x ** 2).mean())


def test_noise_layer_raises_flatness_and_hf_ratio():
    v = _voice()
    clean = summarize({"a": hf_noise(v, SR)})
    noisy = summarize({"a": hf_noise(v + 0.02 * _band_noise(len(v), 5000, 10000), SR)})
    assert clean["voiced_windows"] == noisy["voiced_windows"] == 7  # 169 frames // 22 per window
    assert clean["flatness_mean"] < 0.05 and noisy["flatness_mean"] > 0.3
    assert noisy["hf_ratio_db_mean"] > clean["hf_ratio_db_mean"] + 2


def test_unvoiced_and_silent_windows_are_skipped():
    n = SR * 2
    assert hf_noise(np.zeros(n), SR)["flatness"] == []
    assert hf_noise(0.3 * np.random.default_rng(1).standard_normal(n), SR)["flatness"] == []
    assert summarize({"a": hf_noise(np.zeros(n), SR)})["flatness_mean"] is None
    assert hf_noise(np.zeros(100), SR)["windows"] == 0


def test_student_quality_renders_and_tables(tmp_path):
    """Render two rows with vtts_say from a random-weight int8 vi-en student, compute the HF
    metrics, and print the comparison table (no ASR)."""
    torch = pytest.importorskip("torch")
    from vtts.export.quant import write_model_int8
    from vtts.student.config import PRESETS
    from vtts.student.model import Student

    sys.path.insert(0, str(ROOT / "scripts" / "eval"))
    import student_quality as sq

    torch.manual_seed(0)
    model = tmp_path / "m.vtts"
    write_model_int8(Student(PRESETS["S-vocos-p-bi"]).eval(), model, token_set="vi-en")
    subprocess.run(["make", "-s", "-C", str(sq.RT), "build/vtts_say", "build/lex_en.bin"], check=True)
    rows = [{"id": "a", "text": "Xin chào, hôm nay trời đẹp."}, {"id": "b", "text": "Turn on the Wi-Fi."}]
    sq.render_set(model, rows, tmp_path / "ood", jobs=2)
    assert {p.name for p in (tmp_path / "ood").glob("*.wav")} == {"a.wav", "b.wav"}
    hf = sq.hf_set(tmp_path / "ood", rows)
    assert set(hf["clips"]) == {"a", "b"} and "flatness_mean" in hf["summary"]
    summ = tmp_path / "summary.json"
    summ.write_text(json.dumps({"name": "x", "sets": {"ood": {"corpus_cer": 0.1, "mean_utmos": 2.5,
                                                               "flatness_mean": 0.2, "hf_ratio_db_mean": -30.0}}}))
    t = sq.table([summ])
    assert "| x | 0.100 | 2.50 | 0.200 | -30.0 |" in t
