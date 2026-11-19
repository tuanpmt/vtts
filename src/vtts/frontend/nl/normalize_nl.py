"""Dutch text normalization for one Dutch run (the shared scanner of scan_norm.py with Dutch
tables and number words).

Numbers below a million are one word (eenentwintig, tweeduizendzesentwintig; 22 -> tweeëntwintig),
one alone is één, then miljoen, miljard, biljoen as separate words; 1100-1999 without separators is
read in hundreds (negentienhonderdnegenennegentig). Decimals after "komma" (one or two digits
without a leading zero as a number, else digit by digit). Ordinals: 1e, 2de, 3e, 8ste (eerste,
tweede, derde, achtste, twintigste ...). Dates 3-5-2026, 2026-05-03 (drie mei
tweeduizendzesentwintig), times 14:30 / 14.30 uur (veertien uur dertig), money (€ 5,50 -> vijf
euro en vijftig cent; 5,- -> vijf euro), percent, units, phone numbers, ranges (10-20 -> tien tot
twintig), abbreviations (bijv., o.a., d.w.z. ...), product codes and acronyms with Dutch letter
names. A leading apostrophe stays on 's 't 'n.
"""

from __future__ import annotations

from functools import cache

from ..scan_norm import Currency, Spec, normalize

ONES = ("nul", "een", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien",
        "elf", "twaalf", "dertien", "veertien", "vijftien", "zestien", "zeventien", "achttien",
        "negentien")
TENS = ("", "", "twintig", "dertig", "veertig", "vijftig", "zestig", "zeventig", "tachtig",
        "negentig")
SCALES = ((10 ** 12, "biljoen"), (10 ** 9, "miljard"), (10 ** 6, "miljoen"))
MONTHS = ("", "januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
          "september", "oktober", "november", "december")
LETTERS = {"a": "a", "b": "bee", "c": "cee", "d": "dee", "e": "ee", "f": "ef", "g": "gee",
           "h": "ha", "i": "ie", "j": "jee", "k": "ka", "l": "el", "m": "em", "n": "en", "o": "oo",
           "p": "pee", "q": "kuu", "r": "er", "s": "es", "t": "tee", "u": "uu", "v": "vee",
           "w": "wee", "x": "iks", "y": "ij", "z": "zet", "é": "ee", "ë": "ee", "ï": "ie",
           "ö": "oo", "ü": "uu"}
ACRONYM_WORDS = frozenset(("navo", "nato", "aids", "covid", "unesco", "unicef", "fifa", "uefa",
                           "nasa", "opec", "benelux", "havo", "vwo", "mavo", "vmbo", "pabo",
                           "ram", "rom", "led", "pin", "sim", "wifi", "knvb", "anwb"))
ABBREVIATIONS = {
    "bijv.": "bijvoorbeeld", "bv.": "bijvoorbeeld", "b.v.": "bijvoorbeeld", "enz.": "enzovoort",
    "e.d.": "en dergelijke", "e.a.": "en anderen", "o.a.": "onder andere",
    "d.w.z.": "dat wil zeggen", "m.a.w.": "met andere woorden", "i.p.v.": "in plaats van",
    "t.o.v.": "ten opzichte van", "m.b.t.": "met betrekking tot", "a.d.h.v.": "aan de hand van",
    "n.a.v.": "naar aanleiding van", "m.n.": "met name", "z.s.m.": "zo snel mogelijk",
    "t/m": "tot en met", "v.Chr.": "voor christus", "n.Chr.": "na christus",
    "v. Chr.": "voor christus", "n. Chr.": "na christus", "ca.": "circa", "nr.": "nummer",
    "blz.": "bladzijde", "dhr.": "de heer", "mevr.": "mevrouw", "Dr.": "doctor", "dr.": "doctor",
    "Mr.": "meester", "mr.": "meester", "Prof.": "professor", "prof.": "professor",
    "ir.": "ingenieur", "drs.": "doctorandus", "St.": "sint", "jr.": "junior", "sr.": "senior",
    "a.s.": "aanstaande", "incl.": "inclusief", "excl.": "exclusief", "max.": "maximaal",
    "min.": "minimaal", "vs.": "versus", "evt.": "eventueel", "resp.": "respectievelijk",
    "vgl.": "vergelijk", "zgn.": "zogenaamde", "afb.": "afbeelding", "etc.": "etcetera",
    "'t": "het", "'n": "een",
}
UNITS = {
    "km/h": ("kilometer per uur", "kilometer per uur"), "km": ("kilometer", "kilometer"),
    "m": ("meter", "meter"), "cm": ("centimeter", "centimeter"), "mm": ("millimeter", "millimeter"),
    "m²": ("vierkante meter", "vierkante meter"), "km²": ("vierkante kilometer", "vierkante kilometer"),
    "m³": ("kubieke meter", "kubieke meter"), "ha": ("hectare", "hectare"),
    "kg": ("kilo", "kilo"), "g": ("gram", "gram"), "mg": ("milligram", "milligram"),
    "l": ("liter", "liter"), "ml": ("milliliter", "milliliter"), "cl": ("centiliter", "centiliter"),
    "dl": ("deciliter", "deciliter"), "h": ("uur", "uur"), "min": ("minuut", "minuten"),
    "s": ("seconde", "seconden"), "sec": ("seconde", "seconden"), "ms": ("milliseconde", "milliseconden"),
    "GB": ("gigabyte", "gigabyte"), "MB": ("megabyte", "megabyte"), "TB": ("terabyte", "terabyte"),
    "kB": ("kilobyte", "kilobyte"), "kWh": ("kilowattuur", "kilowattuur"), "kW": ("kilowatt", "kilowatt"),
    "W": ("watt", "watt"), "V": ("volt", "volt"), "mAh": ("milliampère uur", "milliampère uur"),
    "Hz": ("hertz", "hertz"), "kHz": ("kilohertz", "kilohertz"), "MHz": ("megahertz", "megahertz"),
    "GHz": ("gigahertz", "gigahertz"), "°C": ("graad celsius", "graden celsius"),
    "℃": ("graad celsius", "graden celsius"), "°F": ("graad fahrenheit", "graden fahrenheit"),
    "°": ("graad", "graden"), "pk": ("pk", "pk"),
}
CURRENCY = {
    "€": Currency("euro", "euro", "cent", "cent"), "EUR": Currency("euro", "euro", "cent", "cent"),
    "US$": Currency("dollar", "dollar", "cent", "cent"), "$": Currency("dollar", "dollar", "cent", "cent"),
    "USD": Currency("dollar", "dollar", "cent", "cent"), "£": Currency("pond", "pond", "penny", "pence"),
    "¥": Currency("yen", "yen", "", ""), "ƒ": Currency("gulden", "gulden", "cent", "cent"),
}
CURRENCY_BEFORE = ("US$", "€", "$", "£", "¥", "ƒ")
SYMBOLS = {"&": "en", "+": "plus", "=": "is gelijk aan", "@": "apenstaartje", "#": "hekje",
           "×": "keer", "§": "paragraaf", "°": "graden"}


