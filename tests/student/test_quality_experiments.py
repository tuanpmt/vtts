"""Student quality experiments (docs/design/plans/2026-11-19-student-quality-experiments.md):
high-band loss and discriminators, kept checkpoints, the L preset and the runner settings."""

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
import torch

from vtts.student.config import PRESETS
from vtts.student.distill_data import teacher_targets, write_shard
from vtts.student.macs import P4_CALIBRATION, count_macs, estimate_p4_rtf
from vtts.student.model import Student
from vtts.student.train import DISCS, build_disc, hf_stft_loss, save, train
from vtts.teacher.config import TeacherConfig
from vtts.teacher.infer import Teacher
from vtts.teacher.model import build_generator

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "student" / "run_experiment.sh"
SR = 22050


def _filtered_noise(n: int, lo: float, hi: float, seed: int) -> torch.Tensor:
    spec = np.fft.rfft(np.random.default_rng(seed).standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return torch.from_numpy(x / np.sqrt((x ** 2).mean()) * 0.01).float()


def test_hf_loss_sees_only_the_high_band():
    t = torch.arange(8192) / SR
    y = (0.3 * torch.sin(2 * torch.pi * 220 * t) + _filtered_noise(8192, 4500, 10000, 0) * 0.1)[None]
    assert hf_stft_loss(y, y).item() < 1e-6
    hf = hf_stft_loss(y + _filtered_noise(8192, 5000, 10000, 1)[None], y).item()
    lf = hf_stft_loss(y + _filtered_noise(8192, 100, 3000, 1)[None], y).item()
    assert hf > 5 * lf, (hf, lf)


@pytest.mark.parametrize("kind", DISCS)
def test_discriminator_sets(kind):
    d = build_disc(kind)
    y = torch.randn(2, 1, 8192) * 0.1
    real, fake, fr, ff = d(y, y)
    n_mpd = len(build_disc("mpd")(y, y)[0])
    extra = {"mpd": 0, "mpd+mrd": 3, "mpd+mrd-hf": 6}[kind]
    assert len(real) == len(fake) == len(fr) == len(ff) == n_mpd + extra
    assert all(torch.isfinite(r).all() for r in real)


def test_unknown_discriminator():
    with pytest.raises(ValueError):
        build_disc("mrd")


def test_keep_every_keeps_snapshots(tmp_path):
    for step in range(1, 8):
        save(tmp_path, "joint", {"step": step}, keep_every=2)
    kept = sorted(int(p.stem.split("_")[1]) for p in tmp_path.glob("joint_*.pt"))
    assert kept == [2, 4, 5, 6, 7]
    plain = tmp_path / "plain"
    plain.mkdir()
    for step in range(1, 5):
        save(plain, "joint", {"step": step})
    assert len(list(plain.glob("joint_*.pt"))) == 3


@pytest.fixture(scope="module")
def shards(tmp_path_factory):
    root = tmp_path_factory.mktemp("shards")
    cfg = TeacherConfig(inter_channels=192, hidden_channels=32, filter_channels=64, n_layers=2,
                        upsample_initial_channel=32)
    torch.manual_seed(0)
    t = Teacher(build_generator(cfg).eval(), cfg, "cpu")
    items = [dict(teacher_targets(t, [1] + list(range(10 + i, 20 + i)) + [2], seed=i, noise_scale=0.0,
                                  noise_w=0.8), ids=np.array([1] + list(range(10 + i, 20 + i)) + [2], np.int32))
             for i in range(4)]
    write_shard(root / "shard_00000.npz", items)
    return root


def test_dec_step_with_hf_loss_and_hf_disc(tmp_path, shards):
    out = tmp_path / "dec"
    train(PRESETS["S-vocos"], shards, out, "dec", max_steps=2, batch_size=2, ckpt_every=1,
          log_every=1, device="cpu", disc="mpd+mrd-hf", hf_weight=2.0, keep_every=1)
    row = json.loads((out / "log.jsonl").read_text().splitlines()[-1])
    assert np.isfinite(row["loss"]) and np.isfinite(row["l_hf"]) and row["l_hf"] > 0
    st = torch.load(out / "dec_0000002.pt", weights_only=False)
    assert st["disc"] and st["train_opts"]["hf_weight"] == 2.0
    assert (out / "dec_0000001.pt").exists()


def test_l_preset_size_and_p4_estimate():
    cfg = PRESETS["L-vocos-p-bi"]
    n = sum(p.numel() for p in Student(cfg).parameters())
    assert 3.0e6 <= n <= 4.0e6
    m = PRESETS["M-vocos-p-bi"]
    # same front as M, the extra parameters are in the vocoder
    assert (cfg.d_hidden, cfg.a_hidden, cfg.prosody, cfg.vocab) == (m.d_hidden, m.a_hidden, m.prosody, m.vocab)
    assert count_macs(cfg)["acoustic"] == count_macs(m)["acoustic"]
    assert estimate_p4_rtf(cfg) <= 0.5
    # the calibration reproduces its two measured points
    for name, (_, rtf) in zip(("S-vocos-p-bi", "M-vocos-p-bi"), P4_CALIBRATION):
        assert abs(estimate_p4_rtf(PRESETS[name]) - rtf) < 0.005


def _settings(exp: str, **env) -> dict:
    import os

    r = subprocess.run(["bash", str(RUNNER), exp, "g.pt", "s.jsonl", "out"], check=True, capture_output=True,
                       text=True, env={**os.environ, "DRY_RUN": "1", **env})
    return dict(ln.split("=", 1) for ln in r.stdout.splitlines())


@pytest.mark.parametrize("exp,want", [
    ("e0", {"PRESET": "M-vocos-p-bi", "LIMIT": "20000", "FS": "10000", "DS": "30000", "JS": "20000",
            "DEC_DISC": "mpd", "JOINT_DISC": "mpd+mrd", "HF": "0"}),
    ("e1", {"JS": "100000", "SNAP": "10000", "LIMIT": "20000"}),
    ("e2a", {"HF": "2", "DEC_DISC": "mpd", "JS": "20000"}),
    ("e2b", {"HF": "2", "DEC_DISC": "mpd+mrd-hf", "JOINT_DISC": "mpd+mrd-hf"}),
    ("e3", {"LIMIT": "all", "JS": "60000"}),
    ("e4", {"PRESET": "L-vocos-p-bi", "JS": "60000"}),
    ("e5", {"LIMIT": "all", "JS": "100000"}),
])
def test_runner_settings(exp, want):
    got = _settings(exp)
    assert {k: got[k] for k in want} == want
    assert got["PRESET"] in PRESETS and got["DEC_DISC"] in DISCS and got["JOINT_DISC"] in DISCS


def test_runner_environment_overrides_and_wrappers():
    assert _settings("e1", JS="50", SNAP="25")["JS"] == "50"
    for w in sorted((ROOT / "scripts" / "student" / "experiments").glob("e*.sh")):
        exp = w.name.split("_")[0]
        assert f"run_experiment.sh\" {exp} " in w.read_text(), w
    bad = subprocess.run(["bash", str(RUNNER), "e9", "g", "s", "o"], check=False, capture_output=True, text=True)
    assert bad.returncode == 2
