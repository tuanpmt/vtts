"""Italian text normalization for one Italian run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces. Accents and apostrophes are kept (they mark the stress and
the elision for g2p_it).

Rules, in order: typographic apostrophes, abbreviations (sig., dott., ecc.), quotes and brackets
dropped, dates (5/3/2026, 2026-03-05), times (14:30, 14.30 after "alle"/"ore"), phone numbers
(digit by digit), money (20 €, €20, 12,50 € -> dodici euro e cinquanta centesimi), percentages,
units after a number (5 km, 25 °C), ordinals (1º, 2ª, 3°), ranges (10-20), pause marks (… —),
product codes (ESP32: letters by Italian name, digits one by one), numbers (1.250,5 or 1,250.5;
"un" before a word), symbols, acronyms (spelled: USB -> u esse bi; some read as words: NATO).

Numbers are written as words with spaces between the scale groups and between hundreds and tens
(1234 -> mille duecento trentaquattro), so each part keeps its own stress; tens drop their vowel
before uno/otto (ventuno, trentotto) and a final tre is tré (ventitré).
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
    parse_number,
    phone_digits,
    read_number,
    spell,
)
from .g2p_it import ELISION

ONES = ("zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci",
        "undici", "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette", "diciotto",
        "diciannove")
TENS = ("", "", "venti", "trenta", "quaranta", "cinquanta", "sessanta", "settanta", "ottanta",
        "novanta")
DIGITS = ONES[:10]
SCALES = ((10 ** 12, "bilione", "bilioni"), (10 ** 9, "miliardo", "miliardi"), (10 ** 6, "milione", "milioni"))
MONTHS = ("", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
          "settembre", "ottobre", "novembre", "dicembre")
ORD_SMALL = ("", "primo", "secondo", "terzo", "quarto", "quinto", "sesto", "settimo", "ottavo",
             "nono", "decimo")
LETTERS = {"a": "a", "b": "bi", "c": "ci", "d": "di", "e": "e", "f": "effe", "g": "gi", "h": "acca",
           "i": "i", "j": "i lunga", "k": "cappa", "l": "elle", "m": "emme", "n": "enne", "o": "o",
           "p": "pi", "q": "cu", "r": "erre", "s": "esse", "t": "ti", "u": "u", "v": "vu",
           "w": "doppia vu", "x": "ics", "y": "ipsilon", "z": "zeta"}
ACRONYM_WORDS = frozenset(("nato", "onu", "fiat", "ansa", "rai", "istat", "inps", "inail", "anas",
                           "covid", "ram", "rom", "led", "pin", "sim", "laser", "radar", "unesco",
                           "fifa", "uefa", "nasa", "opec", "iva", "tar", "asl", "isee", "enel",
                           "eni", "coni", "ikea", "aids"))
ABBREVIATIONS = {
    "Sig.ra": "signora", "sig.ra": "signora", "Sig.na": "signorina", "Sigg.": "signori",
    "Sig.": "signor", "sig.": "signor", "Dott.ssa": "dottoressa", "dott.ssa": "dottoressa",
    "Dott.": "dottor", "dott.": "dottor", "Prof.ssa": "professoressa", "Prof.": "professor",
    "prof.": "professor", "Avv.": "avvocato", "Ing.": "ingegner", "Arch.": "architetto",
    "S.p.A.": "esse pi a", "ecc.": "eccetera", "pag.": "pagina",
    "pagg.": "pagine", "n.": "numero", "nr.": "numero", "tel.": "telefono", "cfr.": "confronta",
    "ca.": "circa", "es.": "esempio", "p.es.": "per esempio", "sec.": "secolo",
    "c.a.": "corrente anno", "a.C.": "avanti cristo", "d.C.": "dopo cristo",
    "P.za": "piazza", "p.za": "piazza", "C.so": "corso", "c.so": "corso", "V.le": "viale",
    "v.le": "viale", "nº": "numero", "n°": "numero", "cmq": "comunque", "xké": "perché",
    "perké": "perché", "tvb": "ti voglio bene",
}
# Units after a number: (singular, plural).
UNITS = {"km/h": ("chilometro orario", "chilometri orari"), "km": ("chilometro", "chilometri"),
         "m": ("metro", "metri"), "cm": ("centimetro", "centimetri"),
         "mm": ("millimetro", "millimetri"), "kg": ("chilo", "chili"), "g": ("grammo", "grammi"),
         "mg": ("milligrammo", "milligrammi"), "l": ("litro", "litri"), "L": ("litro", "litri"),
         "ml": ("millilitro", "millilitri"), "h": ("ora", "ore"), "min": ("minuto", "minuti"),
         "s": ("secondo", "secondi"), "GB": ("gigabyte", "gigabyte"),
         "MB": ("megabyte", "megabyte"), "TB": ("terabyte", "terabyte"),
         "kWh": ("chilowattora", "chilowattora"), "kW": ("chilowatt", "chilowatt"),
         "W": ("watt", "watt"), "V": ("volt", "volt"), "mAh": ("milliampereora", "milliampereora"),
         "GHz": ("gigahertz", "gigahertz"), "MHz": ("megahertz", "megahertz"),
         "°C": ("grado", "gradi"), "℃": ("grado", "gradi"), "°": ("grado", "gradi")}
CURRENCY = {"US$": ("dollaro", "dollari"), "$": ("dollaro", "dollari"), "€": ("euro", "euro"),
            "EUR": ("euro", "euro"), "£": ("sterlina", "sterline"), "¥": ("yen", "yen"),
            "CHF": ("franco", "franchi")}
SYMBOLS = {"&": " e ", "+": " più ", "=": " uguale a ", "@": " chiocciola ", "#": " cancelletto ",
           "×": " per ", "/": " ", "%": " per cento "}
MARK_WORDS = {",": "virgola", ".": "punto"}

_A = r"(?<![\w.,])"
_Z = r"(?![\w])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?<![\d/.])(\d{1,2})[/.](\d{1,2})[/.](\d{4}|\d{2})(?![\d/]|\.\d)")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])")
TIME_DOT = re.compile(r"\b([Aa]lle|[Oo]re|[Dd]alle|[Ee]ntro|[Vv]erso)\s+([01]?\d|2[0-4])\.([0-5]\d)(?![\d.,])")
PHONE = re.compile(r"(?<![\d])(?:\+\d{1,3}[\s-])?\d{2,4}(?:[\s-]\d{2,4}){2,4}(?![\d])"
                   r"|(?<![\d.,])0\d{5,}(?![\d]|[.,]\d)|(?<![\d.,])3\d{2}[\s-]?\d{6,7}(?![\d])")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")")
MONEY_AFTER = re.compile(_A + r"(" + NUM + r")\s?(" + _CUR_KEYS + r")(?![\w])")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(_A + r"(\d+)(º|ª|°(?!\s?C))(?![\w])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)" + _Z)
FINAL_APOSTROPHE = re.compile(r"(?<=[^\W\d_])'(?![^\W\d_])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])(\s*)(?=([^\W\d_]+)?)")
# Words after a number that are not counted by it (101 e 102, 1 di loro): uno keeps its vowel.
NOT_COUNTED = frozenset(("e", "ed", "o", "od", "a", "ad", "di", "da", "in", "con", "su", "per", "tra",
                         "fra", "del", "della", "dei", "delle", "degli", "al", "alla", "nel", "nella",
                         "che", "è", "ma", "se"))


def _below_100(n: int) -> str:
    if n < 20:
        return ONES[n]
    t, u = divmod(n, 10)
    tens = TENS[t]
    if u in (1, 8):
        tens = tens[:-1]
    return tens + ("tré" if u == 3 else ONES[u] if u else "")


def _below_1000(n: int) -> str:
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts.append("cento" if h == 1 else ONES[h] + "cento")
    if r:
        parts.append(_below_100(r))
    return " ".join(parts)


def cardinal(n: int) -> str:
    """Italian cardinal: 21 -> ventuno, 23 -> ventitré, 1234 -> mille duecento trentaquattro,
    2_000_000 -> due milioni, 10**9 -> un miliardo."""
    if n < 0:
        return "meno " + cardinal(-n)
    if n == 0:
        return "zero"
    if n >= 10 ** 15:
        return digits(str(n), DIGITS)
    parts = []
    for scale, one, many in SCALES:
        q, n = divmod(n, scale)
        if q == 1:
            parts.append(f"un {one}")
        elif q:
            parts.append(f"{cardinal(q)} {many}")
    th, n = divmod(n, 1000)
    if th == 1:
        parts.append("mille")
    elif th:
        words = _below_1000(th).split()
        parts += words[:-1] + [words[-1] + "mila"]
    if n:
        parts.append(_below_1000(n))
    return " ".join(parts)


def ordinal(n: int, fem: bool = False) -> str:
    """1 -> primo, 11 -> undicesimo, 23 -> ventitreesimo; fem: prima, undicesima."""
    if 1 <= n <= 10:
        out = ORD_SMALL[n]
    elif n < 1:
        return cardinal(n)
    else:
        words = cardinal(n).replace(" ", "")
        if words.endswith("tré"):
            out = words[:-3] + "treesimo"
        elif words.endswith("sei"):
            out = words + "esimo"
        elif words.endswith("mille"):
            out = words[:-1] + "esimo"
        else:
            out = words[:-1] + "esimo"
    return out[:-1] + "a" if fem else out


def number(s: str, before_word: bool = False) -> str:
    """A written number; before_word: a final uno is un (un euro, ventun anni)."""
    out = read_number(s.lstrip("-"), cardinal, MARK_WORDS, DIGITS)
    if before_word and parse_number(s.lstrip("-"))[1] is None and out.endswith("uno"):
        out = out[:-1]
    return ("meno " if s.startswith("-") else "") + out


def _count(s: str) -> tuple[str, bool]:
    n, frac, _ = parse_number(s)
    return number(s, before_word=True), n == 1 and frac is None


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{'primo' if d == 1 else cardinal(d)} {MONTHS[m]}"
    if y is not None:
        yy = int(y) + (2000 if len(y) == 2 else 0)
        out += f" {cardinal(yy)}"
    return f" {out} "


def _time(h: int, mi: int, sec: str | None = None) -> str:
    out = "l'una" if h == 1 else cardinal(h)
    if mi:
        out += f" e {cardinal(mi)}"
    if sec and int(sec):
        out += f" e {cardinal(int(sec))} secondi"
    return f" {out} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    words, one = _count(num)
    return f" {'meno ' if sign else ''}{words} {UNITS[unit][0 if one else 1]} "


def _money(num: str, cur: str) -> str:
    n, frac, _ = parse_number(num)
    name = CURRENCY[cur]
    if frac is not None and len(frac) == 2 and cur in ("€", "EUR", "$", "US$"):
        out = f"{number(str(n), before_word=True)} {name[0 if n == 1 else 1]}"
        cents = int(frac)
        if cents:
            out += f" e {cardinal(cents)} {'centesimo' if cents == 1 else 'centesimi'}"
        return f" {out} "
    words, one = _count(num)
    return f" {words} {name[0 if one else 1]} "


def _number(m: re.Match) -> str:
    sign, num, space, word = m.groups()
    counted = bool(word) and word.lower() not in NOT_COUNTED
    return f" {number(sign + num, before_word=counted)}{space or ' '}"


def normalize_it(text: str) -> str:
    t = text.replace("’", "'").replace("‘", "'")
    t = apply_abbreviations(t, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = TIME.sub(lambda m: _time(int(m.group(1)), int(m.group(2)), m.group(3)), t)
    t = TIME_DOT.sub(lambda m: m.group(1) + _time(int(m.group(2)), int(m.group(3))), t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), DIGITS, "più"), t)
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(2)), t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} per cento ", t)
    t = UNIT.sub(_unit, t)
    t = ORDINAL.sub(lambda m: f" {ordinal(int(m.group(1)), m.group(2) == 'ª')} ", t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} a {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, DIGITS)} ", t)
    t = NUMBER.sub(_number, t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    t = FINAL_APOSTROPHE.sub(ELISION, t)  # sull' (before an English word), po': kept as a word
    return finish(t)
