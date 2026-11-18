"""Helpers shared by the normalizers of the Latin-script pair languages (es, id, pt).

Each language writes its own normalize_<lang>() (rules in order, like normalize_ko) and uses these
helpers for what does not depend on the language: number parsing with either decimal mark,
product codes, acronyms and the final split into words and punctuation marks.
"""

from __future__ import annotations

import re
from collections.abc import Callable

MARKS = ",.?!;:"
PAUSE = re.compile(r"…+|\.{3,}|\s[—–-]+\s|—+|–+")
DROP = "“”‘’\"«»()[]{}<>¿¡*_~|"

# A number as written: thousands groups with . or , (1.000.000, 1,000,000), or digits with an
# optional decimal part.
NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"


def parse_number(s: str) -> tuple[int, str | None, str | None]:
    """(integer part, decimal digits or None, decimal mark or None).

    1.000.000 and 1,000,000 are thousands; 1.234,5 and 1,234.5 have both marks; a single group of
    exactly three digits after one mark (1.500, 1,500) is thousands; any other single mark is a
    decimal mark (3,5 3.14 0,05)."""
    s = s.lstrip("+")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):
        a, _, b = s.partition(",")
        return int(a.replace(".", "")), b or None, "," if b else None
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
        a, _, b = s.partition(".")
        return int(a.replace(",", "")), b or None, "." if b else None
    for mark in ",.":
        if mark in s:
            a, b = s.split(mark, 1)
            return int(a or 0), b, mark
    return int(s), None, None


def read_number(s: str, cardinal: Callable[[int], str], marks: dict[str, str],
                digit_names: tuple[str, ...]) -> str:
    """A written number: integer part as a cardinal; a decimal part of one or two digits without a
    leading zero as a cardinal (3,25 -> tres coma veinticinco), else digit by digit."""
    n, frac, mark = parse_number(s)
    out = cardinal(n)
    if frac is not None:
        if len(frac) <= 2 and not frac.startswith("0"):
            out += f" {marks[mark]} {cardinal(int(frac))}"
        else:
            out += f" {marks[mark]} " + " ".join(digit_names[int(c)] for c in frac)
    return out


def digits(s: str, digit_names: tuple[str, ...]) -> str:
    return " ".join(digit_names[int(c)] for c in s if c.isdigit())


def phone_digits(s: str, digit_names: tuple[str, ...], plus: str) -> str:
    """A phone number digit by digit (+ read as plus); fewer than 7 digits in groups (10 20 30) are
    left for the number rules."""
    n = sum(c.isdigit() for c in s)
    if n < 7 and not s.startswith("0"):
        return s
    return f" {plus + ' ' if s.startswith('+') else ''}{digits(s, digit_names)} "


PRODUCT_CODE = re.compile(r"(?<![\w])(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+(?![\w])")


def spell(word: str, letter_names: dict[str, str], digit_names: tuple[str, ...]) -> str:
    """Letters by name and digits one by one (ESP32 -> e ese pe tres dos)."""
    out = []
    for ch in word:
        if ch.isdigit():
            out.append(digit_names[int(ch)])
        elif ch.lower() in letter_names:
            out.append(letter_names[ch.lower()])
    return " ".join(out)


ACRONYM = re.compile(r"(?<![\w])[A-Z]{2,5}(?![\w])")


def acronyms(text: str, letter_names: dict[str, str], words: frozenset[str]) -> str:
    """All-caps words of 2-5 letters are spelled, except those read as words (ONU, OTAN)."""
    def sub(m: re.Match) -> str:
        w = m.group(0)
        return w.lower() if w.lower() in words else spell(w, letter_names, ())
    return ACRONYM.sub(sub, text)


def apply_abbreviations(text: str, table: dict[str, str]) -> str:
    """Case-sensitive keys, longest first, at word boundaries (a key not ending in '.' must not be
    followed by a letter or digit). A key ending in '.' at the end of the text keeps the full
    stop (... etc. -> etcétera .)."""
    for key in sorted(table, key=len, reverse=True):
        tail = "" if key.endswith(".") else r"(?![\w])"
        reading = table[key]

        def sub(m: re.Match, reading=reading, key=key) -> str:
            end = key.endswith(".") and not m.string[m.end():].strip()
            return f" {reading} {'.' if end else ''}"

        text = re.sub(r"(?<![\w])" + re.escape(key) + tail, sub, text)
    return text


WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*|[,.?!;:]")


def finish(text: str) -> str:
    """Lower-case words and the marks , . ? ! ; : separated by single spaces; a mark right after
    another mark is dropped (a leading mark is kept: text.py drops marks that follow nothing)."""
    out: list[str] = []
    for w in WORD.findall(text.lower()):
        if w in MARKS and out and out[-1] in MARKS:
            continue
        out.append(w)
    return " ".join(out)
