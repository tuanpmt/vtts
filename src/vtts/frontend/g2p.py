"""Normalized Vietnamese text -> spelling-based tokens -> ids."""

from __future__ import annotations

from .phoneme_set import BOS, EOS, PUNCTUATION, SPACE, token_to_id
from .syllable import Syllable, parse_syllable


def syllable_tokens(s: Syllable) -> list[str]:
    out = []
    if s.onset is not None:
        out.append(f"O:{s.onset}")
    if s.glide:
        out.append("G:w")
    out.append(f"N:{s.nucleus}")
    if s.coda is not None:
        out.append(f"C:{s.coda}")
    out.append(f"T{s.tone}")
    return out


def g2p(normalized: str) -> list[str]:
    """Tokens for normalized text: lowercase syllables and punctuation separated by spaces.

    Syllables are joined by SPACE; a punctuation token replaces the space next to it.
    """
    tokens: list[str] = []
    for item in normalized.split():
        if item in PUNCTUATION:
            if tokens and tokens[-1] == SPACE:
                tokens.pop()
            if tokens:
                tokens.append(item)
            continue
        syl = parse_syllable(item)
        if syl is None:
            raise ValueError(f"not a Vietnamese syllable: {item!r}")
        if tokens and tokens[-1] not in PUNCTUATION:
            tokens.append(SPACE)
        tokens.extend(syllable_tokens(syl))
    return tokens


def encode(tokens: list[str]) -> list[int]:
    return [token_to_id(BOS), *(token_to_id(t) for t in tokens), token_to_id(EOS)]
