import json

import numpy as np
import soundfile as sf
import torch

from vtts.teacher.config import TeacherConfig
from vtts.teacher.train import latest_checkpoint, train

TINY = dict(inter_channels=32, hidden_channels=32, filter_channels=64, n_layers=2,
            upsample_initial_channel=32, segment_size=2048, batch_size=2)


def _data(tmp_path):
    wavs = tmp_path / "wavs"
    wavs.mkdir()
    lines = []
    for uid, text in [("a", "xin chào bạn"), ("b", "hôm nay trời đẹp"), ("c", "cảm ơn nhiều")]:
        t = np.arange(int(22050 * 1.0)) / 22050
        sf.write(wavs / f"{uid}.wav", 0.3 * np.sin(2 * np.pi * 220 * t), 22050, subtype="PCM_16")
        lines.append(f"{uid}|{text}|1.0")
    (tmp_path / "train.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path / "train.csv", wavs


def _log(out):
    return [json.loads(x) for x in (out / "log.jsonl").read_text().splitlines()]


def test_one_step_cpu_finite(tmp_path):
    csv, wavs = _data(tmp_path)
    out = tmp_path / "run"
    train(TeacherConfig(**TINY), csv, wavs, tmp_path / "cache", out, warmstart=None,
          max_steps=1, ckpt_every=1, log_every=1, device="cpu")
    row = _log(out)[-1]
    assert row["step"] == 1
    assert all(np.isfinite(row[k]) for k in ("loss_g", "loss_d", "loss_mel", "loss_kl", "loss_dur"))


def test_resume_roundtrip(tmp_path):
    csv, wavs = _data(tmp_path)
    out = tmp_path / "run"
    cfg = TeacherConfig(**TINY)
    train(cfg, csv, wavs, tmp_path / "cache", out, None, max_steps=2, ckpt_every=2, log_every=1,
          device="cpu")
    ck = latest_checkpoint(out)
    state = torch.load(ck, weights_only=False)
    assert state["step"] == 2 and state["opt_g"]["state"]
    train(cfg, csv, wavs, tmp_path / "cache", out, None, max_steps=3, ckpt_every=1, log_every=1,
          device="cpu")
    assert [r["step"] for r in _log(out) if "loss_g" in r] == [1, 2, 3]


def test_nan_step_skipped(tmp_path):
    csv, wavs = _data(tmp_path)
    out = tmp_path / "run"
    cfg = TeacherConfig(**TINY)
    train(cfg, csv, wavs, tmp_path / "cache", out, None, max_steps=1, ckpt_every=1, log_every=1,
          device="cpu")
    before = torch.load(latest_checkpoint(out), weights_only=False)["g"]
    train(cfg, csv, wavs, tmp_path / "cache", out, None, max_steps=2, ckpt_every=1, log_every=1,
          device="cpu", nan_steps=frozenset({2}))
    after = torch.load(latest_checkpoint(out), weights_only=False)
    assert any(r.get("skipped_nan") for r in _log(out))
    assert all(torch.equal(before[k], after["g"][k]) for k in before)
    assert after["step"] == 2
