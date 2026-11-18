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


def text_to_ids(text: str, lang: str | None = None) -> list[list[int]]:
    """lang=None: phoneme set v1 (Vietnamese only, unchanged); "vi" | "en" | "auto": set v2
    (vi-en); "zh": token set zh-en (Mandarin + English, ids 0..106 shared with v2)."""
    if lang is None:
        return [encode(g2p(chunk)) for chunk in split_sentences(text)]
    from .phoneme_set import BOS, EOS, token_to_id_v2, token_to_id_zhen

    to_id = token_to_id_zhen if lang == "zh" else token_to_id_v2
    return [[to_id(BOS), *(to_id(t) for t in toks), to_id(EOS)]
            for toks in text_to_tokens(text, lang)]


# ---------------- bilingual (phoneme set v2) ----------------

_V2_MAX_WORDS = 40
_V2_MAX_TOKENS = 318  # + BOS/EOS <= VTTS_TEXT_MAX_IDS (320)


def _items(sentence: str, mode: str) -> list[tuple[str, list[str]]]:
    """("w", tokens) per word and ("p", [mark]) per punctuation mark, in order. A language
    written without spaces (word_units) gives ("w", ...) for the first syllable of a run and
    ("s", ...) for the following ones, which are joined without SPACE."""
    from .lang import runs
    from .languages import LANGUAGES

    items: list[tuple[str, list[str]]] = []
    for text, lang in runs(sentence, mode):
        module = LANGUAGES[lang]
        for w in module.normalize(text).split():
            if w in PUNCTUATION:
                if items and items[-1][0] != "p":
                    items.append(("p", [w]))
                continue
            if module.word_units is not None:
                units = [u for u in module.word_units(w) if u]
                items.extend(("w" if k == 0 else "s", u) for k, u in enumerate(units))
                continue
            toks = module.word_tokens(w)
            if toks:
                items.append(("w", toks))
    return items


def _assemble(items: list[tuple[str, list[str]]]) -> list[str]:
    out: list[str] = []
    for kind, toks in items:
        if kind == "p":
            if out:
                out.extend(toks)
        elif kind == "s":
            out.extend(toks)
        else:
            if out and out[-1] not in PUNCTUATION:
                out.append(" ")
            out.extend(toks)
    return out


def _pack_items(items: list[tuple[str, list[str]]]) -> list[list[tuple[str, list[str]]]]:
    def size(part):
        return len(_assemble(part)), sum(1 for k, _ in part if k != "p")

    pieces: list[list] = [[]]
    for it in items:
        pieces[-1].append(it)
        if it[0] == "p" and it[1][0] in _SOFT_BREAKS:
            pieces.append([])
    out: list[list] = []
    cur: list = []
    for piece in filter(None, pieces):
        n_tok, n_w = size(cur + piece)
        if n_tok <= _V2_MAX_TOKENS and n_w <= _V2_MAX_WORDS:
            cur += piece
            continue
        if cur:
            out.append(cur)
            cur = []
        for it in piece:  # hard cut a piece that is too long on its own
            n_tok, n_w = size(cur + [it])
            if cur and (n_tok > _V2_MAX_TOKENS or n_w > _V2_MAX_WORDS):
                out.append(cur)
                cur = []
            cur.append(it)
    if cur:
        out.append(cur)
    return out


def text_to_tokens(text: str, lang: str = "vi") -> list[list[str]]:
    """Tokens per chunk (no BOS/EOS); lang is "vi", "en" or "auto" (set v2) or "zh" (zh-en)."""
    from .lang import split_sentences_raw

    chunks: list[list[str]] = []
    for sentence in split_sentences_raw(text):
        for part in _pack_items(_items(sentence, lang)):
            toks = _assemble(part)
            if any(t not in PUNCTUATION for t in toks):
                chunks.append(toks)
    return chunks
