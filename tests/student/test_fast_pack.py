"""Fast distillation pack: batched teacher render and prosody computed during the render must
give the same pack as the per-item path followed by add_prosody."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

from vtts.student.distill_data import (
    DistillShards,
    add_prosody,
    convert_to_mmap,
    teacher_targets,
    teacher_targets_batch,
)
from vtts.teacher.config import TeacherConfig
from vtts.teacher.infer import Teacher
from vtts.teacher.model import build_generator

ROOT = Path(__file__).resolve().parents[2]
TINY = {"inter_channels": 32, "hidden_channels": 32, "filter_channels": 64, "n_layers": 2,
            "upsample_initial_channel": 32}


def _teacher(use_sdp: bool = True) -> Teacher:
    cfg = TeacherConfig(**TINY, use_sdp=use_sdp)
    torch.manual_seed(0)
    return Teacher(build_generator(cfg).eval(), cfg, "cpu")


SEQS = [[1, 30, 2], [1, 40, 41, 42, 43, 44, 45, 2], [1, 50, 51, 2], [1] + list(range(10, 30)) + [2]]


@pytest.mark.parametrize("use_sdp", [True, False])
@pytest.mark.parametrize("noise", [0.0, 0.333])
def test_batched_render_equals_per_item(use_sdp, noise):
    t = _teacher(use_sdp)
    seeds = [11, 12, 13, 14]
    ref = [teacher_targets(t, ids, seed=s, noise_scale=noise, noise_w=0.8) for ids, s in zip(SEQS, seeds)]
    out = teacher_targets_batch(t, SEQS, seeds, noise, 0.8)
    for r, o in zip(ref, out):
        assert set(r) == set(o)
        for k in r:
            assert r[k].shape == o[k].shape and r[k].dtype == o[k].dtype, k
        assert np.array_equal(r["dur"], o["dur"])
        assert np.abs(r["z"].astype(np.float32) - o["z"].astype(np.float32)).max() <= 2e-3
        assert np.abs(r["audio"].astype(np.int32) - o["audio"]).max() <= 1


def test_batched_render_amp_keeps_durations_and_latents():
    t = _teacher()
    ref = teacher_targets_batch(t, SEQS, [1, 2, 3, 4], 0.333, 0.8)
    out = teacher_targets_batch(t, SEQS, [1, 2, 3, 4], 0.333, 0.8, amp="bf16")
    for r, o in zip(ref, out):
        assert np.array_equal(r["dur"], o["dur"]) and np.array_equal(r["z"], o["z"])
        assert r["audio"].shape == o["audio"].shape


def test_batches_respect_size_and_token_budget():
    sys.path.insert(0, str(ROOT / "scripts" / "student"))
    try:
        from build_distill_pack import batches
    finally:
        sys.path.pop(0)
    lengths = [5, 50, 7, 30, 6, 40, 8]
    bs = batches(lengths, batch_size=3, batch_tokens=90)
    assert sorted(i for b in bs for i in b) == list(range(len(lengths)))
    for b in bs:
        assert len(b) <= 3 and (len(b) == 1 or len(b) * max(lengths[i] for i in b) <= 90)


def _pack(tmp_path: Path, name: str, *extra: str) -> Path:
    out = tmp_path / name
    cmd = [sys.executable, str(ROOT / "scripts" / "student" / "build_distill_pack.py"),
           "--ckpt", str(tmp_path / "g.pt"), "--sentences", str(tmp_path / "s.jsonl"),
           "--out", str(out / "shards"), "--device", "cpu", *extra]
    subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=ROOT)
    convert_to_mmap(out / "shards", out / "mm")
    add_prosody(out / "mm", workers=1)
    return out / "mm"


def test_pack_build_fast_path_matches_per_item(tmp_path):
    t = _teacher()
    torch.save({"g": t.g.state_dict(), "config": dict(TINY), "step": 0}, tmp_path / "g.pt")
    rows = [{"text": "Xin chào bạn.", "lang": "vi"}, {"text": "Play some music now.", "lang": "en"},
            {"text": "Hôm nay trời đẹp quá.", "lang": "vi"}, {"text": "Good morning.", "lang": "en"}]
    (tmp_path / "s.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                      encoding="utf-8")
    old = _pack(tmp_path, "old", "--per-item", "--prosody-workers", "0")
    new = _pack(tmp_path, "new", "--batch-size", "3", "--prosody-workers", "2")
    # the fast path wrote the prosody into the shard; add_prosody only added the stats
    assert sorted(p.name for p in (new / "shard_00000").glob("*.npy")) == \
        sorted(p.name for p in (old / "shard_00000").glob("*.npy"))
    a, b = DistillShards(old), DistillShards(new)
    assert len(a) == len(b) == 4
    for k in range(4):
        for key in ("ids", "dur", "vuv"):
            assert np.array_equal(a[k][key], b[k][key]), key
        assert np.abs(a[k]["audio"].astype(np.int32) - b[k]["audio"]).max() <= 1
        assert np.abs(a[k]["z"].astype(np.float32) - b[k]["z"]).max() <= 2e-3
        for key in ("lf0", "energy"):
            assert a[k][key].dtype == b[k][key].dtype and a[k][key].shape == b[k][key].shape
    sa = json.loads((old / "prosody_stats.json").read_text())
    sb = json.loads((new / "prosody_stats.json").read_text())
    assert sa.keys() == sb.keys() and all(abs(sa[k] - sb[k]) < 1e-3 for k in sa)
