"""Japanese text (kanji and kana) -> readings -> ja-en tokens.

Readings come from four tables in lexicons/ja/ (built by scripts/frontend/build_ja_lexicon.py
from Open JTalk's dictionary): words.tsv maps a surface form (kanji, possibly mixed with kana:
東京, 食べ, 一日中, の国; and hiragana words pronounced unlike their spelling, such as the
particle は -> ワ) to its reading in katakana, spelled as pronounced (トーキョー);
after_kanji.tsv and after_katakana.tsv hold the readings a key takes right after a kanji or a
katakana word when they differ (人: ヒト, but ジン in 日本人 and アメリカ人; 川: カワ, ガワ after
a kanji); kanji.tsv holds one default reading per kanji.

A run is read by forward longest match at every position (longest key first). After a kanji or
katakana, the matching context table wins over words.tsv when its key is as long or the words.tsv
key is only longer by kana (戦後に: 後 ゴ + に, not 後に ノチニ). No entry starts or ends inside a
katakana run (katakana words are read as written). Where nothing matches, a kanji takes its default
reading (々 repeats the previous kanji's), a kana is read as written and other characters are
skipped. Readings become phonemes through kana.py. No morphological analysis and no model: the C
port is a sorted-table lookup.

Known limits: one reading per key (一日 is イチニチ; ついたち only from the date normalizer),
no rendaku or sound changes beyond the tables, no pitch accent (hook: apply_accent).
"""

from __future__ import annotations

import functools
import unicodedata
from dataclasses import dataclass

from ..lexicons import load_table
from .kana import is_kana, is_katakana, kana_phonemes

MAX_UNIT_MORAE = 10  # longer kana runs are split so the chunk packer can cut them


def is_kanji(ch: str) -> bool:
    """CJK Unified Ideographs plus 〆 and ヶ used as kanji (々 is handled as a repeat mark)."""
    return "一" <= ch <= "鿿" or ch in "〆"


def is_ja_char(ch: str) -> bool:
    return is_kanji(ch) or is_kana(ch) or ch == "々"


CONTEXTS = ("kanji", "katakana")  # previous-character classes with their own tables


def context(text: str, i: int) -> str | None:
    """Class of the character before position i: "kanji", "katakana" or None."""
    if i == 0:
        return None
    prev = text[i - 1]
    if is_kanji(prev) or prev == "々":
        return "kanji"
    if is_katakana(prev):
        return "katakana"
    return None


@dataclass(frozen=True)
class Tables:
    words: dict[str, str]              # surface -> reading
    after: dict[str, dict[str, str]]   # context -> surface -> reading in that context
    kanji: dict[str, str]              # kanji -> default reading
    max_len: int                       # longest key of all word tables

    @staticmethod
    def make(words: dict[str, str], after: dict[str, dict[str, str]] | None = None,
             kanji: dict[str, str] | None = None) -> Tables:
        after = {c: dict((after or {}).get(c, {})) for c in CONTEXTS}
        keys = [*words, *(k for table in after.values() for k in table)]
        return Tables(words, after, kanji or {}, max(map(len, keys), default=1))


@functools.cache
def tables() -> Tables:
    return Tables.make(load_table("ja", "words"),
                       {c: load_table("ja", f"after_{c}") for c in CONTEXTS},
                       load_table("ja", "kanji"))


@dataclass(frozen=True)
class Segment:
    surface: str
    reading: str  # katakana or hiragana; "" when unreadable
    kind: str     # "word" (table), "kanji" (default reading), "kana", "unknown"


def _lookup(text: str, i: int, t: Tables) -> tuple[int, str] | None:
    """Longest table entry starting at i: (length, reading)."""
    # a katakana word is read as written: no entry starts or ends inside a katakana run
    if i > 0 and is_katakana(text[i - 1]) and is_katakana(text[i]):
        return None
    main = _longest(text, i, t.words, t.max_len)
    ctx = context(text, i)
    if ctx is None:
        return main
    after = _longest(text, i, t.after[ctx], t.max_len)
    # a context entry wins over a main entry that is only longer by kana (戦後に: 後 + に)
    if after is not None and (main is None or main[0] <= after[0] or
                              all(is_kana(ch) for ch in text[i + after[0]:i + main[0]])):
        return after
    return main


