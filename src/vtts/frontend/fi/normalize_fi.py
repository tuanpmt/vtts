"""Finnish text normalization for one Finnish run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces.

Rules, in order: abbreviations (esim., jne., n., klo, mm., eKr.), quotes and brackets dropped,
dates (3.5.2026, 3.5., 2026-05-03, 3/5/2026: ordinal day + month name, as "kolmas toukokuuta"),
times (klo 14.30, kello 9, 14:30; H.MM is a time anywhere, since the decimal mark is a comma), thousands separated by spaces (1 000 000), phone numbers
(digit by digit), money (5 €, 12,50 €, $5: partitive after numbers other than one), percentages
(15 % -> viisitoista prosenttia), units after a number (5 km -> viisi kilometriä, 1 km -> yksi
kilometri), ordinals with a dot before a lower-case word (3. toukokuuta -> kolmas toukokuuta,
1. maailmansota), ranges (10–20 -> kymmenestä kahteenkymmeneen), pause marks, product codes
(ESP32: letters by Finnish name, digits one by one), numbers (decimal comma: 3,5 -> kolme pilkku
viisi; negative -5 -> miinus viisi), symbols, acronyms (spelled: USB -> uu äs bee; a few read as
words: Nato, Yle).

Numbers are read in the nominative case. Below a million they are written as one word, as in
Finnish spelling (2026 -> kaksituhattakaksikymmentäkuusi); miljoona and miljardi are separate
words (2 500 000 -> kaksi miljoonaa viisisataatuhatta). g2p_fi splits number words into their
parts for the stresses.
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
    spell,
)

ONES = ("nolla", "yksi", "kaksi", "kolme", "neljä", "viisi", "kuusi", "seitsemän", "kahdeksan",
        "yhdeksän")
DIGITS = ONES
SCALES = ((10 ** 9, "miljardi", "miljardia"), (10 ** 6, "miljoona", "miljoonaa"))
MONTHS = ("", "tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta", "toukokuuta", "kesäkuuta",
          "heinäkuuta", "elokuuta", "syyskuuta", "lokakuuta", "marraskuuta", "joulukuuta")
ORD_ONES = ("", "ensimmäinen", "toinen", "kolmas", "neljäs", "viides", "kuudes", "seitsemäs",
            "kahdeksas", "yhdeksäs")
# Ordinal parts inside a compound (yhdestoista, kahdeskymmenes, kahdessadas).
ORD_PARTS = ("", "yhdes", "kahdes", *ORD_ONES[3:])
# Elative (from) and illative (to) of the parts of a cardinal, for ranges.
ELATIVE = {"nolla": "nollasta", "yksi": "yhdestä", "kaksi": "kahdesta", "kolme": "kolmesta",
           "neljä": "neljästä", "viisi": "viidestä", "kuusi": "kuudesta",
           "seitsemän": "seitsemästä", "kahdeksan": "kahdeksasta", "yhdeksän": "yhdeksästä",
           "kymmenen": "kymmenestä", "kymmentä": "kymmenestä", "toista": "toista",
           "sata": "sadasta", "sataa": "sadasta", "tuhat": "tuhannesta", "tuhatta": "tuhannesta",
           "miljoona": "miljoonasta", "miljoonaa": "miljoonasta", "miljardi": "miljardista",
           "miljardia": "miljardista"}
ILLATIVE = {"nolla": "nollaan", "yksi": "yhteen", "kaksi": "kahteen", "kolme": "kolmeen",
            "neljä": "neljään", "viisi": "viiteen", "kuusi": "kuuteen", "seitsemän": "seitsemään",
            "kahdeksan": "kahdeksaan", "yhdeksän": "yhdeksään", "kymmenen": "kymmeneen",
            "kymmentä": "kymmeneen", "toista": "toista", "sata": "sataan", "sataa": "sataan",
            "tuhat": "tuhanteen", "tuhatta": "tuhanteen", "miljoona": "miljoonaan",
            "miljoonaa": "miljoonaan", "miljardi": "miljardiin", "miljardia": "miljardiin"}
LETTERS = {"a": "aa", "b": "bee", "c": "see", "d": "dee", "e": "ee", "f": "äf", "g": "gee",
           "h": "hoo", "i": "ii", "j": "jii", "k": "koo", "l": "äl", "m": "äm", "n": "än",
           "o": "oo", "p": "pee", "q": "kuu", "r": "är", "s": "äs", "t": "tee", "u": "uu",
           "v": "vee", "w": "kaksoisvee", "x": "äks", "y": "yy", "z": "tset", "å": "ruotsalainen oo",
           "ä": "ää", "ö": "öö"}
ACRONYM_WORDS = frozenset(("nato", "yle", "nasa", "hus", "unesco", "unicef", "fifa", "uefa", "opec",
                           "kela", "alko", "sitra", "led", "pin", "ram", "rom", "sim", "covid",
                           "aids", "hifi", "vr"))
ABBREVIATIONS = {
    "esim.": "esimerkiksi", "Esim.": "esimerkiksi", "jne.": "ja niin edelleen",
    "yms.": "ynnä muuta sellaista", "ym.": "ynnä muuta", "mm.": "muun muassa",
    "Mm.": "muun muassa", "ns.": "niin sanottu", "nk.": "niin kutsuttu", "ks.": "katso",
    "Ks.": "katso", "ts.": "toisin sanoen", "vrt.": "vertaa", "n.": "noin", "klo": "kello",
    "Klo": "kello", "eKr.": "ennen Kristusta", "jKr.": "jälkeen Kristuksen",
    "eaa.": "ennen ajanlaskun alkua", "jaa.": "jälkeen ajanlaskun alun", "tri": "tohtori",
    "Tri": "tohtori", "prof.": "professori", "Prof.": "professori", "kpl": "kappaletta",
    "milj.": "miljoonaa", "mrd.": "miljardia", "puh.": "puhelin", "nro": "numero",
    "Nro": "numero", "huom.": "huomaa", "Huom.": "huomaa", "ry": "rekisteröity yhdistys",
    "Oy": "osakeyhtiö", "Oyj": "julkinen osakeyhtiö", "alk.": "alkaen", "vs.": "versus",
    "o.s.": "omaa sukua", "s.": "syntynyt", "k.": "kuollut", "v.": "vuonna",
}
# Units after a number: (nominative after 1, partitive after other numbers).
UNITS = {"km/h": ("kilometri tunnissa", "kilometriä tunnissa"), "km": ("kilometri", "kilometriä"),
         "m": ("metri", "metriä"), "cm": ("senttimetri", "senttimetriä"),
         "mm": ("millimetri", "millimetriä"), "kg": ("kilo", "kiloa"), "g": ("gramma", "grammaa"),
         "mg": ("milligramma", "milligrammaa"), "l": ("litra", "litraa"), "L": ("litra", "litraa"),
         "dl": ("desilitra", "desilitraa"), "ml": ("millilitra", "millilitraa"),
         "h": ("tunti", "tuntia"), "min": ("minuutti", "minuuttia"), "s": ("sekunti", "sekuntia"),
         "GB": ("gigatavu", "gigatavua"), "MB": ("megatavu", "megatavua"),
         "TB": ("teratavu", "teratavua"), "kWh": ("kilowattitunti", "kilowattituntia"),
         "kW": ("kilowatti", "kilowattia"), "W": ("watti", "wattia"), "V": ("voltti", "volttia"),
         "mAh": ("milliampeeritunti", "milliampeerituntia"), "GHz": ("gigahertsi", "gigahertsiä"),
         "MHz": ("megahertsi", "megahertsiä"), "°C": ("aste", "astetta"), "℃": ("aste", "astetta"),
         "°": ("aste", "astetta")}
CURRENCY = {"€": ("euro", "euroa"), "EUR": ("euro", "euroa"), "US$": ("dollari", "dollaria"),
            "$": ("dollari", "dollaria"), "£": ("punta", "puntaa"), "¥": ("jeni", "jeniä")}
SYMBOLS = {"&": " ja ", "+": " plus ", "=": " on ", "@": " ät ", "#": " risuaita ",
           "×": " kertaa ", "/": " ", "%": " prosenttia "}
MARK_WORDS = {",": "pilkku", ".": "piste"}

_A = r"(?<![\w.,])"
_Z = r"(?![\w])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
# Phone numbers starting with + or 0 are read before the spaces of thousands are removed.
PHONE_FIRST = re.compile(r"(?<![\d])(?<!\d\s)(?:\+\d{1,3}|0\d{1,3})(?:[\s-]\d{2,7}){1,4}(?![\d])")
SPACE_THOUSANDS = re.compile(r"(?<![\d,.])[1-9]\d{0,2}(?:[   ]\d{3})+(?![\d])")
DATE_DOT = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})?(?![\d])")
DATE_SLASH = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME_DOT = re.compile(r"(?<=kello)(\s+)([01]?\d|2[0-4])(?:[.:]([0-5]\d))?(?![\d]|[.,]\d)")
TIME_HM = re.compile(r"(?<![\d.,:])([01]?\d|2[0-3])\.([0-5]\d)(?![\d]|[.,]\d)")
TIME = re.compile(r"(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])")
PHONE = re.compile(r"(?<![\d])(?:\+\d{1,3}[\s-])?\d{2,4}(?:[\s-]\d{2,4}){2,4}(?![\d])"
                   r"|(?<![\d.,])0\d{2,}(?![\d]|[.,]\d)")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")")
MONEY_AFTER = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _CUR_KEYS + r")(?![\w])")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(_A + r"(\d+)\.(?=\s+[a-zåäö])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)" + _Z)
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])")


def _below_100(n: int) -> list[str]:
    if n < 10:
        return [ONES[n]]
    if n == 10:
        return ["kymmenen"]
    t, u = divmod(n, 10)
    if t == 1:
        return [ONES[u], "toista"]
    return [ONES[t], "kymmentä"] + ([ONES[u]] if u else [])


def _below_1000(n: int) -> list[str]:
    h, r = divmod(n, 100)
    parts = [] if not h else ["sata"] if h == 1 else [ONES[h], "sataa"]
    return parts + (_below_100(r) if r or not h else [])


def _below_million(n: int) -> list[str]:
    th, r = divmod(n, 1000)
    parts = [] if not th else ["tuhat"] if th == 1 else [*_below_1000(th), "tuhatta"]
    return parts + (_below_1000(r) if r or not th else [])


def cardinal_groups(n: int) -> list[list[str]]:
    """Parts of a cardinal (n >= 0), one list per written word: 2_500_000 ->
    [[kaksi], [miljoonaa], [viisi, sataa, tuhatta]]."""
    if n == 0:
        return [["nolla"]]
    groups: list[list[str]] = []
    for scale, one, many in SCALES:
        q, n = divmod(n, scale)
        if q == 1:
            groups.append([one])
        elif q:
            groups += [_below_million(q), [many]] if q < 10 ** 6 else [*cardinal_groups(q), [many]]
    if n:
        groups.append(_below_million(n))
    return groups


def cardinal(n: int) -> str:
    """Finnish cardinal (nominative): 21 -> kaksikymmentäyksi, 1000 -> tuhat,
    2026 -> kaksituhattakaksikymmentäkuusi, 2_000_000 -> kaksi miljoonaa."""
    if n < 0:
        return "miinus " + cardinal(-n)
    if n >= 10 ** 15:
        return digits(str(n), DIGITS)
    return " ".join("".join(g) for g in cardinal_groups(n))


def inflect(n: int, table: dict[str, str]) -> str:
    """A cardinal in the elative or illative case: every part is inflected
    (20 -> kahdestakymmenestä, kahteenkymmeneen)."""
    if n < 0 or n >= 10 ** 15:
        return cardinal(n)
    return " ".join("".join(table[p] for p in g) for g in cardinal_groups(n))


def _ordinal_below_1000(n: int, final: bool) -> str:
    h, r = divmod(n, 100)
    out = "" if not h else "sadas" if h == 1 else ORD_PARTS[h] + "sadas"
    t, u = divmod(r, 10)
    if r == 10:
        out += "kymmenes"
    elif t == 1:
        out += ORD_PARTS[u] + "toista"
    else:
        if t:
            out += ORD_PARTS[t] + "kymmenes"
        if u:
            out += ORD_ONES[u] if final else ORD_PARTS[u]
    return out


def ordinal(n: int) -> str:
    """Finnish ordinal (nominative): 1 -> ensimmäinen, 3 -> kolmas, 11 -> yhdestoista,
    21 -> kahdeskymmenesensimmäinen, 100 -> sadas, 2000 -> kahdestuhannes; from 10 000 the
    cardinal."""
    if not 1 <= n <= 9999:
        return cardinal(n)
    th, r = divmod(n, 1000)
    out = "" if not th else "tuhannes" if th == 1 else ORD_PARTS[th] + "tuhannes"
    return out + (_ordinal_below_1000(r, final=True) if r else "")


def number(s: str) -> str:
    """A written number: decimal comma (or point) read as pilkku/piste, decimals of one or two
    digits without a leading zero as a number, else digit by digit."""
    neg = s.startswith("-")
    n, frac, mark = parse_number(s.lstrip("-"))
    out = cardinal(n)
    if frac is not None:
        if len(frac) <= 2 and not frac.startswith("0"):
            out += f" {MARK_WORDS[mark]} {cardinal(int(frac))}"
        else:
            out += f" {MARK_WORDS[mark]} " + digits(frac, DIGITS)
    return ("miinus " if neg else "") + out


def _is_one(s: str) -> bool:
    n, frac, _ = parse_number(s.lstrip("-"))
    return n == 1 and frac is None


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{ordinal(d)} {MONTHS[m]}"
    if y is not None:
        out += f" {cardinal(int(y) + (2000 if len(y) == 2 else 0))}"
    return f" {out} "


def _date_dot(m: re.Match) -> str:
    """3.5.2026 and 3.5. (with the final dot); 3.5 alone is a decimal number."""
    return _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0)


def _clock(h: int, mi: int | None) -> str:
    out = cardinal(h)
    if mi:
        out += " " + (f"nolla {ONES[mi]}" if mi < 10 else cardinal(mi))
    return out


def _time(m: re.Match) -> str:
    h, mi, sec = int(m.group(1)), int(m.group(2)), m.group(3)
    out = _clock(h, mi)
    if sec and int(sec):
        out += f" ja {cardinal(int(sec))} sekuntia"
    return f" {out} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    one = _is_one(num)
    return f" {number(sign + num)} {UNITS[unit][0 if one else 1]} "


def _money(num: str, cur: str, sign: str = "") -> str:
    one, many = CURRENCY[cur]
    n, frac, _ = parse_number(num)
    if frac is not None and len(frac) == 2 and cur in ("€", "EUR"):
        out = f"{cardinal(n)} {one if n == 1 else many}"
        if int(frac):
            out += f" {cardinal(int(frac))} {'sentti' if int(frac) == 1 else 'senttiä'}"
        return f" {'miinus ' if sign else ''}{out} "
    return f" {number(sign + num)} {one if _is_one(num) else many} "


def _percent(m: re.Match) -> str:
    sign, num = m.groups()
    return f" {number(sign + num)} {'prosentti' if _is_one(num) else 'prosenttia'} "


def normalize_fi(text: str) -> str:
    t = apply_abbreviations(text, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP})
    t = PHONE_FIRST.sub(lambda m: phone_digits(m.group(0), DIGITS, "plus"), t)
    t = SPACE_THOUSANDS.sub(lambda m: re.sub(r"[   ]", "", m.group(0)), t)
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_SLASH.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = TIME_DOT.sub(lambda m: f" {_clock(int(m.group(2)), int(m.group(3) or 0))} ", t)
    t = DATE_DOT.sub(_date_dot, t)
    t = TIME_HM.sub(lambda m: f" {_clock(int(m.group(1)), int(m.group(2)))} ", t)
    t = TIME.sub(_time, t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), DIGITS, "plus"), t)
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(2), m.group(3), m.group(1)), t)
    t = PERCENT.sub(_percent, t)
    t = UNIT.sub(_unit, t)
    t = ORDINAL.sub(lambda m: f" {ordinal(int(m.group(1)))} ", t)
    t = RANGE.sub(lambda m: f" {inflect(int(m.group(1)), ELATIVE)} "
                            f"{inflect(int(m.group(2)), ILLATIVE)} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, DIGITS)} ", t)
    t = NUMBER.sub(lambda m: f" {number(m.group(1) + m.group(2))} ", t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    return finish(t)
