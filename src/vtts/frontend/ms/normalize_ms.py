"""Malay (Malaysian standard, Bahasa Melayu) text normalization for one Malay run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces. The e of "elok" may come out as é (letter names, e.g. "ké"
for K), which g2p_ms reads as that e.

Shared with Indonesian (id/normalize_id.py): the 1-999 reading (with Malay digit names), the date,
phone, ordinal (ke-3) and reduplication (anak2) patterns. Malay differs in: lapan (8), sejuta,
bilion, sifar for the number 0 and kosong for a digit read alone, the decimal point read
"perpuluhan" with the decimals digit by digit, Malaysian number marks (1,250.50: comma for
thousands, point for decimals; 1.000.000 with several dot groups is still thousands), ringgit and
sen (RM12.50 -> dua belas ringgit lima puluh sen), peratus, darjah selsius, hingga for ranges,
Malay month names and their abbreviations (19 Nov 2026), times (pukul 8.30 pagi -> pukul lapan
tiga puluh minit pagi) and Malay abbreviations (Jln., En., Pn., Sdn. Bhd., Kg.). Letter names
follow the English alphabet as Malaysians spell acronyms (KTM -> ké ti ém).
"""

from __future__ import annotations

import re

from ..id.normalize_id import DATE_DMY, DATE_ISO, ORDINAL, PHONE, REDUP, _below_1000
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
    spell,
)

ONES = ("kosong", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "lapan", "sembilan")
ZERO = "sifar"
SCALES = ((10 ** 12, "trilion"), (10 ** 9, "bilion"), (10 ** 6, "juta"))
MONTHS = ("", "januari", "februari", "mac", "april", "mei", "jun", "julai", "ogos", "september",
          "oktober", "november", "disember")
MONTH_ABBR = {"jan": 1, "feb": 2, "mac": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "ogo": 8,
              "ogos": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dis": 12}
LETTERS = {"a": "éi", "b": "bi", "c": "si", "d": "di", "e": "i", "f": "éf", "g": "ji", "h": "éic",
           "i": "ai", "j": "jé", "k": "ké", "l": "él", "m": "ém", "n": "én", "o": "o", "p": "pi",
           "q": "kiu", "r": "ar", "s": "és", "t": "ti", "u": "yu", "v": "vi", "w": "dabelyu",
           "x": "éks", "y": "wai", "z": "zéd"}
ACRONYM_WORDS = frozenset(("asean", "nato", "opec", "umno", "mara", "felda", "felcra", "risda",
                           "covid", "pin", "ram", "rom", "petronas", "proton", "unesco", "unicef"))
ABBREVIATIONS = {
    "dll.": "dan lain lain", "dsb.": "dan sebagainya", "dst.": "dan seterusnya",
    "Jln.": "jalan", "Jl.": "jalan", "No.": "nombor", "no.": "nombor", "Bil.": "bilangan",
    "Dr.": "doktor", "Prof.": "profesor", "En.": "encik", "Pn.": "puan", "Tn.": "tuan",
    "Cik.": "cik", "Hj.": "haji", "Hjh.": "hajah", "Sdn. Bhd.": "sendirian berhad",
    "Sdn Bhd": "sendirian berhad", "Bhd.": "berhad", "Kg.": "kampung", "Kpg.": "kampung",
    "Sg.": "sungai", "Bkt.": "bukit", "Tg.": "tanjung", "Tmn.": "taman", "Sek.": "seksyen",
    "m.s.": "muka surat", "hlm.": "halaman", "lwn.": "lawan", "YB": "yang berhormat",
    "YAB": "yang amat berhormat", "yg": "yang", "dgn": "dengan", "tdk": "tidak", "utk": "untuk",
    "krn": "kerana", "kpd": "kepada", "drpd": "daripada", "sbg": "sebagai", "spt": "seperti",
    "bkn": "bukan",
}
UNITS = {"km/j": "kilometer sejam", "km/jam": "kilometer sejam", "km/h": "kilometer sejam",
         "km": "kilometer", "m": "meter", "cm": "sentimeter", "mm": "milimeter", "kg": "kilogram",
         "g": "gram", "mg": "miligram", "l": "liter", "L": "liter", "ml": "mililiter",
         "GB": "gigabait", "MB": "megabait", "TB": "terabait", "kWj": "kilowatt jam",
         "kWh": "kilowatt jam", "kW": "kilowatt", "W": "watt", "V": "volt",
         "mAh": "miliampere jam", "GHz": "gigahertz", "MHz": "megahertz", "ha": "hektar",
         "°C": "darjah selsius", "℃": "darjah selsius", "°": "darjah"}
CURRENCY = {"RM": "ringgit", "US$": "dolar amerika", "S$": "dolar singapura", "$": "dolar",
            "€": "euro", "£": "paun", "¥": "yen", "Rp": "rupiah"}
SYMBOLS = {"&": " dan ", "+": " tambah ", "=": " sama dengan ", "@": " di ", "#": " nombor ",
           "×": " darab ", "/": " per ", "%": " peratus "}
POINT = "perpuluhan"

# A number in Malaysian or Indonesian style: 1,250.50 / 1.000.000 / 3.5 / 3,5.
_A = r"(?<![\w.,])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
_DAY_PART = r"(?=\s+(?:pagi|tengah hari|tengah malam|petang|malam|waktu))"
TIME = re.compile(r"(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])"
                  r"|(?<=pukul )([01]?\d|2[0-4])\.([0-5]\d)(?![\d.])"
                  r"|(?<=jam )([01]?\d|2[0-4])\.([0-5]\d)(?![\d.])"
                  r"|(?<![\d.,])([01]?\d|2[0-4])\.([0-5]\d)(?![\d.])" + _DAY_PART, re.IGNORECASE)
DATE_ABBR = re.compile(r"(?<![\d])(\d{1,2})\s+(" + "|".join(sorted(MONTH_ABBR, key=len, reverse=True))
                       + r"|" + "|".join(m for m in MONTHS if m) + r")\.?(?:\s+(\d{4}))?(?![\w])",
                       re.IGNORECASE)
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")(\s?(?:ribu|juta|bilion|trilion))?")
MONEY_AFTER = re.compile(_A + r"(" + NUM + r")\s?(€|£|¥|\$)")
SEN = re.compile(_A + r"(" + NUM + r")\s?sen(?![\w])")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])")


