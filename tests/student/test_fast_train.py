"""Training speed paths: vectorised expand, sync-free fast step, prefetch, amp, warm decoder
(init_decoder) and the E6 runner."""

import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest
import torch

from vtts.student.config import PRESETS
from vtts.student.distill_data import teacher_targets, write_shard
from vtts.student.model import Student, expand, expand_loop
from vtts.student.train import disc_loss, latest, train
from vtts.teacher.config import TeacherConfig
from vtts.teacher.infer import Teacher
from vtts.teacher.model import build_generator
from vtts.teacher.vits.losses import discriminator_loss

ROOT = Path(__file__).resolve().parents[2]
TINY_T = {"inter_channels": 192, "hidden_channels": 32, "filter_channels": 64, "n_layers": 2,
          "upsample_initial_channel": 32}


@pytest.fixture(scope="module")
def shards(tmp_path_factory):
    root = tmp_path_factory.mktemp("shards")
    cfg = TeacherConfig(**TINY_T)
    torch.manual_seed(0)
    t = Teacher(build_generator(cfg).eval(), cfg, "cpu")
    items = []
    for i in range(6):
        ids = [1] + list(range(10 + i, 20 + i)) + [2]
        items.append(dict(teacher_targets(t, ids, seed=i, noise_scale=0.0, noise_w=0.8),
                          ids=np.array(ids, np.int32)))
    write_shard(root / "shard_00000.npz", items)
    return root


def test_vectorised_expand_equals_loop():
    g = torch.Generator().manual_seed(0)
    for n in (1, 3, 9):
        x = torch.randn(3, 5, n, generator=g, requires_grad=True)
        d = torch.randint(0, 5, (3, n), generator=g)
        d[0] = 0
        d[0, 0] = 2  # short item, zero-duration tokens
        a, fa = expand(x, d)
        b, fb = expand_loop(x, d)
        assert torch.equal(a, b) and torch.equal(fa, fb)
        w = torch.randn_like(a)
        ga, = torch.autograd.grad((a * w).sum(), x)
        gb, = torch.autograd.grad((b * w).sum(), x)
        assert torch.allclose(ga, gb, atol=1e-6)


def test_disc_loss_matches_vits():
    r = [torch.randn(2, 7), torch.randn(2, 3)]
    f = [torch.randn(2, 7), torch.randn(2, 3)]
    assert torch.allclose(disc_loss(r, f), discriminator_loss(r, f)[0])


def _rows(out: Path) -> list[dict]:
    return [json.loads(ln) for ln in (out / "log.jsonl").read_text().splitlines()]


@pytest.mark.parametrize("stage", ["front", "dec", "joint"])
def test_fast_step_tracks_plain_step(tmp_path, shards, stage):
    """Same seed, CPU: the fast step (fused AdamW, sync-free skip) and prefetch give the same
    losses and weights as the plain step."""
    res = {}
    for name, opts in (("plain", {}), ("fast", {"fast": True, "prefetch": 2})):
        torch.manual_seed(0)
        out = tmp_path / name
        train(PRESETS["S-vocos"], shards, out, stage, max_steps=3, batch_size=2, ckpt_every=3,
              log_every=1, device="cpu", disc="mpd+mrd", **opts)
        res[name] = (_rows(out), torch.load(latest(out, stage), weights_only=False)["student"])
    (ra, wa), (rb, wb) = res["plain"], res["fast"]
    assert [r["step"] for r in ra] == [r["step"] for r in rb] == [1, 2, 3]
    for x, y in zip(ra, rb):
        assert abs(x["loss"] - y["loss"]) <= 1e-3 * max(1.0, abs(x["loss"])), (x, y)
    for k in wa:
        assert torch.allclose(wa[k], wb[k], atol=1e-5), k


def test_fast_step_skips_nan_without_sync(tmp_path, shards):
    out = tmp_path / "front"
    train(PRESETS["S-vocos"], shards, out, "front", 1, batch_size=2, ckpt_every=1, log_every=1,
          device="cpu", fast=True)
    before = torch.load(latest(out, "front"), weights_only=False)
    train(PRESETS["S-vocos"], shards, out, "front", 2, batch_size=2, ckpt_every=1, log_every=1,
          device="cpu", nan_steps=frozenset({2}), fast=True)
    after = torch.load(latest(out, "front"), weights_only=False)
    assert after["step"] == 2
    assert all(torch.equal(before["student"][k], after["student"][k]) for k in before["student"])
    # the optimizer state did not advance either
    s0 = before["opt"]["state"][0]
    s1 = after["opt"]["state"][0]
    assert float(s0["step"]) == float(s1["step"]) and torch.equal(s0["exp_avg"], s1["exp_avg"])
    assert any(r.get("skipped_nan") for r in _rows(out))


