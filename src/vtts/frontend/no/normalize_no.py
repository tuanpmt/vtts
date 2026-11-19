"""Norwegian (Bokmål) text normalization for one Norwegian run (the shared scanner of scan_norm.py
with Norwegian tables and number words).

Numbers follow the modern counting (moderne tellemåte): tjueen, tretti, hundre og fem, to tusen og
tjueseks, en million; 1100-1999 without separators is read as a year (1999 -> nitten nittini, 1905
-> nitten hundre og fem). Decimals after "komma". Ordinals: a number with a dot before a lower-case
word (17. mai -> syttende mai; such a dot does not end the sentence) and a day before a month name.
Dates 17.05.2026, 2026-05-17 (syttende mai to tusen og tjueseks), times 14:30 and kl. 14.30
(fjorten tretti), money (5 kr, 50,-, kr 12,50 -> tolv kroner og femti øre, € 5), percent, units,
phone numbers, ranges (10-20 -> ti til tjue), thousands with a space (1 000 000), abbreviations
(f.eks., bl.a., osv., kl.), product codes and acronyms with Norwegian letter names.
"""

from __future__ import annotations

from functools import cache

from ..scan_norm import Currency, Spec, normalize

ONES = ("null", "en", "to", "tre", "fire", "fem", "seks", "sju", "åtte", "ni", "ti", "elleve",
        "tolv", "tretten", "fjorten", "femten", "seksten", "sytten", "atten", "nitten")
TENS = ("", "", "tjue", "tretti", "førti", "femti", "seksti", "sytti", "åtti", "nitti")
SCALES = ((10 ** 12, "billion", "billioner"), (10 ** 9, "milliard", "milliarder"),
          (10 ** 6, "million", "millioner"))
ORD = ("", "første", "andre", "tredje", "fjerde", "femte", "sjette", "sjuende", "åttende", "niende",
       "tiende", "ellevte", "tolvte")
MONTHS = ("", "januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september",
          "oktober", "november", "desember")
LETTERS = {"a": "a", "b": "be", "c": "se", "d": "de", "e": "e", "f": "eff", "g": "ge", "h": "hå",
           "i": "i", "j": "je", "k": "kå", "l": "ell", "m": "em", "n": "en", "o": "o", "p": "pe",
           "q": "ku", "r": "ærr", "s": "ess", "t": "te", "u": "u", "v": "ve", "w": "dobbeltve",
           "x": "eks", "y": "y", "z": "sett", "æ": "æ", "ø": "ø", "å": "å", "é": "e"}
ACRONYM_WORDS = frozenset(("nato", "aids", "covid", "unesco", "unicef", "fifa", "uefa", "nasa",
                           "opec", "ikea", "nav", "ram", "rom", "led", "pin", "sim", "wifi"))
ABBREVIATIONS = {
    "f.eks.": "for eksempel", "bl.a.": "blant annet", "osv.": "og så videre", "o.l.": "og lignende",
    "mv.": "med videre", "m.m.": "med mer", "dvs.": "det vil si", "ca.": "cirka", "ca": "cirka",
    "kl.": "klokken", "nr.": "nummer", "nr": "nummer", "pga.": "på grunn av", "pga": "på grunn av",
    "ifm.": "i forbindelse med", "iht.": "i henhold til", "mht.": "med hensyn til",
    "evt.": "eventuelt", "inkl.": "inklusive", "ekskl.": "eksklusive", "f.Kr.": "før kristus",
    "e.Kr.": "etter kristus", "f. Kr.": "før kristus", "e. Kr.": "etter kristus", "St.": "sankt",
    "dr.": "doktor", "Dr.": "doktor", "prof.": "professor", "jf.": "jamfør", "tlf.": "telefon",
    "etc.": "etcetera", "kap.": "kapittel", "mill.": "millioner", "mrd.": "milliarder", "kr": "kroner",
    "hhv.": "henholdsvis", "o.a.": "og andre",
}
# The same at the start of a sentence (Kl. 14.30, F.eks. ...).
ABBREVIATIONS.update({k[0].upper() + k[1:]: v for k, v in list(ABBREVIATIONS.items())
                      if k[0].islower() and k[0].upper() + k[1:] not in ABBREVIATIONS})
