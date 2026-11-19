"""Normalization for scripts written without spaces between words (Khmer, Burmese).

One engine, parametrized per language by a Spec (km/normalize_km.py, my/normalize_my.py); the
passes and their regular expressions follow th/normalize_th.py (the C port, runtime/src/
vtts_text_nsp.c, mirrors them pass by pass). Output: words and the punctuation tokens , . ? ! ; :
separated by single spaces. A "word" is a run of the script's letters (numbers become number words
inside it) or a lower-case Latin word that the English module reads.

Passes, in order: the language's own pass (pre: Zawgyi conversion for Burmese, zero-width
spaces dropped); native digits and full-width forms to ASCII;
native punctuation to , . : (punct); pause marks (… — – ...) to a comma; quotes and brackets
dropped; dotted abbreviations (glued); the repetition mark joined to the word before it; product
codes (letters in English, digits one by one); dates (19/11/2026, 2026-11-19); times (14:30,
14:30:05); money before (symbol + number) and after (number + symbol) a number; percentages;
units after a number; phone numbers (digit by digit); ranges (10-20); negative numbers; digit
strings with a leading 0 or of 8 or more digits (one by one); other numbers (integers, grouped
thousands, decimals); symbols; Latin words through the English normalizer. Number words are
glued (no spaces next to them). With space_pause, a space between two runs of the script is read
as a pause (" , "), as Thai.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

GLUE = "\x01"  # number words: spaces next to them are dropped
_FULLWIDTH = {c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)}
DROP = "“”‘’\"«»「」『』()[]{}<>·•"
_PAUSE = re.compile(r"…+|—+|–(?!\d)|\.{3,}")
_A = r"(?<![A-Za-z0-9])"
_Z = r"(?![A-Za-z0-9])"
NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
PRODUCT_CODE = re.compile(_A + r"(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+" + _Z)
DATE_DMY = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])")
PERCENT = re.compile(r"(-?)(" + NUM + r")\s?%")
RANGE = re.compile(r"(?<![\d.,])(" + NUM + r")\s?[-–]\s?(?=\d)")
NEGATIVE = re.compile(r"(?<![\w\d])-(?=\d)")
PHONE = re.compile(r"(?<![\d.,-])(?:\+\d{1,3}[\s-]?)?0?\d{1,2}(?:[\s-]\d{3,4}){2}(?![\d-])"
                   r"|(?<![\d.,-])0\d{1,2}-\d{3,4}-?\d{0,4}(?![\d-])")
LONG_DIGITS = re.compile(r"(?<![\d.,])(?:0\d{2,}|\d{8,})(?![\d.,]\d)")
NUMBER = re.compile(r"(?<![\d.,])(" + NUM + r")(?![\d])")
SYMBOL_KEYS = ("+", "=", "&", "@", "×")


@dataclass(frozen=True)
class Spec:
    """Language data for the engine. Number words, units, currencies, months and abbreviations
    are written in the language; `letters` is the regex class of the script's letters and signs."""

    lang: str
    letters: str                       # e.g. "ក-៝" (a regex character class body)
    digit0: int                        # code point of the native digit zero
    cardinal: Callable[[int], str]
    digit_words: tuple[str, ...]       # 0..9
    point: str                         # decimal point word
    minus: str
    to: str                            # range word, after the first number
    percent: str                       # after the number
    currency: dict[str, str]           # symbol before or after a number -> word after the number
    units: dict[str, str]
    date: Callable[[int, int, str], str]   # day, month, year digits -> words
    time: Callable[[int, int, int], str]   # hour, minute, second (0 none) -> words
    symbols: dict[str, str]            # each of SYMBOL_KEYS -> words (" and ", " at ": English)
    abbreviations: dict[str, str] = field(default_factory=dict)  # dotted, e.g. គ.ម.
    punct: dict[str, str] = field(default_factory=dict)          # native marks -> , . :
    repeat: str = ""                   # repetition mark joined to the word before it (ៗ)
    space_pause: bool = False          # a space between two runs of the script is a pause
    pre: Callable[[str], str] | None = None  # language pass before the digits
    dedupe: tuple[str, ...] = ()       # a word written before a reading that starts with it


