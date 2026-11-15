import pytest
import torch

from vtts.student.config import PRESETS, StudentConfig
from vtts.student.macs import count_macs
from vtts.student.model import Student

BUDGET = {"S": 120.0, "M": 300.0}


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_preset_within_budget_and_size(name):
    cfg = PRESETS[name]
    macs = count_macs(cfg)
    assert macs["per_second"] / 1e6 <= BUDGET[cfg.size], (name, macs["per_second"] / 1e6)
    n = sum(p.numel() for p in Student(cfg).parameters())
    lo, hi = (0.3e6, 0.9e6) if cfg.size == "S" else (1.0e6, 2.0e6)
    assert lo <= n <= hi, (name, n)


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_shapes(name):
    m = Student(PRESETS[name]).eval()
    ids = torch.randint(4, 65, (1, 12))
    assert m.forward_duration(ids).shape == (1, 12)
    dur = torch.full((1, 12), 3, dtype=torch.long)
    z = m.forward_latent(ids, dur)
    assert z.shape == (1, 192, 36)
    wav = m.decode(z)
    assert wav.shape == (1, 1, 36 * 256)
    assert torch.all(wav.abs() <= 1.0)


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_macs_match_measured_conv_work(name):
    """Analytic counter agrees with a hook-based count on the decoder within 2%."""
    cfg = PRESETS[name]
    m = Student(cfg).eval()
    measured = m.measure_decoder_macs(frames=100)
    analytic = count_macs(cfg)["decoder"] * 100 * 256 / cfg.sample_rate
    assert abs(measured - analytic) / analytic < 0.02


@pytest.mark.parametrize("name", ["S-vocos", "S-istft"])
def test_decode_under_autocast(name):
    """Training runs the decoder under AMP; iSTFT must still get float32 input."""
    dev = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else None)
    if dev is None:
        pytest.skip("needs a GPU-type device where autocast casts linear layers to fp16")
    m = Student(PRESETS[name]).eval().to(dev)
    with torch.autocast(dev, dtype=torch.float16):
        wav = m.decode(torch.randn(1, 192, 8, device=dev))
    assert wav.shape == (1, 1, 8 * 256) and torch.isfinite(wav).all()


def test_prosody_preset_predicts_and_conditions():
    cfg = PRESETS["M-vocos-p"]
    assert cfg.prosody
    m = Student(cfg).eval()
    ids = torch.randint(4, 65, (2, 10))
    dur = torch.full((2, 10), 3, dtype=torch.long)
    z, pred = m.forward_latent_train(ids, dur, None)
    assert z.shape == (2, 192, 30) and pred.shape == (2, 2, 30)
    target = torch.zeros(2, 2, 30)
    z_forced, _ = m.forward_latent_train(ids, dur, target)
    assert not torch.allclose(z_forced, z)  # conditioning changes the latent
    m.expressiveness = 1.5
    assert not torch.allclose(m.forward_latent(ids, dur), z)
