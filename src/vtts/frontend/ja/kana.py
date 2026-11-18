"""Kana (hiragana or katakana) -> Japanese phonemes of the ja-en token set.

Table-driven so the C port is a lookup: katakana are first folded to hiragana (code point - 0x60),
then the text is read left to right, a two-kana combination (きゃ, ふぁ, てぃ, ...) before a single
kana. Phoneme names follow Open JTalk: し sh i, ち ch i, つ ts u, ふ f u, じ/ぢ j i, ず/づ z u,
を o, ん N, っ cl.

Long vowels are the vowel repeated: ー repeats the previous vowel (トー -> t o o); a written
vowel kana is read as spelled (とう -> t o u). Readings from the lexicon are stored in the
pronounced form (トーキョー), so the long vowels of kanji words come out right. ゝ ゞ ヽ ヾ repeat
the previous kana (voiced for ゞ ヾ).
"""

from __future__ import annotations

V = ("a", "i", "u", "e", "o")


def _row(cons: str, kana: str, vowels=V) -> dict[str, tuple[str, ...]]:
    return {k: ((cons, v) if cons else (v,)) for k, v in zip(kana, vowels)}


SINGLE: dict[str, tuple[str, ...]] = {}
for _c, _k in (("", "あいうえお"), ("k", "かきくけこ"), ("g", "がぎぐげご"), ("s", "さしすせそ"),
               ("z", "ざじずぜぞ"), ("t", "たちつてと"), ("d", "だぢづでど"), ("n", "なにぬねの"),
               ("h", "はひふへほ"), ("b", "ばびぶべぼ"), ("p", "ぱぴぷぺぽ"), ("m", "まみむめも"),
               ("r", "らりるれろ")):
    SINGLE.update(_row(_c, _k))
SINGLE.update({"し": ("sh", "i"), "じ": ("j", "i"), "ち": ("ch", "i"), "つ": ("ts", "u"),
               "ぢ": ("j", "i"), "づ": ("z", "u"), "ふ": ("f", "u"),
               "や": ("y", "a"), "ゆ": ("y", "u"), "よ": ("y", "o"),
               "わ": ("w", "a"), "ゐ": ("i",), "ゑ": ("e",), "を": ("o",), "ん": ("N",),
               "っ": ("cl",), "ゔ": ("v", "u"),
               # small kana standing alone
               "ぁ": ("a",), "ぃ": ("i",), "ぅ": ("u",), "ぇ": ("e",), "ぉ": ("o",),
               "ゃ": ("y", "a"), "ゅ": ("y", "u"), "ょ": ("y", "o"), "ゎ": ("w", "a"),
               "ゕ": ("k", "a"), "ゖ": ("k", "a")})

PAIRS: dict[str, tuple[str, ...]] = {}
# Palatalized: consonant + small ゃ ゅ ょ (and ぇ for the loanword forms しぇ ちぇ じぇ ...).
for _base, _cons in (("き", "ky"), ("ぎ", "gy"), ("し", "sh"), ("じ", "j"), ("ち", "ch"),
                     ("ぢ", "j"), ("に", "ny"), ("ひ", "hy"), ("び", "by"), ("ぴ", "py"),
                     ("み", "my"), ("り", "ry")):
    PAIRS.update({_base + s: (_cons, v) for s, v in (("ゃ", "a"), ("ゅ", "u"), ("ょ", "o"),
                                                     ("ぇ", "e"))})
# Loanword kana with small vowels.
_SMALL = {"ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o"}
for _base, _cons, _skip in (("ふ", "f", "u"), ("ゔ", "v", "u"), ("つ", "ts", "u"),
                            ("う", "w", "u"), ("て", "t", "e"), ("で", "d", "e"),
                            ("と", "t", "o"), ("ど", "d", "o"), ("す", "s", "u"), ("ず", "z", "u"),
                            ("く", "k w", "u"), ("ぐ", "g w", "u")):
    for _s, _v in _SMALL.items():
        if _v != _skip:
            PAIRS[_base + _s] = (*_cons.split(), _v)
PAIRS.update({"いぇ": ("y", "e"), "ふゅ": ("hy", "u"), "ゔゅ": ("by", "u"),
              "てゅ": ("ty", "u"), "でゅ": ("dy", "u"),
              "とぅ": ("t", "u"), "どぅ": ("d", "u"), "うぅ": ("w", "u")})

ITERATION = {"ゝ": False, "ゞ": True}  # repeat mark -> voiced
_VOICED = dict(zip("かきくけこさしすせそたちつてとはひふへほ", "がぎぐげござじずぜぞだぢづでどばびぶべぼ"))
LONG = "ー"


def to_hiragana(text: str) -> str:
    """Katakana (ァ..ヶ, ヽ ヾ) -> hiragana; everything else unchanged."""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" or c in "ヽヾ" else c for c in text)


def to_katakana(text: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" or c in "ゝゞ" else c for c in text)


def is_katakana(ch: str) -> bool:
    return "ァ" <= ch <= "ヺ" or ch == "ー"


def is_kana(ch: str) -> bool:
    return "ぁ" <= ch <= "ゖ" or "ァ" <= ch <= "ヺ" or ch in "ーゝゞヽヾ"


def kana_phonemes(text: str, prev_phoneme: str = "") -> list[str]:
    """Phonemes (without the JA: prefix) of a kana string; other characters are skipped.
    prev_phoneme is the phoneme before the string (a leading ー repeats it if it is a vowel)."""
    s = to_hiragana(text)
    out: list[str] = []
    if s.startswith(LONG) and prev_phoneme in V:
        out.append(prev_phoneme)
        s = s[1:]
    prev = ""
    i = 0
    while i < len(s):
        pair = PAIRS.get(s[i:i + 2])
        if pair is not None:
            out.extend(pair)
            prev = s[i + 1]
            i += 2
            continue
        ch = s[i]
        if ch in ITERATION and prev:
            ch = _VOICED.get(prev, prev) if ITERATION[ch] else prev
        if ch == LONG:
            if out and out[-1] in V:
                out.append(out[-1])
        elif ch in SINGLE:
            out.extend(SINGLE[ch])
            prev = ch
        i += 1
    return out


def mora_count(phonemes: list[str]) -> int:
    """Morae of a phoneme list: each vowel, N and cl is one mora."""
    return sum(1 for p in phonemes if p in V or p in ("N", "cl"))
