import json

import numpy as np
import pytest
import torch

from vtts.student.config import PRESETS
from vtts.student.distill_data import teacher_targets, write_shard
from vtts.student.train import latest, train
from vtts.teacher.config import TeacherConfig
from vtts.teacher.infer import Teacher
from vtts.teacher.model import build_generator

TINY_T = dict(inter_channels=192, hidden_channels=32, filter_channels=64, n_layers=2,
              upsample_initial_channel=32)


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


@pytest.mark.parametrize("stage", ["front", "dec", "joint"])
def test_one_step_finite(tmp_path, shards, stage):
    out = tmp_path / stage
    train(PRESETS["S-vocos"], shards, out, stage, max_steps=1, batch_size=2, ckpt_every=1,
          log_every=1, device="cpu")
    row = json.loads((out / "log.jsonl").read_text().splitlines()[-1])
    assert row["step"] == 1 and np.isfinite(row["loss"])
    assert latest(out, stage) is not None


def test_nan_skipped_and_resume(tmp_path, shards):
    out = tmp_path / "front"
    train(PRESETS["S-vocos"], shards, out, "front", 1, batch_size=2, ckpt_every=1, log_every=1, device="cpu")
    before = torch.load(latest(out, "front"), weights_only=False)["student"]
    train(PRESETS["S-vocos"], shards, out, "front", 2, batch_size=2, ckpt_every=1, log_every=1,
          device="cpu", nan_steps=frozenset({2}))
    after = torch.load(latest(out, "front"), weights_only=False)
    assert after["step"] == 2
    assert all(torch.equal(before[k], after["student"][k]) for k in before)


def test_dec_step_with_mrd(tmp_path, shards):
    out = tmp_path / "mrd"
    train(PRESETS["S-vocos"], shards, out, "dec", max_steps=1, batch_size=2, ckpt_every=1,
          log_every=1, device="cpu", disc="mpd+mrd")
    row = json.loads((out / "log.jsonl").read_text().splitlines()[-1])
    assert np.isfinite(row["loss"]) and np.isfinite(row["l_d"])


def test_mrd_outputs_per_resolution():
    from vtts.student.discriminators import MultiResolutionDiscriminator

    d = MultiResolutionDiscriminator()
    y = torch.randn(2, 1, 8192)
    real, fake, fr, ff = d(y, y)
    assert len(real) == len(fake) == 3 and len(fr) == 3
    assert all(r.shape[0] == 2 for r in real)


def test_front_step_with_prosody_targets(tmp_path, shards):
    from vtts.student.distill_data import add_prosody, convert_to_mmap

    convert_to_mmap(shards, tmp_path / "mm")
    add_prosody(tmp_path / "mm", workers=1)
    out = tmp_path / "frontp"
    train(PRESETS["M-vocos-p"], tmp_path / "mm", out, "front", max_steps=1, batch_size=2,
          ckpt_every=1, log_every=1, device="cpu")
    row = json.loads((out / "log.jsonl").read_text().splitlines()[-1])
    assert np.isfinite(row["l_prosody"]) and np.isfinite(row["l_dur"])
