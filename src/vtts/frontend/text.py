"""Sentence chunking and the top-level text -> ids entry point."""

from __future__ import annotations

from .g2p import encode, g2p
from .normalize import normalize
from .phoneme_set import PUNCTUATION

_TERMINATORS = (".", "!", "?", ";")
_SOFT_BREAKS = (",", ":")


def _count(words: list[str]) -> int:
    return sum(1 for w in words if w not in PUNCTUATION)


def _pack(words: list[str], max_syllables: int) -> list[list[str]]:
    """Split one sentence at commas, packing pieces up to max_syllables; hard-cut longer pieces."""
    pieces: list[list[str]] = [[]]
    for w in words:
        pieces[-1].append(w)
        if w in _SOFT_BREAKS:
            pieces.append([])
    out: list[list[str]] = []
    cur: list[str] = []
    for piece in filter(None, pieces):
        if _count(piece) > max_syllables:
            if cur:
                out.append(cur)
                cur = []
            buf: list[str] = []
            for w in piece:
                if w not in PUNCTUATION and _count(buf) == max_syllables:
                    out.append(buf)
                    buf = []
                buf.append(w)
            cur = buf
        elif _count(cur) + _count(piece) > max_syllables:
            out.append(cur)
            cur = list(piece)
        else:
            cur.extend(piece)
    if cur:
        out.append(cur)
    return out


def split_sentences(text: str, max_syllables: int = 40) -> list[str]:
    """Normalize and split into chunks of at most max_syllables syllables each."""
    words = normalize(text).split()
    sentences: list[list[str]] = [[]]
    for w in words:
        sentences[-1].append(w)
        if w in _TERMINATORS:
            sentences.append([])
    chunks: list[str] = []
    for sent in sentences:
        if _count(sent) == 0:
            continue
        for part in _pack(sent, max_syllables):
            if _count(part):
                chunks.append(" ".join(part))
    return chunks


def text_to_ids(text: str) -> list[list[int]]:
    return [encode(g2p(chunk)) for chunk in split_sentences(text)]