class Normalizer:
    def __init__(self, spec: Spec) -> None:
        self.s = spec
        L = spec.letters
        self.digits_table = {spec.digit0 + k: ord("0") + k for k in range(10)}
        keys = "".join(re.escape(c) for c in spec.currency)
        self.money_before = re.compile(r"([" + keys + r"])\s?(" + NUM + r")")
        self.money_after = re.compile(r"(?<![\d.,])(" + NUM + r")\s?([" + keys + r"])")
        unit_keys = "|".join(re.escape(u) for u in sorted(spec.units, key=len, reverse=True))
        self.unit = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")\s?(" + unit_keys + r")(?![A-Za-z])")
        dotted = [k for k in sorted(spec.abbreviations, key=len, reverse=True)]
        self.abbrev = re.compile(r"(?<![" + L + r".])(?:" + "|".join(re.escape(k) for k in dotted)
                                 + ")") if dotted else None
        self.script_space = re.compile(r"(?<=[" + L + r"])\s+(?=[" + L + r"])")
        self.words = re.compile(r"[" + L + r"]+|[a-z][a-z']*|[,.?!;:]")
        if spec.repeat:
            self.repeat = re.compile(r"\s*" + re.escape(spec.repeat) + r"\s*")

    # ---- numbers ----
    def digits(self, s: str) -> str:
        return "".join(self.s.digit_words[int(c)] for c in s if c.isdigit())

    def number(self, s: str) -> str:
        s = s.replace(",", "")
        neg = s.startswith("-")
        s = s.lstrip("-")
        if "." in s:
            a, b = s.split(".", 1)
            out = self.s.cardinal(int(a or 0)) + self.s.point + self.digits(b)
        else:
            out = self.s.cardinal(int(s))
        return (self.s.minus if neg else "") + out

    def _date(self, d: int, m: int, y: str) -> str | None:
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        return _g(self.s.date(d, m, y))

    def _time(self, m: re.Match) -> str:
        return _g(self.s.time(int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)))

    def _code(self, m: re.Match) -> str:
        return " " + re.sub(r"[A-Z]|[0-9]+", lambda p: f" {p.group(0).lower()} " if p.group(0).isalpha()
                            else _g(self.digits(p.group(0))), m.group(0)) + " "

    def __call__(self, text: str) -> str:
        s = self.s
        t = s.pre(text) if s.pre is not None else text
        t = t.translate(self.digits_table).translate(_FULLWIDTH)
        for k, v in s.punct.items():
            t = t.replace(k, v)
        t = _PAUSE.sub(" , ", t)
        t = t.translate({ord(c): " " for c in DROP})
        if self.abbrev is not None:
            t = self.abbrev.sub(lambda m: _g(s.abbreviations[m.group(0)]), t)
        if s.repeat:
            t = self.repeat.sub(s.repeat, t)
        t = PRODUCT_CODE.sub(self._code, t)
        t = DATE_DMY.sub(lambda m: self._date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
        t = DATE_ISO.sub(lambda m: self._date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
        t = TIME.sub(self._time, t)
        t = self.money_before.sub(lambda m: _g(self.number(m.group(2)) + s.currency[m.group(1)]), t)
        t = self.money_after.sub(lambda m: _g(self.number(m.group(1)) + s.currency[m.group(2)]), t)
        t = PERCENT.sub(lambda m: _g((s.minus if m.group(1) else "") + self.number(m.group(2)) + s.percent), t)
        t = self.unit.sub(lambda m: _g((s.minus if m.group(1) else "") + self.number(m.group(2))
                                       + s.units[m.group(3)]), t)
        t = PHONE.sub(lambda m: _g(self.digits(m.group(0))), t)
        t = RANGE.sub(lambda m: _g(self.number(m.group(1)) + s.to), t)
        t = NEGATIVE.sub(_g(s.minus), t)
        t = LONG_DIGITS.sub(lambda m: _g(self.digits(m.group(0))), t)
        t = NUMBER.sub(lambda m: _g(self.number(m.group(1))), t)
        for k in SYMBOL_KEYS:
            v = s.symbols[k]
            t = t.replace(k, _g(v) if v.strip() == v else v)
        t = re.sub(r"[A-Za-z][A-Za-z']*", _latin, t)
        t = re.sub(r"\s*" + GLUE + r"\s*", GLUE, t)
        for w in s.dedupe:  # ថ្ងៃទី 19/11/2026: the date reading starts with ថ្ងៃទី again
            t = t.replace(w + GLUE + w, GLUE + w)
        if s.space_pause:
            t = self.script_space.sub(" , ", t)
        t = t.replace(GLUE, "")
        out: list[str] = []
        for w in self.words.findall(t):
            if w in ",.?!;:":
                # A leading mark is kept: it may follow an English word of the previous run;
                # text.py drops marks that follow nothing.
                if not out or out[-1] not in ",.?!;:":
                    out.append(w)
            else:
                out.append(w)
        return " ".join(out)


def _g(text: str) -> str:
    return GLUE + text + GLUE


def _latin(m: re.Match) -> str:
    from .en.normalize_en import normalize_en

    return f" {normalize_en(m.group(0))} "
