"""Swedish text normalization for one Swedish run (the shared scanner of scan_norm.py with Swedish
tables and number words).

Numbers below a million are one word (tjugoett, tvåtusentjugosex), one is ett, then miljon(er),
miljard(er), biljon(er) as separate words; 1100-1999 without separators is read in hundreds
(nittonhundranittionio). Decimals after "komma". Ordinals: 1:a, 2:a, 3:e (första, andra, tredje),
and a day before a month name (3 maj -> tredje maj). Dates 2026-05-03, 3/5/2026 (tredje maj
tvåtusentjugosex), times 14:30 and kl. 14.30 (fjorton trettio), money (5 kr, 5:-, 12,50 kr -> tolv
kronor och femtio öre, € 5), percent, units, phone numbers (08-123 45 67), ranges (10-20 -> tio
till tjugo), thousands with a space (1 000 000), abbreviations (t.ex., bl.a., osv., kl.), product
codes and acronyms with Swedish letter names.
"""

from __future__ import annotations

from functools import cache

from ..scan_norm import Currency, Spec, normalize

ONES = ("noll", "ett", "två", "tre", "fyra", "fem", "sex", "sju", "åtta", "nio", "tio", "elva",
        "tolv", "tretton", "fjorton", "femton", "sexton", "sjutton", "arton", "nitton")
TENS = ("", "", "tjugo", "trettio", "fyrtio", "femtio", "sextio", "sjuttio", "åttio", "nittio")
SCALES = ((10 ** 12, "biljon", "biljoner"), (10 ** 9, "miljard", "miljarder"),
          (10 ** 6, "miljon", "miljoner"))
ORD = ("", "första", "andra", "tredje", "fjärde", "femte", "sjätte", "sjunde", "åttonde", "nionde",
       "tionde", "elfte", "tolfte")
MONTHS = ("", "januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september",
          "oktober", "november", "december")
LETTERS = {"a": "a", "b": "be", "c": "se", "d": "de", "e": "e", "f": "eff", "g": "ge", "h": "hå",
           "i": "i", "j": "ji", "k": "kå", "l": "ell", "m": "em", "n": "en", "o": "o", "p": "pe",
           "q": "ku", "r": "ärr", "s": "ess", "t": "te", "u": "u", "v": "ve", "w": "dubbelve",
           "x": "eks", "y": "y", "z": "säta", "å": "å", "ä": "ä", "ö": "ö", "é": "e"}
ACRONYM_WORDS = frozenset(("nato", "aids", "covid", "unesco", "unicef", "fifa", "uefa", "nasa",
                           "opec", "ikea", "saab", "sida", "ram", "rom", "led", "pin", "sim", "wifi"))
ABBREVIATIONS = {
    "t.ex.": "till exempel", "bl.a.": "bland annat", "osv.": "och så vidare",
    "o.s.v.": "och så vidare", "m.m.": "med mera", "dvs.": "det vill säga",
    "d.v.s.": "det vill säga", "ca.": "cirka", "ca": "cirka", "kl.": "klockan", "nr.": "nummer",
    "nr": "nummer", "s.k.": "så kallad", "f.d.": "före detta", "fr.o.m.": "från och med",
    "t.o.m.": "till och med", "p.g.a.": "på grund av", "pga.": "på grund av", "pga": "på grund av",
    "inkl.": "inklusive", "exkl.": "exklusive", "f.Kr.": "före kristus", "e.Kr.": "efter kristus",
    "f. Kr.": "före kristus", "e. Kr.": "efter kristus", "St.": "sankt", "Dr.": "doktor",
    "dr.": "doktor", "prof.": "professor", "jfr.": "jämför", "jfr": "jämför",
    "resp.": "respektive", "tel.": "telefon", "obs.": "observera", "etc.": "etcetera",
    "ev.": "eventuellt", "kap.": "kapitel", "milj.": "miljoner", "mdr": "miljarder", "kr": "kronor",
}
# The same at the start of a sentence (Kl. 14.30, T.ex. ...).
ABBREVIATIONS.update({k[0].upper() + k[1:]: v for k, v in list(ABBREVIATIONS.items())
                      if k[0].islower() and k[0].upper() + k[1:] not in ABBREVIATIONS})
