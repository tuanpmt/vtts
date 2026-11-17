"""Pronunciation data per language: lexicons/<lang>/<table>.tsv.

Each file has one entry per line, `key<TAB>reading`, in the order they are applied; lines that
are empty or start with '#' are ignored. Keys are kept exactly (no case folding or stripping);
each table's user documents its matching rule. See docs/frontend/pronunciation-rules.md.
"""

from functools import cache
from pathlib import Path

ROOT = Path(__file__).parent


@cache
def load_table(lang: str, name: str) -> dict[str, str]:
    path = ROOT / lang / f"{name}.tsv"
    table: dict[str, str] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        key, sep, reading = line.partition("\t")
        if not sep or not key or not reading or "\t" in reading:
            raise ValueError(f"{path}:{n}: expected key<TAB>reading")
        if key in table:
            raise ValueError(f"{path}:{n}: duplicate key {key!r}")
        table[key] = reading
    return table
