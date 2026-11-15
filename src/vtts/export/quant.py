"""int8 export: per-output-channel symmetric weights, repacked [co][k][ci] for contiguous dots.

Quantized: frame-rate acoustic convs, acoustic output, all decoder convs / linears /
transposed convs except the depthwise ones. Kept fp32: embeddings, the duration model,
token-rate acoustic blocks, LayerNorm, biases, gamma, the position linear, depthwise convs.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .format import model_dims, write_tensors

QUANT_PATTERNS = [
    r"acoustic\.frame_blocks\.\d+\.conv\.weight",
    r"acoustic\.pitch_blocks\.\d+\.conv\.weight",
    r"acoustic\.out\.weight",
    r"decoder\.pre\.weight",
    r"decoder\.ups\.\d+\.weight",
    r"decoder\.res\.\d+\.convs\.\d+\.weight",
    r"decoder\.post\.weight",
    r"decoder\.blocks\.\d+\.pw[12]\.weight",
    r"decoder\.head\.weight",
]


def is_quantized(name: str) -> bool:
    return any(re.fullmatch(p, name) for p in QUANT_PATTERNS)


def repack(name: str, w: np.ndarray) -> np.ndarray:
    """Return weights as [co, K, ci]."""
    if w.ndim == 2:  # Linear [out, in]
        return w[:, None, :]
    if re.fullmatch(r"decoder\.ups\.\d+\.weight", name):  # ConvTranspose1d [ci, co, K]
        return np.transpose(w, (1, 2, 0))
    return np.transpose(w, (0, 2, 1))  # Conv1d [co, ci, K]


def quantize_weight(w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    flat = w.reshape(w.shape[0], -1)
    amax = np.abs(flat).max(axis=1)
    scale = np.where(amax > 0, amax / 127.0, 1.0).astype(np.float32)
    q = np.clip(np.round(flat / scale[:, None]), -127, 127).astype(np.int8)
    return q.reshape(w.shape), scale


def write_model_int8(model, path: Path) -> None:
    tensors = {}
    for name, v in model.state_dict().items():
        arr = v.detach().cpu().numpy().astype(np.float32)
        if is_quantized(name):
            q, s = quantize_weight(repack(name, arr))
            tensors[name + ".q8"] = (np.ascontiguousarray(q), s)
        else:
            tensors[name] = (arr, None)
    write_tensors(Path(path), model_dims(model), tensors)