def cardinal(n: int) -> str:
    """Malay cardinal: 8 -> lapan, 11 -> sebelas, 100 -> seratus, 1000 -> seribu,
    1_000_000 -> sejuta, 2_500_000 -> dua juta lima ratus ribu, 10**9 -> satu bilion."""
    if n < 0:
        return "negatif " + cardinal(-n)
    if n == 0:
        return ZERO
    if n >= 10 ** 15:
        return digits(str(n), ONES)
    parts = []
    for scale, name in SCALES:
        q, n = divmod(n, scale)
        if q == 1 and name == "juta":
            parts.append("sejuta")
        elif q:
            parts.append(f"{cardinal(q)} {name}")
    th, n = divmod(n, 1000)
    if th == 1:
        parts.append("seribu")
    elif th:
        parts.append(f"{_below_1000(th, ONES)} ribu")
    if n:
        parts.append(_below_1000(n, ONES))
    return " ".join(parts)


def ordinal(n: int) -> str:
    """1 -> pertama, 3 -> ketiga, 21 -> kedua puluh satu."""
    return "pertama" if n == 1 else "ke" + cardinal(n)


def parse_number(s: str) -> tuple[int, str | None]:
    """(integer part, decimal digits or None) in Malaysian style: a comma before groups of three
    digits is a thousands mark and the point a decimal mark (1,250.50; 3.14); several dot groups
    are thousands (1.000.000); a single comma not before three digits is a decimal mark (3,5)."""
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
        a, _, b = s.partition(".")
        return int(a.replace(",", "")), b or None
    if re.fullmatch(r"\d{1,3}(\.\d{3}){2,}(,\d+)?", s):
        a, _, b = s.partition(",")
        return int(a.replace(".", "")), b or None
    for mark in ".,":
        if mark in s:
            a, b = s.split(mark, 1)
            return int(a.replace(",", "") or 0), b  # 1,500.300.200: a comma group before the point
    return int(s), None


def number(s: str) -> str:
    """A written number; decimals digit by digit after perpuluhan (3.14 -> tiga perpuluhan satu
    empat)."""
    neg = s.startswith("-")
    n, frac = parse_number(s.lstrip("-+"))
    out = cardinal(n)
    if frac:
        out += f" {POINT} {digits(frac, ONES)}"
    return ("negatif " if neg else "") + out


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{cardinal(d)} {MONTHS[m]}"
    if y is not None:
        out += f" {cardinal(int(y) + (2000 if len(y) == 2 else 0))}"
    return f" {out} "


def _date_abbr(m: re.Match) -> str:
    key = m.group(2).lower()  # re.IGNORECASE also matches letters whose lower() is not ASCII (ſ, İ)
    month = MONTH_ABBR.get(key) or (MONTHS.index(key) if key in MONTHS else 0)
    return _date(int(m.group(1)), month, m.group(3)) or m.group(0)


def _time(m: re.Match) -> str:
    g = [x for x in m.groups() if x is not None]
    h, mi = int(g[0]), int(g[1])
    sec = int(g[2]) if len(g) > 2 else 0
    out = cardinal(h) + (f" {cardinal(mi)} minit" if mi else "")
    if sec:
        out += f" {cardinal(sec)} saat"
    return f" {out} "


def _ringgit(num: str, scale: str | None, name: str) -> str:
    """RM12.50 -> dua belas ringgit lima puluh sen; RM0.50 -> lima puluh sen; RM1.5 juta -> satu
    perpuluhan lima juta ringgit."""
    if scale:
        return f" {number(num)} {scale.strip()} {name} "
    n, frac = parse_number(num)
    if name == "ringgit" and frac and len(frac) == 2:
        sen = int(frac)
        main = f"{cardinal(n)} ringgit " if n else ""
        return f" {main}{cardinal(sen) + ' sen' if sen else ''} "
    return f" {number(num)} {name} "


def normalize_ms(text: str) -> str:
    t = apply_abbreviations(text, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = DATE_ABBR.sub(_date_abbr, t)
    t = TIME.sub(_time, t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), ONES, "tambah"), t)
    t = MONEY_BEFORE.sub(lambda m: _ringgit(m.group(2), m.group(3), CURRENCY[m.group(1)]), t)
    t = MONEY_AFTER.sub(lambda m: f" {number(m.group(1))} {CURRENCY[m.group(2)]} ", t)
    t = SEN.sub(lambda m: f" {number(m.group(1))} sen ", t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} peratus ", t)
    t = UNIT.sub(lambda m: f" {number(m.group(1) + m.group(2))} {UNITS[m.group(3)]} ", t)
    t = ORDINAL.sub(lambda m: f" {ordinal(int(m.group(1)))} ", t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} hingga {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, ONES)} ", t)
    t = NUMBER.sub(lambda m: f" {number(m.group(1) + m.group(2))} ", t)
    t = REDUP.sub(r"\1 \1", t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    return finish(t)
