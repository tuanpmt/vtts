"""Swahili text normalization for one Swahili run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces; ng' keeps its apostrophe (ng'ombe).

Numbers are read in the counting form (moja, mbili, tatu ...; kumi na moja, ishirini na moja,
mia moja, elfu moja, laki moja for 100,000, milioni, bilioni; "na" before the last part when it is
below 100: elfu mbili na ishirini na sita). Numbers do not agree with the noun class (watu 2 is
read watu mbili, not watu wawili). Decimals: nukta and the decimals digit by digit (3.5 -> tatu
nukta tano); East African marks (1,250.50). Ordinals after a concord word: wa 1 -> wa kwanza,
ya 2 -> ya pili, other numbers as cardinals (wa tatu).

Words that come before the number in Swahili are moved there: money (TSh 5,000 and 5,000/= ->
shilingi elfu tano; $5 -> dola tano; senti), percent (15% -> asilimia kumi na tano), units
(5 km -> kilomita tano, 25°C -> nyuzi joto ishirini na tano).

Times are read as written on the 24-hour or 12-hour clock with saa (14:30 -> saa kumi na nne na
nusu, 9:15 -> saa tisa na robo, 9:05 -> saa tisa na dakika tano): they are NOT converted to
Swahili time (where 7:00 is saa moja), because the text does not say which system it uses; a
writer who means Swahili time writes it that way already (saa 3 asubuhi -> saa tatu asubuhi).
Dates are day first (19/11/2026 -> tarehe kumi na tisa novemba elfu mbili na ishirini na sita).
Letter names follow the English alphabet as acronyms are spelled in East Africa (CCM -> si si em).
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
    finish,
    phone_digits,
    spell,
)

ONES = ("sifuri", "moja", "mbili", "tatu", "nne", "tano", "sita", "saba", "nane", "tisa")
TENS = ("", "kumi", "ishirini", "thelathini", "arobaini", "hamsini", "sitini", "sabini",
        "themanini", "tisini")
SCALES = ((10 ** 12, "trilioni"), (10 ** 9, "bilioni"), (10 ** 6, "milioni"))
MONTHS = ("", "januari", "februari", "machi", "aprili", "mei", "juni", "julai", "agosti",
          "septemba", "oktoba", "novemba", "desemba")
LETTERS = {"a": "ei", "b": "bi", "c": "si", "d": "di", "e": "i", "f": "ef", "g": "ji", "h": "eichi",
           "i": "ai", "j": "jei", "k": "kei", "l": "el", "m": "em", "n": "en", "o": "o", "p": "pi",
           "q": "kyu", "r": "ar", "s": "es", "t": "ti", "u": "yu", "v": "vi", "w": "dabliyu",
           "x": "eksi", "y": "wai", "z": "zedi"}
ACRONYM_WORDS = frozenset(("tanesco", "nato", "covid", "unesco", "unicef", "tamisemi", "tanapa",
                           "nssf", "pin", "ram", "rom"))
ABBREVIATIONS = {
    "n.k.": "na kadhalika", "nk.": "na kadhalika", "k.m.": "kwa mfano", "Bw.": "bwana",
    "Bi.": "bibi", "Dkt.": "daktari", "Dk.": "daktari", "Prof.": "profesa",
    "Mh.": "mheshimiwa", "Mhe.": "mheshimiwa", "S.L.P.": "sanduku la posta", "Mt.": "mtakatifu",
    "Na.": "namba", "Nam.": "namba", "BK": "baada ya kristo", "KK": "kabla ya kristo",
}
UNITS = {"km/h": "kilomita kwa saa", "km/saa": "kilomita kwa saa", "km": "kilomita",
         "m": "mita", "cm": "sentimita", "mm": "milimita", "kg": "kilo", "g": "gramu",
         "mg": "miligramu", "l": "lita", "L": "lita", "ml": "mililita", "GB": "gigabaiti",
         "MB": "megabaiti", "TB": "terabaiti", "kWh": "kilowati saa", "kW": "kilowati",
         "W": "wati", "V": "volti", "mAh": "miliampea saa", "GHz": "gigahezi", "MHz": "megahezi",
         "ha": "hekta", "°C": "nyuzi joto", "℃": "nyuzi joto", "°": "nyuzi"}
CURRENCY = {"TSh": "shilingi", "TZS": "shilingi", "KSh": "shilingi", "KES": "shilingi",
            "USh": "shilingi", "UGX": "shilingi", "Sh.": "shilingi", "Sh": "shilingi",
            "US$": "dola", "$": "dola", "€": "yuro", "£": "pauni", "¥": "yeni"}
SYMBOLS = {"&": " na ", "+": " jumlisha ", "=": " ni sawa na ", "@": " et ", "#": " namba ",
           "×": " mara ", "/": " kwa ", "%": " asilimia "}
CONCORDS = ("wa", "ya", "la", "cha", "vya", "za", "kwa", "pa", "mwa")

_A = r"(?<![\w.,])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?:(?<![\w])tarehe\s+)?(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])",
                      re.IGNORECASE)
DATE_ISO = re.compile(r"(?:(?<![\w])tarehe\s+)?(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])",
                      re.IGNORECASE)
TIME = re.compile(r"(?:(?<![\w])saa\s+)?(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::[0-5]\d)?(?![\d:])",
                  re.IGNORECASE)
PHONE = re.compile(r"(?<![\d])(?:\+\d{1,3}[\s-])?\d{2,4}(?:[\s-]\d{2,4}){2,4}(?![\d])"
                   r"|(?<![\d.,])0\d{2,}(?![\d]|[.,]\d)")
MONEY_BEFORE = re.compile(r"(?<![\w])(" + _CUR_KEYS + r")\s?(" + NUM + r")(?:/=)?")
MONEY_AFTER = re.compile(_A + r"(" + NUM + r")\s?(?:/=|(€|£|¥|\$)|\s?(?:shilingi|Sh|TSh|KSh)(?![\w]))")
PERCENT = re.compile(r"(?:(?<![\w])asilimia\s+)?" + _A + r"(-?)(" + NUM + r")\s?%", re.IGNORECASE)
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
# A unit written before its number, as Swahili reads it (km 190, kg 1.2); units of two or more
# letters only.
_UNIT_WORDS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True) if len(u) > 1 and u.isalpha())
UNIT_BEFORE = re.compile(r"(?<![\w.,])(" + _UNIT_WORDS + r")\s+(" + NUM + r")(?![\d])")
ORDINAL = re.compile(r"(?<![\w])(" + "|".join(CONCORDS) + r")\s+([12])(?![\d.,:/\w])", re.IGNORECASE)
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])")


def _below_100(n: int) -> str:
    t, u = divmod(n, 10)
    if not t:
        return ONES[u]
    return TENS[t] + (f" na {ONES[u]}" if u else "")


def _below_1000(n: int) -> str:
    h, r = divmod(n, 100)
    if not h:
        return _below_100(r)
    out = f"mia {ONES[h]}"
    if r:
        out += (" na " if r < 10 else " ") + _below_100(r)
    return out


def _thousands(q: int) -> str:
    """q thousand, q < 1000: elfu ishirini na tano; from 100 thousand with laki (laki mbili na
    elfu hamsini)."""
    lakh, rest = divmod(q, 100)
    parts = [f"laki {_below_100(lakh)}"] if lakh else []
    if rest:
        parts.append(f"elfu {_below_100(rest)}")
    return " na ".join(parts)


def cardinal(n: int) -> str:
    """Swahili cardinal (counting form): 11 -> kumi na moja, 101 -> mia moja na moja,
    2026 -> elfu mbili na ishirini na sita, 250_000 -> laki mbili na elfu hamsini."""
    if n < 0:
        return "hasi " + cardinal(-n)
    if n == 0:
        return "sifuri"
    if n >= 10 ** 15:
        return " ".join(ONES[int(c)] for c in str(n))
    parts = []
    for scale, name in SCALES:
        q, n = divmod(n, scale)
        if q:
            parts.append(f"{name} {cardinal(q)}")
    q, n = divmod(n, 1000)
    if q:
        parts.append(_thousands(q))
    if n:
        parts.append(("na " if parts and n < 100 else "") + _below_1000(n))
    return " ".join(parts)


def parse_number(s: str) -> tuple[int, str | None]:
    """(integer part, decimals): comma for thousands, point for decimals (1,250.50; 3.5)."""
    s = s.lstrip("+")
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
        a, _, b = s.partition(".")
        return int(a.replace(",", "")), b or None
    if re.fullmatch(r"\d{1,3}(\.\d{3}){2,}", s):
        return int(s.replace(".", "")), None
    for mark in ".,":
        if mark in s:
            a, b = s.split(mark, 1)
            return int(a.replace(",", "") or 0), b  # 21,234.5,6: commas group the integer part
    return int(s), None


def number(s: str) -> str:
    neg = s.startswith("-")
    n, frac = parse_number(s.lstrip("-"))
    out = cardinal(n)
    if frac:
        out += " nukta " + " ".join(ONES[int(c)] for c in frac if c.isdigit())  # 1.234,5: marks skipped
    return ("hasi " if neg else "") + out


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"tarehe {cardinal(d)} {MONTHS[m]}"
    if y is not None:
        out += f" {cardinal(int(y) + (2000 if len(y) == 2 else 0))}"
    return f" {out} "


def _time(m: re.Match) -> str:
    h, mi = int(m.group(1)), int(m.group(2))
    out = f"saa {cardinal(h)}"
    if mi == 15:
        out += " na robo"
    elif mi == 30:
        out += " na nusu"
    elif mi:
        out += f" na dakika {cardinal(mi)}"
    return f" {out} "


def _money(name: str, num: str) -> str:
    n, frac = parse_number(num)
    cents = int(frac[:2].ljust(2, "0")) if frac else 0
    if name == "shilingi" and cents:
        return f" shilingi {cardinal(n)} na senti {cardinal(cents)} "
    return f" {name} {number(num)} "


def _money_after(m: re.Match) -> str:
    return _money(CURRENCY[m.group(2)] if m.group(2) else "shilingi", m.group(1))


def normalize_sw(text: str) -> str:
    t = apply_abbreviations(text, ABBREVIATIONS)
    t = t.replace("’", "'")
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = TIME.sub(_time, t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), ONES, "jumlisha"), t)
    t = MONEY_BEFORE.sub(lambda m: _money(CURRENCY[m.group(1)], m.group(2)), t)
    t = MONEY_AFTER.sub(_money_after, t)
    t = PERCENT.sub(lambda m: f" asilimia {number(m.group(1) + m.group(2))} ", t)
    t = UNIT.sub(lambda m: f" {UNITS[m.group(3)]} {number(m.group(1) + m.group(2))} ", t)
    t = UNIT_BEFORE.sub(lambda m: f" {UNITS[m.group(1)]} {number(m.group(2))} ", t)
    t = ORDINAL.sub(lambda m: f" {m.group(1)} {'kwanza' if m.group(2) == '1' else 'pili'} ", t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} hadi {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, ONES)} ", t)
    t = NUMBER.sub(lambda m: f" {number(m.group(1) + m.group(2))} ", t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    return finish(t)