def test_fast_resume_from_plain_checkpoint(tmp_path, shards):
    out = tmp_path / "dec"
    train(PRESETS["S-vocos"], shards, out, "dec", 1, batch_size=2, ckpt_every=1, log_every=1, device="cpu")
    train(PRESETS["S-vocos"], shards, out, "dec", 2, batch_size=2, ckpt_every=1, log_every=1,
          device="cpu", fast=True)
    assert torch.load(latest(out, "dec"), weights_only=False)["step"] == 2


def test_bf16_autocast_step_runs(tmp_path, shards):
    out = tmp_path / "bf16"
    train(PRESETS["S-vocos"], shards, out, "joint", 2, batch_size=2, ckpt_every=2, log_every=1,
          device="cpu", amp="bf16", fast=True, disc="mpd+mrd")
    assert all(np.isfinite(r["loss"]) for r in _rows(out) if "loss" in r)


def test_init_decoder_takes_the_decoder_only(tmp_path, shards):
    cfg = PRESETS["S-vocos"]
    torch.manual_seed(1)
    src = Student(cfg)
    torch.save({"student": src.state_dict()}, tmp_path / "src.pt")
    torch.manual_seed(2)
    front = Student(cfg)
    torch.save({"student": front.state_dict()}, tmp_path / "front.pt")
    out = tmp_path / "dec"
    train(cfg, shards, out, "dec", 1, batch_size=2, lr=0.0, ckpt_every=1, log_every=1, device="cpu",
          init=tmp_path / "front.pt", init_decoder=tmp_path / "src.pt")
    got = torch.load(latest(out, "dec"), weights_only=False)["student"]
    for k, v in got.items():
        want = (src if k.startswith("decoder.") else front).state_dict()[k]
        assert torch.equal(v, want), k


def test_e6_warm_decoder_smoke(tmp_path):
    """Tiny random teacher: an E0 run writes the float student, E6 starts its decoder from it."""
    cfg = TeacherConfig(**TINY_T)
    torch.manual_seed(0)
    torch.save({"g": build_generator(cfg).state_dict(), "config": dict(TINY_T), "step": 0}, tmp_path / "g.pt")
    rows = [{"text": "Xin chào bạn.", "lang": "vi"}, {"text": "Play some music.", "lang": "en"},
            {"text": "Hôm nay trời đẹp.", "lang": "vi"}]
    (tmp_path / "s.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                      encoding="utf-8")
    env = {**os.environ, "PRESET": "S-vocos-p-bi", "LIMIT": "3", "FS": "2", "DS": "2", "JS": "2",
           "SNAP": "2", "PROSODY_WORKERS": "1", "OMP_NUM_THREADS": "2"}
    runner = ROOT / "scripts" / "student" / "run_experiment.sh"
    args = [str(tmp_path / "g.pt"), str(tmp_path / "s.jsonl")]
    subprocess.run(["bash", str(runner), "e0", *args, str(tmp_path / "runs" / "e0"), "cpu"], check=True,
                   env=env, capture_output=True, text=True)
    init = tmp_path / "runs" / "e0" / "S-vocos-p-bi.student.pt"
    assert init.exists()
    bad = subprocess.run(["bash", str(runner), "e6", *args, str(tmp_path / "runs" / "e6x"), "cpu"],
                         check=False, env=env, capture_output=True, text=True)
    assert bad.returncode == 2  # no INIT_FROM
    r = subprocess.run(["bash", str(runner), "e6", *args, str(tmp_path / "runs" / "e6"), "cpu"],
                       check=True, env={**env, "INIT_FROM": str(init), "INIT_FRONT": "1"},
                       capture_output=True, text=True)
    assert "INIT_FROM=" + str(init) in (tmp_path / "runs" / "e6" / "experiment.env").read_text(), r.stdout
    assert (tmp_path / "runs" / "e6" / "S-vocos-p-bi.q8.vtts").exists()
    assert (tmp_path / "runs" / "e6" / "CHAIN_DONE").exists()