UNITS = {
    "km/h": ("kilometer i timen", "kilometer i timen"), "km": ("kilometer", "kilometer"),
    "m": ("meter", "meter"), "cm": ("centimeter", "centimeter"), "mm": ("millimeter", "millimeter"),
    "dm": ("desimeter", "desimeter"), "m²": ("kvadratmeter", "kvadratmeter"),
    "km²": ("kvadratkilometer", "kvadratkilometer"), "m³": ("kubikkmeter", "kubikkmeter"),
    "ha": ("hektar", "hektar"), "kg": ("kilo", "kilo"), "g": ("gram", "gram"), "hg": ("hekto", "hekto"),
    "mg": ("milligram", "milligram"), "l": ("liter", "liter"), "dl": ("desiliter", "desiliter"),
    "cl": ("centiliter", "centiliter"), "ml": ("milliliter", "milliliter"), "h": ("time", "timer"),
    "min": ("minutt", "minutter"), "s": ("sekund", "sekunder"), "ms": ("millisekund", "millisekunder"),
    "GB": ("gigabyte", "gigabyte"), "MB": ("megabyte", "megabyte"), "TB": ("terabyte", "terabyte"),
    "kB": ("kilobyte", "kilobyte"), "kWh": ("kilowattime", "kilowattimer"),
    "kW": ("kilowatt", "kilowatt"), "W": ("watt", "watt"), "V": ("volt", "volt"),
    "mAh": ("milliamperetime", "milliamperetimer"), "Hz": ("hertz", "hertz"),
    "kHz": ("kilohertz", "kilohertz"), "MHz": ("megahertz", "megahertz"),
    "GHz": ("gigahertz", "gigahertz"), "°C": ("grad celsius", "grader celsius"),
    "℃": ("grad celsius", "grader celsius"), "°F": ("grad fahrenheit", "grader fahrenheit"),
    "°": ("grad", "grader"), "stk": ("stykk", "stykker"), "mil": ("mil", "mil"),
}
CURRENCY = {
    "kr": Currency("krone", "kroner", "øre", "øre"), "kr.": Currency("krone", "kroner", "øre", "øre"),
    "NOK": Currency("krone", "kroner", "øre", "øre"),
    "SEK": Currency("svensk krone", "svenske kroner", "øre", "øre"),
    "DKK": Currency("dansk krone", "danske kroner", "øre", "øre"),
    "€": Currency("euro", "euro", "cent", "cent"), "EUR": Currency("euro", "euro", "cent", "cent"),
    "US$": Currency("dollar", "dollar", "cent", "cent"), "$": Currency("dollar", "dollar", "cent", "cent"),
    "USD": Currency("dollar", "dollar", "cent", "cent"), "£": Currency("pund", "pund", "penny", "pence"),
    "¥": Currency("yen", "yen", "", ""),
}
CURRENCY_BEFORE = ("US$", "kr.", "kr", "€", "$", "£", "¥")
SYMBOLS = {"&": "og", "+": "pluss", "=": "er lik", "@": "krøllalfa", "#": "firkant",
           "×": "ganger", "§": "paragraf", "°": "grader"}


def _below_100(n: int) -> str:
    if n < 20:
        return ONES[n]
    t, u = divmod(n, 10)
    return TENS[t] + (ONES[u] if u else "")


def _below_1000(n: int) -> str:
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts.append("hundre" if h == 1 else f"{ONES[h]} hundre")
    if r:
        parts.append(("og " if h else "") + _below_100(r))
    return " ".join(parts)


def cardinal(n: int) -> str:
    """0 -> null, 1 -> en, 21 -> tjueen, 105 -> hundre og fem, 2026 -> to tusen og tjueseks,
    1250 -> tusen to hundre og femti, 2_500_000 -> to millioner fem hundre tusen."""
    if n == 0:
        return "null"
    parts = []
    for scale, one, many in SCALES:
        q, n = divmod(n, scale)
        if q == 1:
            parts.append(f"en {one}")
        elif q:
            parts.append(f"{cardinal(q)} {many}")
    th, r = divmod(n, 1000)
    if th:
        parts.append("tusen" if th == 1 else f"{_below_1000(th)} tusen")
    if r:
        parts.append(("og " if parts and r < 100 else "") + _below_1000(r))
    return " ".join(parts)


def year(n: int) -> str:
    """1100-1999: 1999 -> nitten nittini, 1900 -> nitten hundre, 1905 -> nitten hundre og fem."""
    h, r = divmod(n, 100)
    if r == 0:
        return f"{_below_100(h)} hundre"
    if r < 10:
        return f"{_below_100(h)} hundre og {ONES[r]}"
    return f"{_below_100(h)} {_below_100(r)}"


def _ord_below_100(r: int) -> str:
    if r <= 12:
        return ORD[r]
    if r < 20:
        return ONES[r] + "de"
    if r % 10 == 0:
        return TENS[r // 10] + ("nde" if TENS[r // 10].endswith("e") else "ende")
    return TENS[r // 10] + ORD[r % 10]


def ordinal(n: int) -> str:
    """1 -> første, 3 -> tredje, 13 -> trettende, 20 -> tjuende, 21 -> tjueførste, 100 -> hundrede,
    101 -> hundre og første, 1000 -> tusende."""
    if n >= 10 ** 6:
        return cardinal(n)
    r = n % 100
    if r == 0:
        return cardinal(n).replace(" ", "") + "de"
    head = cardinal(n - r) if n - r else ""
    return f"{head} og {_ord_below_100(r)}" if head else _ord_below_100(r)


def date(d: int, m: int, y: int | None) -> str:
    out = f"{ordinal(d)} {MONTHS[m]}"
    if y is not None:
        out += " " + (year(y) if 1100 <= y <= 1999 else cardinal(y))
    return out


def time(h: int, mi: int, sec: int | None) -> str:
    out = cardinal(h)
    if mi:
        out += f" null {ONES[mi]}" if mi < 10 else f" {cardinal(mi)}"
    if sec:
        out += f" og {cardinal(sec)} {'sekund' if sec == 1 else 'sekunder'}"
    return out


@cache
def spec() -> Spec:
    return Spec(
        code="no", digits=ONES[:10], cardinal=cardinal, ordinal=ordinal, year=year, date=date, time=time,
        minus="minus", comma="komma", point="punktum", percent="prosent", permille="promille",
        range_word="til", plus="pluss", and_word="og", letters=LETTERS, acronym_words=ACRONYM_WORDS,
        abbreviations=ABBREVIATIONS, units=UNITS, currency=CURRENCY, currency_before=CURRENCY_BEFORE,
        symbols=SYMBOLS, months=MONTHS, ordinal_dot=True, month_ordinal=True,
        time_before=("kl.", "kl", "klokka", "klokken"), dash_money=(",-",), default_currency="kr")


def normalize_no(text: str) -> str:
    return normalize(text, spec())