UNITS = {
    "km/h": ("kilometer i timmen", "kilometer i timmen"), "km": ("kilometer", "kilometer"),
    "m": ("meter", "meter"), "cm": ("centimeter", "centimeter"), "mm": ("millimeter", "millimeter"),
    "dm": ("decimeter", "decimeter"), "m²": ("kvadratmeter", "kvadratmeter"),
    "km²": ("kvadratkilometer", "kvadratkilometer"), "m³": ("kubikmeter", "kubikmeter"),
    "ha": ("hektar", "hektar"), "kg": ("kilo", "kilo"), "g": ("gram", "gram"), "hg": ("hekto", "hekto"),
    "mg": ("milligram", "milligram"), "l": ("liter", "liter"), "dl": ("deciliter", "deciliter"),
    "cl": ("centiliter", "centiliter"), "ml": ("milliliter", "milliliter"), "h": ("timme", "timmar"),
    "min": ("minut", "minuter"), "s": ("sekund", "sekunder"), "ms": ("millisekund", "millisekunder"),
    "GB": ("gigabyte", "gigabyte"), "MB": ("megabyte", "megabyte"), "TB": ("terabyte", "terabyte"),
    "kB": ("kilobyte", "kilobyte"), "kWh": ("kilowattimme", "kilowattimmar"),
    "kW": ("kilowatt", "kilowatt"), "W": ("watt", "watt"), "V": ("volt", "volt"),
    "mAh": ("milliamperetimme", "milliamperetimmar"), "Hz": ("hertz", "hertz"),
    "kHz": ("kilohertz", "kilohertz"), "MHz": ("megahertz", "megahertz"),
    "GHz": ("gigahertz", "gigahertz"), "°C": ("grad celsius", "grader celsius"),
    "℃": ("grad celsius", "grader celsius"), "°F": ("grad fahrenheit", "grader fahrenheit"),
    "°": ("grad", "grader"), "st": ("styck", "stycken"), "mil": ("mil", "mil"),
}
CURRENCY = {
    "kr": Currency("krona", "kronor", "öre", "öre"), "kr.": Currency("krona", "kronor", "öre", "öre"),
    "SEK": Currency("krona", "kronor", "öre", "öre"),
    "NOK": Currency("norsk krona", "norska kronor", "öre", "öre"),
    "DKK": Currency("dansk krona", "danska kronor", "öre", "öre"),
    "€": Currency("euro", "euro", "cent", "cent"), "EUR": Currency("euro", "euro", "cent", "cent"),
    "US$": Currency("dollar", "dollar", "cent", "cent"), "$": Currency("dollar", "dollar", "cent", "cent"),
    "USD": Currency("dollar", "dollar", "cent", "cent"), "£": Currency("pund", "pund", "penny", "pence"),
    "¥": Currency("yen", "yen", "", ""),
}
CURRENCY_BEFORE = ("US$", "€", "$", "£", "¥")
SYMBOLS = {"&": "och", "+": "plus", "=": "är lika med", "@": "snabel a", "#": "fyrkant",
           "×": "gånger", "§": "paragraf", "°": "grader"}


def _below_100(n: int) -> str:
    if n < 20:
        return ONES[n]
    t, u = divmod(n, 10)
    return TENS[t] + (ONES[u] if u else "")


def _below_1000(n: int) -> str:
    h, r = divmod(n, 100)
    out = ("" if h == 1 else ONES[h]) + "hundra" if h else ""
    return out + (_below_100(r) if r else "")


def _below_million(n: int) -> str:
    th, r = divmod(n, 1000)
    out = ("" if th == 1 else _below_1000(th)) + "tusen" if th else ""
    return out + (_below_1000(r) if r else "")


def cardinal(n: int) -> str:
    """0 -> noll, 1 -> ett, 21 -> tjugoett, 2026 -> tvåtusentjugosex, 2_500_000 -> två miljoner
    femhundratusen."""
    if n == 0:
        return "noll"
    parts = []
    for scale, one, many in SCALES:
        q, n = divmod(n, scale)
        if q == 1:
            parts.append(f"en {one}")
        elif q:
            parts.append(f"{cardinal(q)} {many}")
    if n:
        parts.append(_below_million(n))
    return " ".join(parts)


def year(n: int) -> str:
    """1100-1999 in hundreds: 1999 -> nittonhundranittionio."""
    h, r = divmod(n, 100)
    return _below_100(h) + "hundra" + (_below_100(r) if r else "")


def ordinal(n: int) -> str:
    """1 -> första, 3 -> tredje, 13 -> trettonde, 20 -> tjugonde, 21 -> tjugoförsta, 100 ->
    hundrade, 1000 -> tusende."""
    if n >= 10 ** 6:
        return cardinal(n)
    r = n % 100
    head = _below_million(n - r) if n - r else ""
    if r == 0:
        return head + "de"
    if r <= 12:
        tail = ORD[r]
    elif r < 20:
        tail = ONES[r] + "de"
    elif r % 10 == 0:
        tail = TENS[r // 10] + "nde"
    else:
        tail = TENS[r // 10] + ORD[r % 10]
    return head + tail


def date(d: int, m: int, y: int | None) -> str:
    out = f"{ordinal(d)} {MONTHS[m]}"
    if y is not None:
        out += " " + (year(y) if 1100 <= y <= 1999 else cardinal(y))
    return out


def time(h: int, mi: int, sec: int | None) -> str:
    out = cardinal(h)
    if mi:
        out += f" noll {ONES[mi]}" if mi < 10 else f" {cardinal(mi)}"
    if sec:
        out += f" och {cardinal(sec)} {'sekund' if sec == 1 else 'sekunder'}"
    return out


@cache
def spec() -> Spec:
    return Spec(
        code="sv", digits=ONES[:10], cardinal=cardinal, ordinal=ordinal, year=year, date=date, time=time,
        minus="minus", comma="komma", point="punkt", percent="procent", permille="promille",
        range_word="till", plus="plus", and_word="och", letters=LETTERS, acronym_words=ACRONYM_WORDS,
        abbreviations=ABBREVIATIONS, units=UNITS, currency=CURRENCY, currency_before=CURRENCY_BEFORE,
        symbols=SYMBOLS, months=MONTHS, ordinal_suffixes=(":a", ":e"), month_ordinal=True,
        time_before=("kl.", "kl", "klockan"), dash_money=(":-", ",-"), default_currency="kr")


def normalize_sv(text: str) -> str:
    return normalize(text, spec())
