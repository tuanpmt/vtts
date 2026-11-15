import itertools
import os
from pathlib import Path

import numpy as np
import pytest
import torch

from vtts.teacher.config import TeacherConfig
from vtts.teacher.vits.monotonic_align import maximum_path


def _best_monotonic(value: np.ndarray) -> float:
    """Brute force: each frame y maps to a token x, non-decreasing, steps of 0/1, start 0 end last."""
    t_y, t_x = value.shape
    best = -np.inf
    for steps in itertools.product([0, 1], repeat=t_y - 1):
        xs = np.concatenate([[0], np.cumsum(steps)])
        if xs[-1] != t_x - 1:
            continue
        best = max(best, value[np.arange(t_y), xs].sum())
    return best


def test_mas_matches_bruteforce():
    rng = np.random.default_rng(0)
    value = rng.standard_normal((6, 3)).astype(np.float32)
    v = torch.from_numpy(value)[None]
    path = maximum_path(v, torch.ones_like(v))[0].numpy()
    assert path.sum() == 6
    assert np.isclose((path * value).sum(), _best_monotonic(value), atol=1e-5)


def test_mas_short_text():
    v = torch.randn(1, 50, 1)
    path = maximum_path(v, torch.ones_like(v))[0]
    assert torch.all(path[:, 0] == 1)


def test_generator_infer_shape():
    from vtts.teacher.model import build_generator

    g = build_generator(TeacherConfig()).eval()
    x = torch.randint(4, 65, (1, 20))
    torch.manual_seed(0)
    with torch.no_grad():
        y = g.infer(x, torch.tensor([20]), noise_scale=0.667, length_scale=1.0,
                    noise_scale_w=0.8)[0]
    assert y.shape[-1] % 256 == 0 and y.shape[-1] > 0


@pytest.mark.slow
def test_warmstart_loads_strict():
    from vtts.teacher.model import build_discriminator, build_generator, load_warmstart

    ckpt = Path(os.environ.get("VTTS_WARMSTART", "artifacts/warmstart/epoch=4769-step=919580.ckpt"))
    if not ckpt.exists():
        pytest.skip("warm-start checkpoint not present")
    cfg = TeacherConfig()
    load_warmstart(build_generator(cfg), build_discriminator(cfg), ckpt)
