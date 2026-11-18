"""Numbered pinyin syllable -> zh-en tokens [ZI:initial] ZF:final ZTtone.

Input is pinyin with a tone digit 1-5 (5 = neutral) and "v" for u-umlaut: "zhong1", "lv3",
"yuan2". Spelling abbreviations are undone so each final has one token: y/w are not initials
(yi -> i, wu -> u, you -> iou, wei -> uei, yun -> vn), u after j/q/x is u-umlaut (ju -> v),
iu/ui/un after an initial are iou/uei/uen, and the "i" after zh/ch/sh/r and z/c/s is the apical
vowel (ii, i0). Interjection syllables without a regular final (m, n, ng, hm, hng, yo,
e-circumflex) map to the nearest regular syllable so they need no rarely-trained tokens.
"""

from __future__ import annotations

import functools

from ..phoneme_set import ZH_FINALS, ZH_INITIALS

_INITIALS_LONG_FIRST = sorted(ZH_INITIALS, key=len, reverse=True)
_FINALS = frozenset(ZH_FINALS)
_RETROFLEX = ("zh", "ch", "sh", "r")
_DENTAL = ("z", "c", "s")
_ABBREVIATED = {"iu": "iou", "ui": "uei", "un": "uen"}

# Interjections: written syllable -> (initial, final).
SPECIAL = {"m": ("m", "u"), "n": ("", "en"), "ng": ("", "eng"), "hm": ("h", "en"),
           "hng": ("h", "eng"), "ê": ("", "ei"), "yo": ("", "iou")}


def split_syllable(base: str) -> tuple[str, str] | None:
    """Toneless pinyin -> (initial or "", final in full form); None if not a valid syllable."""
    s = base.replace("ü", "v")
    if s in SPECIAL:
        return SPECIAL[s]
    if not s.isalpha() or "ii" in s:  # the tokens ii/i0 are never written
        return None
    if s.startswith("y"):
        rest = s[1:]
        if rest.startswith(("u", "v")):
            fin = "v" + rest[1:]
        elif rest.startswith("i"):
            fin = rest
        else:
            fin = "iou" if rest == "ou" else "i" + rest
        return ("", fin) if fin in _FINALS else None
    if s.startswith("w"):
        rest = s[1:]
        fin = rest if rest.startswith("u") else "u" + rest
        return ("", fin) if fin in _FINALS else None
    ini = next((i for i in _INITIALS_LONG_FIRST if s.startswith(i)), "")
    fin = s[len(ini):]
    if ini in ("j", "q", "x") and fin.startswith("u"):
        fin = "v" + fin[1:]
    elif ini and fin in _ABBREVIATED:
        fin = _ABBREVIATED[fin]
    elif fin == "i" and ini in _RETROFLEX:
        fin = "ii"
    elif fin == "i" and ini in _DENTAL:
        fin = "i0"
    if fin not in _FINALS:
        return None
    if ini in ("j", "q", "x") and not fin.startswith(("i", "v")):
        return None
    if fin.startswith("v") and ini not in ("n", "l", "j", "q", "x"):
        return None
    return ini, fin


@functools.lru_cache(maxsize=4096)
def _tokens(syllable: str) -> tuple[str, ...] | None:
    if len(syllable) < 2 or syllable[-1] not in "12345":
        return None
    parts = split_syllable(syllable[:-1])
    if parts is None:
        return None
    ini, fin = parts
    return ((f"ZI:{ini}",) if ini else ()) + (f"ZF:{fin}", f"ZT{syllable[-1]}")


def syllable_tokens(syllable: str) -> list[str] | None:
    """Tokens of one numbered pinyin syllable ("hang2" -> ZI:h ZF:ang ZT2); None if invalid."""
    toks = _tokens(syllable)
    return list(toks) if toks is not None else None
