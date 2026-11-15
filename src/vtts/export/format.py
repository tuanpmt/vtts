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


def write_model(model, path: Path) -> None:
    """fp32 export of a Student."""
    tensors = {k: (v.detach().cpu().numpy().astype(np.float32), None)
               for k, v in model.state_dict().items()}
    write_tensors(Path(path), model_dims(model), tensors)


def model_dims(model) -> dict[str, int]:
    d = config_dims(model.cfg)
    d["expr_milli"] = int(round(getattr(model, "expressiveness", 1.0) * 1000))
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
        raise ValueError("not a VTTS v1 file")
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
