"""Spanish text normalization for one Spanish run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces. Accents are kept (they mark the stress for g2p_es).

Rules, in order: abbreviations (Sr., EE. UU., etc.), quotes, brackets and ¿ ¡ dropped, dates
(5/3/2026, 2026-03-05), times (14:30, 7:00 h), phone numbers (digit by digit), money ($5, 20 €),
percentages, units after a number (5 km, 25 °C), ordinals (1.º, 2.ª, 3.er), ranges (10-20),
pause marks (… — and a dash between spaces), product codes (ESP32: letters by Spanish name,
digits one by one), numbers (1.250,5 or 1,250.5; "un"/"veintiún" before a word), symbols,
acronyms (spelled: USB -> u ese be; a few read as words: ONU, OTAN).
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

ONES = ("cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
        "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho",
        "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro",
        "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve")
TENS = ("", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa")
HUNDREDS = ("", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos",
            "seiscientos", "setecientos", "ochocientos", "novecientos")
SCALES = ((10 ** 18, "trillón", "trillones"), (10 ** 12, "billón", "billones"),
          (10 ** 6, "millón", "millones"))
DIGITS = ONES[:10]
MONTHS = ("", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")
ORD_ONES = ("", "primero", "segundo", "tercero", "cuarto", "quinto", "sexto", "séptimo", "octavo",
            "noveno")
ORD_TENS = ("", "décimo", "vigésimo", "trigésimo", "cuadragésimo", "quincuagésimo", "sexagésimo",
            "septuagésimo", "octogésimo", "nonagésimo")
ORD_HUNDREDS = ("", "centésimo", "ducentésimo", "tricentésimo", "cuadringentésimo",
                "quingentésimo", "sexcentésimo", "septingentésimo", "octingentésimo",
                "noningentésimo")
LETTERS = {"a": "á", "b": "be", "c": "ce", "d": "dé", "e": "é", "f": "efe", "g": "ge",
           "h": "hache", "i": "í", "j": "jota", "k": "ka", "l": "ele", "m": "eme", "n": "ene",
           "ñ": "eñe", "o": "ó", "p": "pe", "q": "cu", "r": "erre", "s": "ese", "t": "té",
           "u": "ú", "v": "uve", "w": "uve doble", "x": "equis", "y": "ye", "z": "zeta"}
ACRONYM_WORDS = frozenset(("onu", "otan", "ovni", "sida", "iva", "nasa", "fifa", "uefa", "unam",
                           "renfe", "opep", "pyme", "pymes", "dana", "covid", "ram", "rom", "led", "pin",
                           "sim"))
ABBREVIATIONS = {
    "EE. UU.": "estados unidos", "EE.UU.": "estados unidos", "Sr.": "señor", "Sra.": "señora",
    "Srta.": "señorita", "Dr.": "doctor", "Dra.": "doctora", "Ud.": "usted", "Uds.": "ustedes",
    "Vd.": "usted", "D.": "don", "Dña.": "doña", "etc.": "etcétera", "pág.": "página",
    "págs.": "páginas", "núm.": "número", "n.º": "número", "nº": "número", "aprox.": "aproximadamente",
    "Av.": "avenida", "Avda.": "avenida", "tel.": "teléfono", "S.A.": "sociedad anónima",
}
# Units after a number: (singular, plural).
UNITS = {"km/h": ("kilómetro por hora", "kilómetros por hora"), "km": ("kilómetro", "kilómetros"),
         "m": ("metro", "metros"), "cm": ("centímetro", "centímetros"),
         "mm": ("milímetro", "milímetros"), "kg": ("kilo", "kilos"), "g": ("gramo", "gramos"),
         "mg": ("miligramo", "miligramos"), "l": ("litro", "litros"), "L": ("litro", "litros"),
         "ml": ("mililitro", "mililitros"), "h": ("hora", "horas"), "min": ("minuto", "minutos"),
         "s": ("segundo", "segundos"), "GB": ("gigabyte", "gigabytes"),
         "MB": ("megabyte", "megabytes"), "TB": ("terabyte", "terabytes"),
         "kWh": ("kilovatio hora", "kilovatios hora"), "kW": ("kilovatio", "kilovatios"),
         "W": ("vatio", "vatios"), "V": ("voltio", "voltios"), "mAh": ("miliamperio hora",
                                                                       "miliamperios hora"),
         "GHz": ("gigahercio", "gigahercios"), "MHz": ("megahercio", "megahercios"),
         "°C": ("grado", "grados"), "℃": ("grado", "grados"), "°": ("grado", "grados")}
CURRENCY = {"US$": ("dólar", "dólares"), "$": ("dólar", "dólares"), "€": ("euro", "euros"),
            "£": ("libra", "libras"), "¥": ("yen", "yenes")}
SYMBOLS = {"&": " y ", "+": " más ", "=": " igual a ", "@": " arroba ", "#": " número ",
           "×": " por ", "/": " ", "%": " por ciento "}
MARK_WORDS = {",": "coma", ".": "punto"}

_A = r"(?<![\w.,])"
_Z = r"(?![\w])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?:\s?(?:h|hs|hrs)(?![\w]))?(?![\d:])")
PHONE = re.compile(r"(?<![\d])(?:\+\d{1,3}[\s-])?\d{2,4}(?:[\s-]\d{2,4}){2,4}(?![\d])"
                   r"|(?<![\d.,])0\d{2,}(?![\d]|[.,]\d)")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")")
MONEY_AFTER = re.compile(_A + r"(" + NUM + r")\s?(" + _CUR_KEYS + r")")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(_A + r"(\d+)\.?(º|ª|er)(?![\w])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)" + _Z)
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])(\s*)(?=([^\W\d_])?)")


def _below_100(n: int) -> str:
    if n < 30:
        return ONES[n]
    t, u = divmod(n, 10)
    return TENS[t] + (f" y {ONES[u]}" if u else "")


def _below_1000(n: int) -> str:
    if n == 100:
        return "cien"
    h, r = divmod(n, 100)
    parts = [HUNDREDS[h]] if h else []
    if r:
        parts.append(_below_100(r))
    return " ".join(parts)


def _below_million(n: int) -> str:
    th, r = divmod(n, 1000)
    parts = []
    if th == 1:
        parts.append("mil")
    elif th:
        parts.append(apocope(_below_1000(th)) + " mil")
    if r:
        parts.append(_below_1000(r))
    return " ".join(parts)


def apocope(words: str) -> str:
    """'uno' -> 'un' at the end (before a noun, mil or millones): veintiuno -> veintiún."""
    if words.endswith("veintiuno"):
        return words[:-9] + "veintiún"
    if words.endswith("uno"):
        return words[:-3] + "un"
    return words


def cardinal(n: int) -> str:
    """Spanish cardinal (masculine): 21 -> veintiuno, 100 -> cien, 1001 -> mil uno,
    2_000_000 -> dos millones, 10**9 -> mil millones."""
    if n < 0:
        return "menos " + cardinal(-n)
    if n == 0:
        return "cero"
    if n >= 10 ** 24:
        return digits(str(n), DIGITS)
    parts = []
    for scale, one, many in SCALES:
        q, n = divmod(n, scale)
        if q == 1:
            parts.append(f"un {one}")
        elif q:
            parts.append(f"{apocope(_below_million(q))} {many}")
    if n:
        parts.append(_below_million(n))
    return " ".join(parts)


def feminine(words: str) -> str:
    """Feminine of a cardinal (la una, veintiuna, doscientas): uno -> una, -ientos -> -ientas."""
    words = re.sub(r"uno$", "una", words)
    words = re.sub(r"veintiuno$", "veintiuna", words)
    return re.sub(r"ientos\b", "ientas", words)


def ordinal(n: int, fem: bool = False) -> str:
    """1 -> primero, 21 -> vigésimo primero; above 999 the cardinal."""
    if not 1 <= n <= 999:
        return cardinal(n)
    h, r = divmod(n, 100)
    t, u = divmod(r, 10)
    parts = [p for p in (ORD_HUNDREDS[h], ORD_TENS[t], ORD_ONES[u]) if p]
    if r in (11, 12):
        parts = [p for p in (ORD_HUNDREDS[h], "undécimo" if r == 11 else "duodécimo") if p]
    out = " ".join(parts)
    return re.sub(r"o\b", "a", out) if fem else out


def number(s: str, before_word: bool = False) -> str:
    """A written number; before_word: an integer ending in uno takes the short form (un, veintiún)."""
    out = read_number(s.lstrip("-"), cardinal, MARK_WORDS, DIGITS)
    if before_word and parse_number(s.lstrip("-"))[1] is None:
        out = apocope(out)
    return ("menos " if s.startswith("-") else "") + out


def _count(s: str) -> tuple[str, bool]:
    """Words of an amount before its unit and whether the unit is singular (exactly one)."""
    n, frac, _ = parse_number(s)
    return number(s, before_word=True), n == 1 and frac is None


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{cardinal(d)} de {MONTHS[m]}"
    if y is not None:
        yy = int(y) + (2000 if len(y) == 2 else 0)
        out += f" de {cardinal(yy)}"
    return f" {out} "


def _time(m: re.Match) -> str:
    h, mi, sec = int(m.group(1)), int(m.group(2)), m.group(3)
    out = feminine(cardinal(h))
    out += f" y {cardinal(mi)}" if mi else " en punto"
    if sec and int(sec):
        out += f" y {cardinal(int(sec))} segundos"
    return f" {out} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    words, one = _count(num)
    return f" {'menos ' if sign else ''}{words} {UNITS[unit][0 if one else 1]} "


def _money(num: str, cur: str) -> str:
    words, one = _count(num)
    return f" {words} {CURRENCY[cur][0 if one else 1]} "


def _number(m: re.Match) -> str:
    sign, num, space, letter = m.groups()
    return f" {number(sign + num, before_word=bool(letter))}{space or ' '}"


def normalize_es(text: str) -> str:
    t = apply_abbreviations(text, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = TIME.sub(_time, t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), DIGITS, "más"), t)
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(2)), t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} por ciento ", t)
    t = UNIT.sub(_unit, t)
    t = ORDINAL.sub(lambda m: f" {_ordinal(int(m.group(1)), m.group(2))} ", t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} a {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, DIGITS)} ", t)
    t = NUMBER.sub(_number, t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    return finish(t)


def _ordinal(n: int, suffix: str) -> str:
    fem = suffix in ("ª", "a", "as")
    words = ordinal(n, fem)
    if suffix == "er":  # 1.er, 3.er: primer, tercer
        words = re.sub(r"(primer|tercer)o$", r"\1", words)
    return words