def _longest(text: str, i: int, table: dict[str, str], max_len: int) -> tuple[int, str] | None:
    for n in range(min(max_len, len(text) - i), 0, -1):
        j = i + n
        if j < len(text) and is_katakana(text[j - 1]) and is_katakana(text[j]):
            continue
        reading = table.get(text[i:j])
        if reading is not None:
            return n, reading
    return None


def segment(text: str, t: Tables | None = None) -> list[Segment]:
    """Forward longest-match segmentation of one Japanese string."""
    t = tables() if t is None else t
    out: list[Segment] = []
    i = 0
    while i < len(text):
        hit = _lookup(text, i, t)
        if hit is not None:
            n, reading = hit
            out.append(Segment(text[i:i + n], reading, "word"))
            i += n
            continue
        ch = text[i]
        if ch == "々":  # repeat the previous kanji (no rendaku)
            last = out[-1] if out else None
            prev = last.surface[-1] if last else ""
            if last is not None and len(last.surface) == 1 and is_kanji(prev):
                r = last.reading  # the reading it just had (人 ヒト + 々 -> ヒトヒト)
            else:
                r = t.kanji.get(prev, "") if is_kanji(prev) else ""
            out.append(Segment(ch, r, "kanji" if r else "unknown"))
        elif is_kanji(ch):
            r = t.kanji.get(ch, "")
            out.append(Segment(ch, r, "kanji" if r else "unknown"))
        elif is_kana(ch):
            if out and out[-1].kind == "kana":
                last = out[-1]
                out[-1] = Segment(last.surface + ch, last.reading + ch, "kana")
            else:
                out.append(Segment(ch, ch, "kana"))
        elif ch.isalpha():
            out.append(Segment(ch, "", "unknown"))
        i += 1
    return apply_accent(out)


def apply_accent(segments: list[Segment]) -> list[Segment]:
    """Hook for pitch accent (version 1 marks none; the model learns it from the audio)."""
    return segments


def ja_reading(text: str) -> str:
    """Reading of a Japanese string as kana (for checks and evaluation)."""
    return "".join(s.reading for s in segment(text))


def ja_phonemes(text: str) -> list[str]:
    """Phonemes (without the JA: prefix) of a Japanese string."""
    return kana_phonemes(ja_reading(text))


def _split_morae(phonemes: list[str], size: int) -> list[list[str]]:
    from .kana import V

    out: list[list[str]] = [[]]
    count = 0
    for p in phonemes:
        if count == size:
            out.append([])
            count = 0
        out[-1].append(p)
        if p in V or p in ("N", "cl"):
            count += 1
    return out


def ja_units(text: str) -> list[list[str]]:
    """ja-en tokens per segment of a Japanese run (a table word, one kanji or a kana run of at
    most MAX_UNIT_MORAE morae); the units of a run are joined without the space token."""
    units: list[list[str]] = []
    prev = ""
    for seg in segment(text):
        ph = kana_phonemes(seg.reading, prev)  # prev: a leading ー repeats the previous vowel
        if not ph:
            continue
        prev = ph[-1]
        for part in _split_morae(ph, MAX_UNIT_MORAE):
            if part:
                units.append([f"JA:{p}" for p in part])
    return units


def unreadable_ja(text: str) -> list[str]:
    """Characters the Japanese front-end skips (kanji without a reading, other scripts), to filter
    training sentences; kana, ASCII (read by the English module), full-width forms and
    punctuation are readable."""
    text = unicodedata.normalize("NFKC", text)
    return [ch for s in segment(text) if s.kind == "unknown" for ch in s.surface
            if not ch.isascii()]
