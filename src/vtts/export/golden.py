"""Golden fixtures for the C runtime: ids, log-durations, durations, latent, pcm."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import torch

from vtts.frontend.g2p import encode, g2p
from vtts.frontend.text import split_sentences
from vtts.student.model import Student, durations_from_log

MAGIC = b"VGLD"


@torch.no_grad()
def golden_case(model: Student, ids: list[int], length_scale: float = 1.0) -> dict:
    x = torch.tensor([ids], dtype=torch.long)
    log_dur = model.forward_duration(x)
    dur = durations_from_log(log_dur, length_scale, model.cfg.max_duration)
    z = model.forward_latent(x, dur)
    pcm = model.decode(z)
    return {"ids": np.array(ids, np.int32), "log_dur": log_dur[0].numpy().astype(np.float32),
            "dur": dur[0].numpy().astype(np.int32), "z": z[0].numpy().astype(np.float32),
            "pcm": pcm[0, 0].numpy().astype(np.float32)}


def write_golden(model: Student, texts: list[str], path: Path) -> list[dict]:
    model.eval()
    cases = [golden_case(model, encode(g2p(split_sentences(t)[0]))) for t in texts]
    with open(path, "wb") as f:
        f.write(MAGIC + struct.pack("<I", len(cases)))
        for c in cases:
            n = len(c["ids"])
            f.write(struct.pack("<i", n) + c["ids"].tobytes() + c["log_dur"].tobytes() + c["dur"].tobytes())
            f.write(struct.pack("<ii", c["z"].shape[1], c["z"].shape[0]) + c["z"].tobytes())
            f.write(struct.pack("<i", len(c["pcm"])) + c["pcm"].tobytes())
    return cases
