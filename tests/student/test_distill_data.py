import numpy as np
import torch

from vtts.student.distill_data import DistillShards, teacher_targets, write_shard
from vtts.teacher.config import TeacherConfig
from vtts.teacher.infer import Teacher
from vtts.teacher.model import build_generator

TINY = dict(inter_channels=32, hidden_channels=32, filter_channels=64, n_layers=2,
            upsample_initial_channel=32)


def _teacher():
    cfg = TeacherConfig(**TINY)
    torch.manual_seed(0)
    return Teacher(build_generator(cfg).eval(), cfg, "cpu")


def test_targets_consistent():
    t = teacher_targets(_teacher(), [1, 30, 40, 50, 2], seed=7, noise_scale=0.0, noise_w=0.8)
    assert t["dur"].dtype == np.int32 and (t["dur"] >= 1).all()
    assert t["z"].shape == (32, int(t["dur"].sum()))
    assert len(t["audio"]) == int(t["dur"].sum()) * 256
    assert t["audio"].dtype == np.int16


def test_targets_deterministic():
    tch = _teacher()
    a = teacher_targets(tch, [1, 30, 40, 2], seed=3, noise_scale=0.0, noise_w=0.8)
    b = teacher_targets(tch, [1, 30, 40, 2], seed=3, noise_scale=0.0, noise_w=0.8)
    assert np.array_equal(a["dur"], b["dur"]) and np.array_equal(a["audio"], b["audio"])


def test_shard_roundtrip(tmp_path):
    tch = _teacher()
    items = [dict(teacher_targets(tch, ids, seed=i, noise_scale=0.0, noise_w=0.8), ids=np.array(ids, np.int32))
             for i, ids in enumerate([[1, 30, 2], [1, 40, 41, 42, 2]])]
    write_shard(tmp_path / "shard_00000.npz", items)
    ds = DistillShards(tmp_path)
    assert len(ds) == 2
    x = ds[1]
    assert list(x["ids"]) == [1, 40, 41, 42, 2]
    assert x["z"].shape[1] == x["dur"].sum() and len(x["audio"]) == x["dur"].sum() * 256


def test_mmap_conversion_matches_npz(tmp_path):
    from vtts.student.distill_data import convert_to_mmap

    tch = _teacher()
    items = [dict(teacher_targets(tch, ids, seed=i, noise_scale=0.0, noise_w=0.8), ids=np.array(ids, np.int32))
             for i, ids in enumerate([[1, 30, 2], [1, 40, 41, 42, 2], [1, 50, 2]])]
    write_shard(tmp_path / "npz" / "shard_00000.npz", items[:2]) if (tmp_path / "npz").mkdir() is None else None
    write_shard(tmp_path / "npz" / "shard_00001.npz", items[2:])
    convert_to_mmap(tmp_path / "npz", tmp_path / "mm")
    a, b = DistillShards(tmp_path / "npz"), DistillShards(tmp_path / "mm")
    assert len(a) == len(b) == 3
    for k in range(3):
        for key in ("ids", "dur", "audio", "z"):
            assert np.array_equal(a[k][key], b[k][key])
    assert isinstance(b[0]["z"], np.memmap) or b[0]["z"].base is not None


def test_prosody_added_to_mmap_pack(tmp_path):
    import json

    from vtts.student.distill_data import add_prosody, convert_to_mmap

    tch = _teacher()
    items = [dict(teacher_targets(tch, ids, seed=i, noise_scale=0.0, noise_w=0.8), ids=np.array(ids, np.int32))
             for i, ids in enumerate([[1, 30, 31, 2], [1, 40, 41, 42, 2]])]
    (tmp_path / "npz").mkdir()
    write_shard(tmp_path / "npz" / "shard_00000.npz", items)
    convert_to_mmap(tmp_path / "npz", tmp_path / "mm")
    stats = add_prosody(tmp_path / "mm", workers=1)
    assert set(stats) >= {"lf0_mean", "lf0_std", "energy_mean", "energy_std"}
    assert json.loads((tmp_path / "mm" / "prosody_stats.json").read_text()) == stats
    ds = DistillShards(tmp_path / "mm")
    for k in range(2):
        x = ds[k]
        t = int(x["dur"].sum())
        assert x["lf0"].shape == x["vuv"].shape == x["energy"].shape == (t,)
