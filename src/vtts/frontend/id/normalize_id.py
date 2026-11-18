"""Indonesian text normalization for one Indonesian run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces. The e of "enak" may come out as é (letter names, e.g.
"é" for E), which g2p_id reads as that e.

Rules, in order: abbreviations (dll., Jl., No.), quotes and brackets dropped, dates (17/08/1945,
2026-11-18), times (pukul 14.30, 07:00), phone numbers (digit by digit), money (Rp50.000,
Rp 1,5 juta, $5), percentages, units after a number (5 km, 25 °C), ordinals (ke-3 -> ketiga,
ke-1 -> pertama), ranges (10-20 -> sepuluh sampai dua puluh), pause marks, product codes (ESP32:
letters by Indonesian name, digits one by one), numbers (1.250.000 or 1,5), informal
reduplication (anak2 -> anak anak), symbols, acronyms (spelled: KTP -> ka té pé; a few read as
words: ASEAN, NATO).
"""

from __future__ import annotations

import re

from ..latin_norm import (
    DROP,
    NUM,
    PAUSE,
    PRODUCT_CODE,
    acronyms,
    apply_abbreviations,
    digits,
    finish,
    phone_digits,
    read_number,
    spell,
)

ONES = ("nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan")
SCALES = ((10 ** 12, "triliun"), (10 ** 9, "miliar"), (10 ** 6, "juta"))
MONTHS = ("", "januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus",
          "september", "oktober", "november", "desember")
LETTERS = {"a": "a", "b": "bé", "c": "cé", "d": "dé", "e": "é", "f": "éf", "g": "gé", "h": "ha",
           "i": "i", "j": "jé", "k": "ka", "l": "él", "m": "ém", "n": "én", "o": "o", "p": "pé",
           "q": "ki", "r": "ér", "s": "és", "t": "té", "u": "u", "v": "fé", "w": "wé", "x": "éks",
           "y": "yé", "z": "zét"}
ACRONYM_WORDS = frozenset(("asean", "nato", "opec", "bulog", "pemilu", "golput", "covid", "pin",
                           "ram", "rom", "led", "sim"))
ABBREVIATIONS = {
    "dll.": "dan lain lain", "dsb.": "dan sebagainya", "dst.": "dan seterusnya",
    "Jl.": "jalan", "No.": "nomor", "no.": "nomor", "Bpk.": "bapak", "Dr.": "doktor",
    "Prof.": "profesor", "a.n.": "atas nama", "s.d.": "sampai dengan", "tsb.": "tersebut",
    "yg": "yang", "dgn": "dengan", "tdk": "tidak", "utk": "untuk", "krn": "karena",
    "Kab.": "kabupaten", "Kec.": "kecamatan", "Tbk.": "terbuka", "PT.": "pé té",
}
UNITS = {"km/jam": "kilometer per jam", "km/h": "kilometer per jam", "km": "kilometer",
         "m": "meter", "cm": "sentimeter", "mm": "milimeter", "kg": "kilogram", "g": "gram",
         "mg": "miligram", "l": "liter", "L": "liter", "ml": "mililiter", "GB": "gigabita",
         "MB": "megabita", "TB": "terabita", "kWh": "kilowatt jam", "kW": "kilowatt",
         "W": "watt", "V": "volt", "mAh": "miliampere jam", "GHz": "gigahertz",
         "MHz": "megahertz", "ha": "hektare", "°C": "derajat celsius", "℃": "derajat celsius",
         "°": "derajat"}
CURRENCY = {"Rp.": "rupiah", "Rp": "rupiah", "US$": "dolar", "$": "dolar", "€": "euro",
            "£": "pound", "¥": "yen"}
SYMBOLS = {"&": " dan ", "+": " tambah ", "=": " sama dengan ", "@": " et ", "#": " nomor ",
           "×": " kali ", "/": " per ", "%": " persen "}
MARK_WORDS = {",": "koma", ".": "titik"}

