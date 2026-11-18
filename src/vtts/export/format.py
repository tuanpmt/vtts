"""Writer/reader for the VTTS model file (see docs/model-format.md)."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

MAGIC = b"VTTS"
VERSION = 1
HEADER = struct.Struct("<4sIIII")
DIM = struct.Struct("<32si")
ROW = struct.Struct("<48sBBH4iIII")
ALIGN = 16
DECODER_IDS = {"hifigan": 0, "istft": 1, "vocos": 2}
# Optional dim `token_set` (vtts_token_set_t in runtime/include/vtts.h); 0 or absent = derive
# from vocab. Sizes are those of src/vtts/frontend/phoneme_set.py (checked by tests).
TOKEN_SET_CODES = {"v1": 1, "vi-en": 2, "zh-en": 3, "ko-en": 4, "ja-en": 5}
TOKEN_SET_SIZES = {"v1": 65, "vi-en": 107, "zh-en": 171, "ko-en": 153, "ja-en": 144}


def token_set_for_vocab(vocab: int) -> str | None:
    """The token set whose size is exactly vocab, else None (ambiguous)."""
    return next((k for k, n in TOKEN_SET_SIZES.items() if n == vocab), None)


def token_set_of(dims: dict[str, int]) -> str:
    """Token set of a model file's dims, the way vtts_init resolves it: the token_set dim when
    present (a code newer than this reader: "unknown"), else by vocab (exact size, else the
    old firmware rule vocab > 65 -> vi-en)."""
    code = dims.get("token_set", 0)
    if code:
        return next((k for k, c in TOKEN_SET_CODES.items() if c == code), "unknown")
    vocab = dims["vocab"]
    return token_set_for_vocab(vocab) or ("vi-en" if vocab > 65 else "v1")


def resolve_token_set(vocab: int, token_set: str | None) -> str | None:
    """The token set to record for an export: the given one (checked against the vocab), else
    the one the vocab names unambiguously, else None (dim omitted)."""
    if token_set is None:
        return token_set_for_vocab(vocab)
    if token_set not in TOKEN_SET_CODES:
        raise ValueError(f"unknown token set {token_set!r}; one of {sorted(TOKEN_SET_CODES)}")
    if vocab < TOKEN_SET_SIZES[token_set]:
        raise ValueError(f"vocab {vocab} is smaller than token set {token_set} "
                         f"({TOKEN_SET_SIZES[token_set]} ids)")
    return token_set


def config_dims(cfg) -> dict[str, int]:
    d = {
        "vocab": cfg.vocab, "latent": cfg.latent, "hop": cfg.hop, "sample_rate": cfg.sample_rate,
        "max_duration": cfg.max_duration, "d_hidden": cfg.d_hidden, "d_depth": cfg.d_depth,
        "d_kernel": cfg.d_kernel, "a_hidden": cfg.a_hidden, "a_token_depth": cfg.a_token_depth,
        "a_frame_depth": cfg.a_frame_depth, "a_kernel": cfg.a_kernel,
        "decoder": DECODER_IDS[cfg.decoder], "c0": cfg.c0, "n_up": len(cfg.upsample),
        "n_res": len(cfg.res_dilations), "res_kernel": cfg.res_kernel, "n_fft": cfg.n_fft,
        "istft_hop": cfg.istft_hop, "v_dim": cfg.v_dim, "v_blocks": cfg.v_blocks,
        "v_mult": cfg.v_mult, "prosody": int(cfg.prosody), "p_depth": cfg.p_depth if cfg.prosody else 0,
    }
    for i, (u, k) in enumerate(zip(cfg.upsample, cfg.upsample_kernel)):
        d[f"up{i}"], d[f"upk{i}"] = u, k
    for i, r in enumerate(cfg.res_dilations):
        d[f"res_d{i}"] = r
    return d


def _pad(n: int) -> int:
    return (-n) % ALIGN


def write_tensors(path: Path, dims: dict[str, int],
                  tensors: dict[str, tuple[np.ndarray, np.ndarray | None]]) -> None:
    """tensors: name -> (array f32 or i8, per-out-channel f32 scales for i8 else None)."""
    names = list(tensors)
    table_bytes = HEADER.size + DIM.size * len(dims) + ROW.size * len(names)
    offset = table_bytes + _pad(table_bytes)
    payload = bytearray()
    rows = []
    for name in names:
        arr, scale = tensors[name]
        arr = np.ascontiguousarray(arr)
        if arr.dtype == np.float32:
            dtype = 0
        elif arr.dtype == np.int8:
            dtype = 1
        else:
            raise TypeError(f"{name}: unsupported dtype {arr.dtype}")
        if arr.ndim > 4 or len(name.encode()) >= 48:
            raise ValueError(f"{name}: ndim {arr.ndim} or name too long")
        t_off = offset + len(payload)
        payload += arr.tobytes() + b"\0" * _pad(arr.nbytes)
        s_off = 0
        if dtype == 1:
            s = np.ascontiguousarray(scale, dtype=np.float32)
            s_off = offset + len(payload)
            payload += s.tobytes() + b"\0" * _pad(s.nbytes)
        shape = list(arr.shape) + [1] * (4 - arr.ndim)
        rows.append(ROW.pack(name.encode(), dtype, arr.ndim, 0, *shape, t_off, arr.nbytes, s_off))
    with open(path, "wb") as f:
        f.write(HEADER.pack(MAGIC, VERSION, len(dims), len(names), offset))
        for k, v in dims.items():
            f.write(DIM.pack(k.encode(), int(v)))
        f.write(b"".join(rows))
        f.write(b"\0" * _pad(table_bytes))
        f.write(payload)


def write_model(model, path: Path, token_set: str | None = None) -> None:
    """fp32 export of a Student. token_set: see model_dims."""
    tensors = {k: (v.detach().cpu().numpy().astype(np.float32), None)
               for k, v in model.state_dict().items()}
    write_tensors(Path(path), model_dims(model, token_set), tensors)


def model_dims(model, token_set: str | None = None) -> dict[str, int]:
    """Dims of a Student; token_set (e.g. "zh-en") is recorded in the token_set dim, by default
    the set the vocab names (65 -> v1, 107 -> vi-en, 171 -> zh-en, 153 -> ko-en, 144 -> ja-en)."""
    d = config_dims(model.cfg)
    d["expr_milli"] = int(round(getattr(model, "expressiveness", 1.0) * 1000))
    ts = resolve_token_set(model.cfg.vocab, token_set)
    if ts is not None:
        d["token_set"] = TOKEN_SET_CODES[ts]
    return d


def read_table(path: Path) -> list[dict]:
    data = Path(path).read_bytes()
    magic, version, n_dims, n_tensors, _ = HEADER.unpack_from(data, 0)
    pos = HEADER.size + DIM.size * n_dims
    rows = []
    for i in range(n_tensors):
        name, dtype, ndim, _, s0, s1, s2, s3, off, nbytes, s_off = ROW.unpack_from(data, pos + i * ROW.size)
        rows.append({"name": name.rstrip(b"\0").decode(), "dtype": dtype,
                     "shape": (s0, s1, s2, s3)[:ndim], "offset": off, "nbytes": nbytes,
                     "scale_offset": s_off})
    return rows


def read_model(path: Path) -> tuple[dict[str, int], dict[str, np.ndarray]]:
    data = Path(path).read_bytes()
    magic, version, n_dims, n_tensors, _ = HEADER.unpack_from(data, 0)
    if magic != MAGIC or version != VERSION:
        raise ValueError("not a VTTS file (format version 1)")
    dims = {}
    for i in range(n_dims):
        k, v = DIM.unpack_from(data, HEADER.size + i * DIM.size)
        dims[k.rstrip(b"\0").decode()] = v
    tensors = {}
    for row in read_table(path):
        dt = np.float32 if row["dtype"] == 0 else np.int8
        arr = np.frombuffer(data, dt, row["nbytes"] // np.dtype(dt).itemsize, row["offset"])
        tensors[row["name"]] = arr.reshape(row["shape"])
    return dims, tensors