def _below_100(n: int) -> str:
    if n < 20:
        return ONES[n]
    t, u = divmod(n, 10)
    if not u:
        return TENS[t]
    unit = ONES[u]
    return unit + ("ën" if unit.endswith("e") else "en") + TENS[t]


def _below_1000(n: int) -> str:
    h, r = divmod(n, 100)
    out = ("" if h == 1 else ONES[h]) + "honderd" if h else ""
    return out + (_below_100(r) if r else "")


def _below_million(n: int) -> str:
    th, r = divmod(n, 1000)
    out = ("" if th == 1 else _below_1000(th)) + "duizend" if th else ""
    return out + (_below_1000(r) if r else "")


def cardinal(n: int) -> str:
    """0 -> nul, 1 -> één, 21 -> eenentwintig, 2026 -> tweeduizendzesentwintig,
    2_500_000 -> twee miljoen vijfhonderdduizend."""
    if n == 0:
        return "nul"
    if n == 1:
        return "één"
    parts = []
    for scale, name in SCALES:
        q, n = divmod(n, scale)
        if q:
            parts.append(f"{cardinal(q)} {name}")
    if n:
        parts.append(_below_million(n))
    return " ".join(parts)


def year(n: int) -> str:
    """1100-1999 in hundreds: 1999 -> negentienhonderdnegenennegentig."""
    h, r = divmod(n, 100)
    return _below_100(h) + "honderd" + (_below_100(r) if r else "")


def ordinal(n: int) -> str:
    """1 -> eerste, 2 -> tweede, 3 -> derde, 8 -> achtste, 20 -> twintigste, 21 ->
    eenentwintigste, 100 -> honderdste, 101 -> honderdeerste."""
    words = cardinal(n)
    if words.endswith("één"):
        words = words[:-3] + "een"
    for end, rep in (("een", "eerste"), ("twee", "tweede"), ("drie", "derde"), ("acht", "achtste")):
        if words.endswith(end) and not words.endswith("tien" + end):
            return words[:-len(end)] + rep
    if words.endswith(("tig", "honderd", "duizend", "joen", "jard")):
        return words + "ste"
    return words + "de"


def date(d: int, m: int, y: int | None) -> str:
    out = f"{cardinal(d)} {MONTHS[m]}"
    if y is not None:
        out += " " + (year(y) if 1100 <= y <= 1999 else cardinal(y))
    return out


def time(h: int, mi: int, sec: int | None) -> str:
    out = f"{cardinal(h)} uur"
    if mi:
        out += f" {cardinal(mi)}"
    if sec:
        out += f" en {cardinal(sec)} {'seconde' if sec == 1 else 'seconden'}"
    return out


@cache
def spec() -> Spec:
    return Spec(
        code="nl", digits=("nul", "één", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen"),
        cardinal=cardinal, ordinal=ordinal, year=year, date=date, time=time,
        minus="min", comma="komma", point="punt", percent="procent", permille="promille",
        range_word="tot", plus="plus", and_word="en", letters=LETTERS, acronym_words=ACRONYM_WORDS,
        abbreviations=ABBREVIATIONS, units=UNITS, currency=CURRENCY, currency_before=CURRENCY_BEFORE,
        symbols=SYMBOLS, months=MONTHS, ordinal_suffixes=("ste", "de", "e"), time_after=("uur",),
        leading_apostrophe=True, dash_money=(",-",), default_currency="€")


def normalize_nl(text: str) -> str:
    return normalize(text, spec())
