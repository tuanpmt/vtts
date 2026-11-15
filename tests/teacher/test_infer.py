import numpy as np
import torch

from vtts.teacher.config import TeacherConfig
from vtts.teacher.infer import Teacher
from vtts.teacher.model import build_generator

TINY = dict(inter_channels=32, hidden_channels=32, filter_channels=64, n_layers=2,
            upsample_initial_channel=32)


def _ckpt(tmp_path):
    cfg = TeacherConfig(**TINY)
    path = tmp_path / "ckpt_0000001.pt"
    torch.save({"g": build_generator(cfg).state_dict(), "config": cfg.__dict__, "step": 1}, path)
    return path


def test_synthesize_deterministic(tmp_path):
    t = Teacher.load(_ckpt(tmp_path), "cpu")
    a, b = t.synthesize("xin chào"), t.synthesize("xin chào")
    assert a.dtype == np.float32 and len(a) > 0
    assert np.array_equal(a, b)


def test_synthesize_multi_chunk(tmp_path):
    t = Teacher.load(_ckpt(tmp_path), "cpu")
    one = t.synthesize("xin chào bạn.")
    three = t.synthesize("xin chào bạn. hôm nay trời đẹp. cảm ơn nhiều.")
    assert len(three) > len(one)


def test_empty_text_gives_empty_audio(tmp_path):
    t = Teacher.load(_ckpt(tmp_path), "cpu")
    assert len(t.synthesize("...")) == 0
