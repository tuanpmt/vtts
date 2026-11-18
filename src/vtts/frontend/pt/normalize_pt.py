"""Brazilian Portuguese text normalization for one Portuguese run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces. Accents are kept (they mark stress and vowel quality
for g2p_pt).

Rules, in order: abbreviations (Sr., Dra., etc., vc), quotes and brackets dropped, dates
(5/3/2026, 2026-03-05; day 1 is "primeiro"), times (14:30, 14h30, 14h), phone numbers (digit by
digit), money (R$ 1.250,50, US$ 5, 20 €), percentages, units after a number (5 km, 25 °C),
ordinals (1º, 2ª), ranges (10-20), pause marks, product codes (ESP32: letters by Portuguese name,
digits one by one), numbers (1.250,5 or 1,250.5; "mil e duzentos", "dois mil e vinte e seis"),
symbols, acronyms (spelled: USB -> ú ésse bê; a few read as words: ONU, ENEM).
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

ONES = ("zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
        "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito",
        "dezenove")
TENS = ("", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta",
        "noventa")
HUNDREDS = ("", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
            "setecentos", "oitocentos", "novecentos")
SCALES = ((10 ** 12, "trilhão", "trilhões"), (10 ** 9, "bilhão", "bilhões"),
          (10 ** 6, "milhão", "milhões"), (10 ** 3, "mil", "mil"))
DIGITS = ONES[:10]
MONTHS = ("", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro")
ORD_ONES = ("", "primeiro", "segundo", "terceiro", "quarto", "quinto", "sexto", "sétimo",
            "oitavo", "nono")
ORD_TENS = ("", "décimo", "vigésimo", "trigésimo", "quadragésimo", "quinquagésimo",
            "sexagésimo", "septuagésimo", "octogésimo", "nonagésimo")
ORD_HUNDREDS = ("", "centésimo", "ducentésimo", "trecentésimo", "quadringentésimo",
                "quingentésimo", "sexcentésimo", "septingentésimo", "octingentésimo",
                "noningentésimo")
LETTERS = {"a": "á", "b": "bê", "c": "cê", "d": "dê", "e": "é", "f": "éfe", "g": "gê", "h": "agá",
           "i": "í", "j": "jóta", "k": "cá", "l": "éle", "m": "ême", "n": "êne", "o": "ó",
           "p": "pê", "q": "quê", "r": "érre", "s": "ésse", "t": "tê", "u": "ú", "v": "vê",
           "w": "dáblio", "x": "xís", "y": "ípsilon", "z": "zê"}
ACRONYM_WORDS = frozenset(("onu", "otan", "nasa", "fifa", "covid", "aids", "sus", "enem", "cep",
                           "fies", "ram", "rom", "led", "pin", "sim", "detran", "unesco"))
ABBREVIATIONS = {
    "Sr.": "senhor", "Sra.": "senhora", "Srta.": "senhorita", "Dr.": "doutor", "Dra.": "doutora",
    "Prof.": "professor", "Profa.": "professora", "etc.": "etcétera", "Av.": "avenida",
    "nº": "número", "n.º": "número", "pág.": "página", "tel.": "telefone", "obs.": "observação",
    "vc": "você", "vcs": "vocês", "pq": "porque", "tb": "também", "tbm": "também",
    "Ltda.": "limitada",
}
# Units after a number: (singular, plural).
UNITS = {"km/h": ("quilômetro por hora", "quilômetros por hora"),
         "km": ("quilômetro", "quilômetros"), "m": ("metro", "metros"),
         "cm": ("centímetro", "centímetros"), "mm": ("milímetro", "milímetros"),
         "kg": ("quilo", "quilos"), "g": ("grama", "gramas"), "mg": ("miligrama", "miligramas"),
         "l": ("litro", "litros"), "L": ("litro", "litros"), "ml": ("mililitro", "mililitros"),
         "min": ("minuto", "minutos"), "s": ("segundo", "segundos"),
         "GB": ("gigabaite", "gigabaites"), "MB": ("megabaite", "megabaites"),
         "TB": ("terabaite", "terabaites"), "kWh": ("quilowatt hora", "quilowatts hora"),
         "kW": ("quilowatt", "quilowatts"), "W": ("watt", "watts"), "V": ("volt", "volts"),
         "mAh": ("miliampère hora", "miliampères hora"), "GHz": ("gigahertz", "gigahertz"),
         "MHz": ("megahertz", "megahertz"), "°C": ("grau", "graus"), "℃": ("grau", "graus"),
         "°": ("grau", "graus")}
CURRENCY = {"R$": ("real", "reais"), "US$": ("dólar", "dólares"), "$": ("dólar", "dólares"),
            "€": ("euro", "euros"), "£": ("libra", "libras"), "¥": ("iene", "ienes")}
SYMBOLS = {"&": " e ", "+": " mais ", "=": " igual a ", "@": " arroba ", "#": " número ",
           "×": " vezes ", "/": " ", "%": " por cento "}
MARK_WORDS = {",": "vírgula", ".": "ponto"}

_A = r"(?<![\w.,])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-4])(?::|h)([0-5]\d)(?::([0-5]\d))?(?:\s?h(?![\w]))?(?![\d:])"
                  r"|(?<![\w:.,])([01]?\d|2[0-4])h(?![\w])")
PHONE = re.compile(r"(?<![\d])(?:\+\d{1,3}[\s-])?(?:\(\d{2}\)\s?)?\d{2,5}(?:[\s-]\d{2,5}){1,4}(?![\d])"
                   r"|(?<![\d.,])0\d{2,}(?![\d]|[.,]\d)")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")(\s?(?:milhões|milhão|bilhões|bilhão|mil)(?![\w]))?")
MONEY_AFTER = re.compile(_A + r"(" + NUM + r")\s?(€|£|¥)")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(_A + r"(\d+)\.?(º|ª)(?![\w])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])")


def _below_1000(n: int) -> str:
    if n == 100:
        return "cem"
    h, r = divmod(n, 100)
    parts = [HUNDREDS[h]] if h else []
    if r:
        if r < 20:
            parts.append(ONES[r])
        else:
            t, u = divmod(r, 10)
            parts.append(TENS[t] + (f" e {ONES[u]}" if u else ""))
    return " e ".join(parts)


def cardinal(n: int) -> str:
    """Brazilian Portuguese cardinal (masculine): 21 -> vinte e um, 100 -> cem, 1200 -> mil e
    duzentos, 1234 -> mil duzentos e trinta e quatro, 2026 -> dois mil e vinte e seis,
    2_000_000 -> dois milhões."""
    if n < 0:
        return "menos " + cardinal(-n)
    if n == 0:
        return "zero"
    if n >= 10 ** 15:
        return digits(str(n), DIGITS)
    groups: list[tuple[int, str]] = []
    for scale, one, many in SCALES:
        q, n = divmod(n, scale)
        if q == 1:
            groups.append((q, "mil" if scale == 1000 else f"um {one}"))
        elif q:
            groups.append((q, f"{_below_1000(q)} {many}"))
    if n:
        groups.append((n, _below_1000(n)))
    words = [w for _, w in groups]
    # "e" before the last group when it is below 100 or a round hundred
    if len(groups) > 1 and (groups[-1][0] < 100 or groups[-1][0] % 100 == 0):
        words[-1] = "e " + words[-1]
    return " ".join(words)


def feminine(words: str) -> str:
    """um -> uma, dois -> duas, duzentos -> duzentas (hours, feminine nouns)."""
    words = re.sub(r"\bum$", "uma", words)
    words = re.sub(r"\bdois$", "duas", words)
    return re.sub(r"entos\b", "entas", words)


def ordinal(n: int, fem: bool = False) -> str:
    """1 -> primeiro, 21 -> vigésimo primeiro; above 999 the cardinal."""
    if not 1 <= n <= 999:
        return cardinal(n)
    h, r = divmod(n, 100)
    t, u = divmod(r, 10)
    out = " ".join(p for p in (ORD_HUNDREDS[h], ORD_TENS[t], ORD_ONES[u]) if p)
    return re.sub(r"o\b", "a", out) if fem else out


def number(s: str) -> str:
    return ("menos " if s.startswith("-") else "") + read_number(s.lstrip("-"), cardinal,
                                                                  MARK_WORDS, DIGITS)


def _count(s: str) -> tuple[str, bool]:
    n, frac, _ = parse_number(s)
    return number(s), n == 1 and frac is None


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{'primeiro' if d == 1 else cardinal(d)} de {MONTHS[m]}"
    if y is not None:
        out += f" de {cardinal(int(y) + (2000 if len(y) == 2 else 0))}"
    return f" {out} "


def _time(m: re.Match) -> str:
    if m.group(4) is not None:
        h, mi, sec = int(m.group(4)), 0, 0
    else:
        h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    hours = feminine(cardinal(h))
    out = f"{hours} {'hora' if h == 1 else 'horas'}" if not mi else f"{hours} e {cardinal(mi)}"
    if sec:
        out += f" e {cardinal(sec)} segundos"
    return f" {out} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    words, one = _count(num)
    return f" {'menos ' if sign else ''}{words} {UNITS[unit][0 if one else 1]} "


def _money(num: str, cur: str, scale: str | None = None) -> str:
    """R$ 1.250,50 -> mil duzentos e cinquenta reais e cinquenta centavos; R$ 1,5 milhão -> um
    vírgula cinco milhão de reais."""
    words, one = _count(num)
    if scale:
        return f" {words} {scale.strip()} de {CURRENCY[cur][1]} "
    n, frac, _ = parse_number(num)
    if frac is not None and len(frac) == 2:
        out = f"{cardinal(n)} {CURRENCY[cur][0 if n == 1 else 1]}"
        cents = int(frac)
        if cents:
            out += f" e {cardinal(cents)} {'centavo' if cents == 1 else 'centavos'}"
        return f" {out} "
    return f" {words} {CURRENCY[cur][0 if one else 1]} "


def _ordinal(m: re.Match) -> str:
    return f" {ordinal(int(m.group(1)), m.group(2) == 'ª')} "


def normalize_pt(text: str) -> str:
    t = apply_abbreviations(text, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP.replace("(", "").replace(")", "")})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = TIME.sub(_time, t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), DIGITS, "mais"), t)
    t = t.replace("(", " ").replace(")", " ")
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1), m.group(3)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(2)), t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} por cento ", t)
    t = UNIT.sub(_unit, t)
    t = ORDINAL.sub(_ordinal, t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} a {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, DIGITS)} ", t)
    t = NUMBER.sub(lambda m: f" {number(m.group(1) + m.group(2))} ", t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    return finish(t)
