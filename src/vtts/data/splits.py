"""Deterministic train / val / heldout splits."""

from __future__ import annotations

import random

from .filter import Row


def make_splits(rows: list[Row], n_heldout: int = 50, val_frac: float = 0.02,
                seed: int = 1234) -> dict[str, list[Row]]:
    order = sorted(rows, key=lambda r: r.id)
    random.Random(seed).shuffle(order)
    heldout = [r for r in order if 3.0 <= r.duration_s <= 10.0][:n_heldout]
    held_ids = {r.id for r in heldout}
    rest = [r for r in order if r.id not in held_ids]
    n_val = round(len(rest) * val_frac)
    return {"train": rest[n_val:], "val": rest[:n_val], "heldout": heldout}
