"""No-reference quality predictors: DNSMOS (torchmetrics) and UTMOS (SpeechMOS)."""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

from vtts.data.audio import resample


def eval_threads(num_threads: int | None) -> int | None:
    """Threads for the ONNX scorer: the argument, else VTTS_EVAL_THREADS, else all cores. ONNX
    Runtime pins its own threads, so `taskset` alone does not keep it off other jobs' cores."""
    if num_threads is not None:
        return num_threads
    env = os.environ.get("VTTS_EVAL_THREADS")
    return int(env) if env else None


def dnsmos(x: np.ndarray, sr: int, num_threads: int | None = None) -> dict[str, float]:
    import torch
    from torchmetrics.functional.audio.dnsmos import (
        deep_noise_suppression_mean_opinion_score as _dnsmos,
    )

    y = resample(np.asarray(x, dtype=np.float32), sr, 16000)
    _p808, sig, bak, ovrl = _dnsmos(torch.from_numpy(y), 16000, personalized=False,
                                    num_threads=eval_threads(num_threads)).tolist()
    return {"sig": sig, "bak": bak, "ovrl": ovrl}


@lru_cache(maxsize=1)
def _utmos_model():
    import torch

    model = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
    return model.eval()


def utmos(x: np.ndarray, sr: int) -> float:
    import torch

    y = resample(np.asarray(x, dtype=np.float32), sr, 16000)
    with torch.inference_mode():
        return float(_utmos_model()(torch.from_numpy(y)[None], 16000).item())