_A = r"(?<![\w.,])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])"
                  r"|(?<=pukul )([01]?\d|2[0-4])\.([0-5]\d)(?![\d.])"
                  r"|(?<=jam )([01]?\d|2[0-4])\.([0-5]\d)(?![\d.])", re.IGNORECASE)
PHONE = re.compile(r"(?<![\d])(?:\+\d{1,3}[\s-])?\d{2,4}(?:[\s-]\d{2,4}){2,4}(?![\d])"
                   r"|(?<![\d.,])0\d{2,}(?![\d]|[.,]\d)")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")(\s?(?:ribu|juta|miliar|triliun))?")
MONEY_AFTER = re.compile(_A + r"(" + NUM + r")\s?(€|£|¥|\$)")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(r"(?<![\w])[Kk]e-?(\d+)(?![\d])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])")
REDUP = re.compile(r"\b([^\W\d_]{2,})2\b")


def _below_1000(n: int) -> str:
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts.append("seratus" if h == 1 else f"{ONES[h]} ratus")
    if r >= 20:
        t, u = divmod(r, 10)
        parts.append(f"{ONES[t]} puluh" + (f" {ONES[u]}" if u else ""))
    elif r >= 12:
        parts.append(f"{ONES[r - 10]} belas")
    elif r == 11:
        parts.append("sebelas")
    elif r == 10:
        parts.append("sepuluh")
    elif r:
        parts.append(ONES[r])
    return " ".join(parts)


def cardinal(n: int) -> str:
    """Indonesian cardinal: 11 -> sebelas, 100 -> seratus, 1000 -> seribu, 2_500_000 -> dua juta
    lima ratus ribu."""
    if n < 0:
        return "minus " + cardinal(-n)
    if n == 0:
        return "nol"
    if n >= 10 ** 15:
        return digits(str(n), ONES)
    parts = []
    for scale, name in SCALES:
        q, n = divmod(n, scale)
        if q:
            parts.append(f"{cardinal(q)} {name}")
    th, n = divmod(n, 1000)
    if th == 1:
        parts.append("seribu")
    elif th:
        parts.append(f"{_below_1000(th)} ribu")
    if n:
        parts.append(_below_1000(n))
    return " ".join(parts)


def ordinal(n: int) -> str:
    """1 -> pertama, 3 -> ketiga, 21 -> kedua puluh satu."""
    return "pertama" if n == 1 else "ke" + cardinal(n)


def number(s: str) -> str:
    return ("minus " if s.startswith("-") else "") + read_number(s.lstrip("-"), cardinal,
                                                                  MARK_WORDS, ONES)


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{cardinal(d)} {MONTHS[m]}"
    if y is not None:
        out += f" {cardinal(int(y) + (2000 if len(y) == 2 else 0))}"
    return f" {out} "


def _time(m: re.Match) -> str:
    g = [x for x in m.groups() if x is not None]
    h, mi = int(g[0]), int(g[1])
    sec = int(g[2]) if len(g) > 2 else 0
    out = cardinal(h) + (f" lewat {cardinal(mi)} menit" if mi else "")
    if sec:
        out += f" {cardinal(sec)} detik"
    return f" {out} "


def _money_before(m: re.Match) -> str:
    cur, num, scale = m.groups()
    return f" {number(num)}{' ' + scale.strip() if scale else ''} {CURRENCY[cur]} "


def normalize_id(text: str) -> str:
    t = apply_abbreviations(text, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = TIME.sub(_time, t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), ONES, "plus"), t)
    t = MONEY_BEFORE.sub(_money_before, t)
    t = MONEY_AFTER.sub(lambda m: f" {number(m.group(1))} {CURRENCY[m.group(2)]} ", t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} persen ", t)
    t = UNIT.sub(lambda m: f" {number(m.group(1) + m.group(2))} {UNITS[m.group(3)]} ", t)
    t = ORDINAL.sub(lambda m: f" {ordinal(int(m.group(1)))} ", t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} sampai {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, ONES)} ", t)
    t = NUMBER.sub(lambda m: f" {number(m.group(1) + m.group(2))} ", t)
    t = REDUP.sub(r"\1 \1", t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    return finish(t)
