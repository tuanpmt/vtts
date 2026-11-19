"""Danish text normalization for one Danish run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces.

Numbers are read the Danish way: units before tens joined with "og" (21 -> enogtyve), the
vigesimal tens halvtreds tres halvfjerds firs halvfems, hundrede and tusind without "et"/"en",
"og" before the last part below 100 (2026 -> to tusind og seksogtyve, 101 -> hundrede og en),
million(er), milliard(er); a year 1100-1999 standing alone is read in hundreds (1984 -> nitten
hundrede og fireogfirs). Decimals with komma (3,5 -> tre komma fem; the Danish decimal comma and
thousands dot, or 1,250.5). Ordinals 1.-31. before a lower-case word or a month (1. maj ->
første maj, den 3. plads -> den tredje plads); dates 5/3/2026, 5.3.2026, 2026-03-05 and 5. marts
2026 (femte marts to tusind og seksogtyve); times 14:30, kl. 14.30 (klokken fjorten tredive);
kroner and øre (12,50 kr. -> tolv kroner og halvtreds øre, 1 kr. -> en krone, DKK 500), euro,
dollar, pund; percent (procent), units, phone numbers (+45 12 34 56 78: groups read as numbers,
a group with a leading 0 digit by digit), ranges (10-20 -> ti til tyve), abbreviations (f.eks.,
bl.a., osv., ca., nr., kr., mio., mia., kl. ...), product codes and acronyms spelled with the
Danish letter names (USB -> u es be; a few are read as words: NATO).
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
    parse_number,
    spell,
)

ONES = ("nul", "en", "to", "tre", "fire", "fem", "seks", "syv", "otte", "ni", "ti", "elleve",
        "tolv", "tretten", "fjorten", "femten", "seksten", "sytten", "atten", "nitten")
TENS = ("", "", "tyve", "tredive", "fyrre", "halvtreds", "tres", "halvfjerds", "firs", "halvfems")
DIGITS = ONES[:10]
ORDINALS = ("", "første", "anden", "tredje", "fjerde", "femte", "sjette", "syvende", "ottende",
            "niende", "tiende", "ellevte", "tolvte", "trettende", "fjortende", "femtende",
            "sekstende", "syttende", "attende", "nittende", "tyvende", "enogtyvende", "toogtyvende",
            "treogtyvende", "fireogtyvende", "femogtyvende", "seksogtyvende", "syvogtyvende",
            "otteogtyvende", "niogtyvende", "tredivte", "enogtredivte")
MONTHS = ("", "januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september",
          "oktober", "november", "december")
LETTERS = {"a": "a", "b": "be", "c": "se", "d": "de", "e": "e", "f": "ef", "g": "ge", "h": "hå",
           "i": "i", "j": "jod", "k": "kå", "l": "el", "m": "em", "n": "en", "o": "o", "p": "pe",
           "q": "ku", "r": "ær", "s": "es", "t": "te", "u": "u", "v": "ve", "w": "dobbeltve",
           "x": "eks", "y": "y", "z": "set", "æ": "æ", "ø": "ø", "å": "å"}
ACRONYM_WORDS = frozenset(("nato", "unesco", "unicef", "nasa", "fifa", "uefa", "aids", "covid",
                           "ram", "rom", "led", "pin", "sim", "opec", "dong", "dsb", "dr"))
ABBREVIATIONS = {
    "f.eks.": "for eksempel", "fx.": "for eksempel", "bl.a.": "blandt andet", "osv.": "og så videre",
    "dvs.": "det vil sige", "ca.": "cirka", "nr.": "nummer", "mio.": "millioner",
    "mia.": "milliarder", "evt.": "eventuelt", "m.m.": "med mere", "mht.": "med hensyn til",
    "pga.": "på grund af", "jf.": "jævnfør", "inkl.": "inklusive", "ekskl.": "eksklusive",
    "tlf.": "telefon", "hr.": "hr", "Hr.": "hr", "dr.": "doktor", "Dr.": "doktor", "St.": "sankt",
    "kl.": "klokken", "ift.": "i forhold til", "vha.": "ved hjælp af", "etc.": "et cetera",
    "o.l.": "og lignende", "m.fl.": "med flere", "iflg.": "ifølge", "pct.": "procent",
    "årh.": "århundrede", "bl.": "blandt", "s.": "side", "f.": "født", "d.": "den",
    "e.Kr.": "efter kristus", "f.Kr.": "før kristus", "A/S": "a s", "ApS": "a p s",
}
# Units after a number: (singular, plural).
UNITS = {"km/t": ("kilometer i timen", "kilometer i timen"), "km/h": ("kilometer i timen",
                                                                     "kilometer i timen"),
         "km": ("kilometer", "kilometer"), "m": ("meter", "meter"), "cm": ("centimeter", "centimeter"),
         "mm": ("millimeter", "millimeter"), "kg": ("kilo", "kilo"), "g": ("gram", "gram"),
         "mg": ("milligram", "milligram"), "l": ("liter", "liter"), "L": ("liter", "liter"),
         "ml": ("milliliter", "milliliter"), "t": ("time", "timer"), "min": ("minut", "minutter"),
         "sek": ("sekund", "sekunder"), "s": ("sekund", "sekunder"), "GB": ("gigabyte", "gigabyte"),
         "MB": ("megabyte", "megabyte"), "TB": ("terabyte", "terabyte"),
         "kWh": ("kilowatttime", "kilowatttimer"), "kW": ("kilowatt", "kilowatt"),
         "W": ("watt", "watt"), "V": ("volt", "volt"), "mAh": ("milliamperetime", "milliamperetimer"),
         "GHz": ("gigahertz", "gigahertz"), "MHz": ("megahertz", "megahertz"),
         "°C": ("grad", "grader"), "℃": ("grad", "grader"), "°": ("grad", "grader"),
         "m²": ("kvadratmeter", "kvadratmeter"), "km²": ("kvadratkilometer", "kvadratkilometer")}
CURRENCY = {"kr.": ("krone", "kroner"), "kr": ("krone", "kroner"), "DKK": ("krone", "kroner"),
            "€": ("euro", "euro"), "EUR": ("euro", "euro"), "$": ("dollar", "dollar"),
            "USD": ("dollar", "dollar"), "£": ("pund", "pund")}
SYMBOLS = {"&": " og ", "+": " plus ", "=": " lig med ", "@": " snabel a ", "#": " nummer ",
           "×": " gange ", "/": " ", "%": " procent ", "§": " paragraf "}
MARK_WORDS = {",": "komma", ".": "punktum"}

_A = r"(?<![\w.,])"
_Z = r"(?![\w])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_AFTER = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
_CUR_BEFORE = "|".join(re.escape(c) for c in ("DKK", "EUR", "USD", "€", "$", "£"))
# Month names in lower case or capitalized (no re.IGNORECASE: it also matches the Kelvin sign and the
# long s of Unicode, which the device front-end does not fold).
_MONTH_KEYS = "|".join(MONTHS[1:] + tuple(m.capitalize() for m in MONTHS[1:]))
DATE_DMY = re.compile(r"(?<![\d/.])(\d{1,2})([/.])(\d{1,2})\2(\d{4})(?![\d/]|\.\d)")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
DATE_NAMED = re.compile(r"(?<![\d.,])(\d{1,2})\.\s?(" + _MONTH_KEYS + r")(?:\s(\d{4}))?(?![\w])")
TIME_KL = re.compile(r"([Kk]lokken)\s+(\d{1,2})(?:[.:]([0-5]\d))?(?![\d])")
TIME = re.compile(r"(?<![\d:.,])([01]?\d|2[0-4])[:.]([0-5]\d)(?![\d:]|[.,]\d)")
PHONE = re.compile(r"(?<![\d])(?:\+\d{2}\s)?\d{2}(?:\s\d{2}){3}(?![\d])|(?<![\d])\+\d{2}\s?\d{8}(?![\d])")
MONEY_BEFORE = re.compile(r"(" + _CUR_BEFORE + r")\s?(" + NUM + r")(?:,-)?")
MONEY_AFTER = re.compile(_A + r"(" + NUM + r")(?:,-)?\s?(" + _CUR_AFTER + r")(?![\w])")
ORE = re.compile(_A + r"(\d+)\s?øre(?![\w])")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(_A + r"(\d{1,2})\.(?=\s[a-zæøå])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)" + _Z)
YEAR = re.compile(r"(?<![\w.,])(1[1-9]\d\d)(?![\w]|[.,]\d)")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])")


def _below_100(n: int) -> str:
    if n < 20:
        return ONES[n]
    t, u = divmod(n, 10)
    return (f"{ONES[u]}og" if u else "") + TENS[t]


def _below_1000(n: int) -> str:
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts.append("hundrede" if h == 1 else f"{ONES[h]} hundrede")
    if r:
        parts.append(("og " if h else "") + _below_100(r))
    return " ".join(parts)


def cardinal(n: int) -> str:
    """Danish cardinal: 21 -> enogtyve, 100 -> hundrede, 2026 -> to tusind og seksogtyve,
    1_000_000 -> en million."""
    if n < 0:
        return "minus " + cardinal(-n)
    if n == 0:
        return "nul"
    if n >= 10 ** 15:
        return " ".join(DIGITS[int(c)] for c in str(n))
    parts: list[str] = []
    for scale, one, many in ((10 ** 9, "milliard", "milliarder"), (10 ** 6, "million", "millioner")):
        q, n = divmod(n, scale)
        if q:
            parts.append(f"en {one}" if q == 1 else f"{cardinal(q)} {many}")
    q, n = divmod(n, 1000)
    if q:
        parts.append("tusind" if q == 1 else f"{_below_1000(q)} tusind")
    if n:
        parts.append(("og " if parts and n < 100 else "") + _below_1000(n))
    return " ".join(parts)


def year(n: int) -> str:
    """1100-1999 in hundreds: 1984 -> nitten hundrede og fireogfirs; other years as cardinals."""
    if 1100 <= n <= 1999:
        h, r = divmod(n, 100)
        return f"{ONES[h]} hundrede" + (f" og {_below_100(r)}" if r else "")
    return cardinal(n)


def number(s: str) -> str:
    """A written number (decimal comma or point): 3,5 -> tre komma fem; 0,05 -> nul komma nul fem."""
    neg = s.startswith("-")
    n, frac, mark = parse_number(s.lstrip("-"))
    out = cardinal(n)
    if frac is not None:
        if len(frac) <= 2 and not frac.startswith("0"):
            out += f" {MARK_WORDS[mark]} {cardinal(int(frac))}"
        else:
            out += f" {MARK_WORDS[mark]} " + " ".join(DIGITS[int(c)] for c in frac)
    return ("minus " if neg else "") + out


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{ORDINALS[d]} {MONTHS[m]}"
    if y:
        out += f" {year(int(y))}"
    return f" {out} "


def _named_date(m: re.Match) -> str:
    d = int(m.group(1))
    if not 1 <= d <= 31:
        return m.group(0)
    out = f"{ORDINALS[d]} {m.group(2).lower()}"
    if m.group(3):
        out += f" {year(int(m.group(3)))}"
    return f" {out} "


def _clock(h: int, mi: int) -> str:
    if mi == 0:
        return cardinal(h)
    return f"{cardinal(h)} {'nul ' + ONES[mi] if mi < 10 else _below_100(mi)}"


def _money(num: str, cur: str) -> str:
    n, frac, _ = parse_number(num)
    one, many = CURRENCY[cur]
    if frac is not None and cur in ("kr.", "kr", "DKK") and len(frac) == 2:
        out = f"{cardinal(n)} {one if n == 1 else many}"
        if int(frac):
            out += f" og {cardinal(int(frac))} øre"
        return f" {out} "
    return f" {number(num)} {one if n == 1 and frac is None else many} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    n, frac, _ = parse_number(num)
    one = n == 1 and frac is None
    return f" {'minus ' if sign else ''}{number(num)} {UNITS[unit][0 if one else 1]} "


def _phone(m: re.Match) -> str:
    out = []
    for g in m.group(0).split():
        if g.startswith("+"):
            out.append("plus " + cardinal(int(g[1:3])))
            g = g[3:]
        for k in range(0, len(g), 2):
            pair = g[k:k + 2]
            out.append(" ".join(DIGITS[int(c)] for c in pair) if pair.startswith("0") else cardinal(int(pair)))
    return " " + " ".join(out) + " "


def normalize_da(text: str) -> str:
    t = apply_abbreviations(text, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(3)), m.group(4)) or m.group(0), t)
    t = DATE_NAMED.sub(_named_date, t)
    t = TIME_KL.sub(lambda m: f"{m.group(1)} {_clock(int(m.group(2)), int(m.group(3) or 0))} ", t)
    t = TIME.sub(lambda m: f" {_clock(int(m.group(1)), int(m.group(2)))} ", t)
    t = PHONE.sub(_phone, t)
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(2)) + (
        "." if m.group(2) == "kr." and not m.string[m.end():].strip() else ""), t)
    t = ORE.sub(lambda m: f" {cardinal(int(m.group(1)))} øre ", t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} procent ", t)
    t = UNIT.sub(_unit, t)
    t = ORDINAL.sub(lambda m: f" {ORDINALS[int(m.group(1))] if 1 <= int(m.group(1)) <= 31 else cardinal(int(m.group(1)))} ", t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} til {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, DIGITS)} ", t)
    t = YEAR.sub(lambda m: f" {year(int(m.group(1)))} ", t)
    t = NUMBER.sub(lambda m: f" {number(m.group(1) + m.group(2))} ", t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    return finish(t)
