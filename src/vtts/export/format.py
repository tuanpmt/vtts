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
# from vocab. Sizes are those of src/vtts/frontend/phoneme_set.py (checked by tests). Codes from 11
# have a Python front-end only so far: the C runtime does not know them yet and loads such models
# with token set "unknown" (raw ids only).
TOKEN_SET_CODES = {"v1": 1, "vi-en": 2, "zh-en": 3, "ko-en": 4, "ja-en": 5, "es-en": 6, "id-en": 7,
                   "pt-en": 8, "th-en": 9, "hi-en": 10}
TOKEN_SET_SIZES = {"v1": 65, "vi-en": 107, "zh-en": 171, "ko-en": 153, "ja-en": 144, "es-en": 138,
                   "id-en": 141, "pt-en": 150, "th-en": 162, "hi-en": 157}
TOKEN_SET_CODES["no-en"], TOKEN_SET_SIZES["no-en"] = 24, 156
TOKEN_SET_CODES["sv-en"], TOKEN_SET_SIZES["sv-en"] = 23, 155
TOKEN_SET_CODES["nl-en"], TOKEN_SET_SIZES["nl-en"] = 21, 159
# The sets that existed before the token_set dim: a file without the dim holds one of them, so only
# these are inferred from the vocab (their sizes are distinct). Every later set is recorded by its
# code (its size may equal another's: it-en and fi-en both have 142 ids).
LEGACY_TOKEN_SETS = ("v1", "vi-en", "zh-en", "ko-en", "ja-en", "es-en", "id-en", "pt-en", "th-en", "hi-en")
TOKEN_SET_CODES["fr-en"] = 11
TOKEN_SET_SIZES["fr-en"] = 143
TOKEN_SET_CODES["de-en"] = 12
TOKEN_SET_SIZES["de-en"] = 167
TOKEN_SET_CODES["it-en"] = 13
TOKEN_SET_SIZES["it-en"] = 142
TOKEN_SET_CODES["tr-en"] = 15
TOKEN_SET_SIZES["tr-en"] = 146
TOKEN_SET_CODES["ru-en"] = 16
TOKEN_SET_SIZES["ru-en"] = 154
TOKEN_SET_CODES["pl-en"] = 17
TOKEN_SET_SIZES["pl-en"] = 151
TOKEN_SET_CODES["ar-en"] = 19
TOKEN_SET_SIZES["ar-en"] = 149
TOKEN_SET_CODES["fi-en"] = 25
TOKEN_SET_SIZES["fi-en"] = 142
TOKEN_SET_CODES["el-en"] = 26
TOKEN_SET_SIZES["el-en"] = 139
TOKEN_SET_CODES["ms-en"] = 28
TOKEN_SET_SIZES["ms-en"] = 145
TOKEN_SET_CODES["tl-en"] = 29
TOKEN_SET_SIZES["tl-en"] = 139
TOKEN_SET_CODES["sw-en"] = 33
TOKEN_SET_SIZES["sw-en"] = 147
TOKEN_SET_CODES["da-en"] = 22
TOKEN_SET_SIZES["da-en"] = 158
TOKEN_SET_CODES["lo-en"] = 32
TOKEN_SET_SIZES["lo-en"] = 163
TOKEN_SET_CODES["km-en"], TOKEN_SET_SIZES["km-en"] = 31, 176
TOKEN_SET_CODES["my-en"], TOKEN_SET_SIZES["my-en"] = 30, 160


def token_set_for_vocab(vocab: int) -> str | None:
    """The legacy token set whose size is exactly vocab (how a file without the dim is read), else None."""
    return next((k for k in LEGACY_TOKEN_SETS if TOKEN_SET_SIZES[k] == vocab), None)


def export_token_set_for_vocab(vocab: int) -> str | None:
    """The one token set of any age whose size is exactly vocab (the default of an export), None when
    no set or several sets have that size (it-en and fi-en: 142 ids): the dim is then left out unless
    the caller names the set (scripts/student/export_student.py requires it)."""
    hits = [k for k, n in TOKEN_SET_SIZES.items() if n == vocab]
    return hits[0] if len(hits) == 1 else None


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
        return export_token_set_for_vocab(vocab)
    if token_set not in TOKEN_SET_CODES:
        raise ValueError(f"unknown token set {token_set!r}; one of {sorted(TOKEN_SET_CODES)}")
    if vocab < TOKEN_SET_SIZES[token_set]:
        raise ValueError(f"vocab {vocab} is smaller than token set {token_set} "
                         f"({TOKEN_SET_SIZES[token_set]} ids)")
    return token_set



def pack_text_mode(mode: str) -> int:
    """Optional dim `text_mode`: the device text mode a model starts in (e.g. "en" for the
    English-only voice nu-en, which uses the vi-en token set), up to 4 ASCII chars packed
    little-endian ("en" = 0x6e65). Runtimes without the dim start in the token set's first mode."""
    b = mode.encode("ascii")
    if not 1 <= len(b) <= 4 or not all(0x20 < c < 0x7f for c in b):
        raise ValueError(f"text mode {mode!r}: 1-4 printable ASCII chars")
    return int.from_bytes(b, "little")


def unpack_text_mode(value: int) -> str:
    return int(value).to_bytes(4, "little").rstrip(b"\0").decode("ascii") if value else ""


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
        f.writelines(DIM.pack(k.encode(), int(v)) for k, v in dims.items())
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
    the set the vocab names (65 -> v1, 107 -> vi-en, 171 -> zh-en, 153 -> ko-en, 144 -> ja-en,
    138 -> es-en, 141 -> id-en, 150 -> pt-en, 162 -> th-en, 157 -> hi-en, 143 -> fr-en, 167 -> de-en, 142 -> it-en,
    146 -> tr-en, 154 -> ru-en, 151 -> pl-en, 149 -> ar-en,
    145 -> ms-en, 147 -> sw-en, 159 -> nl-en, 155 -> sv-en, 156 -> no-en; it-en and fi-en (142), el-en and tl-en (139) need the argument)."""
    d = config_dims(model.cfg)
    d["expr_milli"] = round(getattr(model, "expressiveness", 1.0) * 1000)
    ts = resolve_token_set(model.cfg.vocab, token_set)
    if ts is not None:
        d["token_set"] = TOKEN_SET_CODES[ts]
    return d


def read_table(path: Path) -> list[dict]:
    data = Path(path).read_bytes()
    _magic, _version, n_dims, n_tensors, _ = HEADER.unpack_from(data, 0)
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
    magic, version, n_dims, _n_tensors, _ = HEADER.unpack_from(data, 0)
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


def read_tensors(path: Path) -> tuple[dict[str, int], dict[str, tuple[np.ndarray, np.ndarray | None]]]:
    """dims and tensors (with the per-channel scales of int8 tensors), as write_tensors takes them."""
    data = Path(path).read_bytes()
    dims, arrays = read_model(path)
    tensors = {}
    for row in read_table(path):
        scale = None
        if row["dtype"] == 1:
            scale = np.frombuffer(data, np.float32, row["shape"][0], row["scale_offset"]).copy()
        tensors[row["name"]] = (arrays[row["name"]], scale)
    return dims, tensors


def set_dims(src: Path, dst: Path, updates: dict[str, int]) -> None:
    """Rewrite a model file with dims added or changed (tensor bytes unchanged; offsets move)."""
    dims, tensors = read_tensors(src)
    dims.update({k: int(v) for k, v in updates.items()})
    write_tensors(Path(dst), dims, tensors)
