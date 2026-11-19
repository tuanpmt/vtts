"""Tagalog (Filipino) text normalization for one Tagalog run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces; words may hold an apostrophe (the contractions 't and 'y,
and a glottal stop written for a hyphen before a vowel: mag-aral -> mag'aral), which g2p_tl reads.

Numbers. Counts and most numbers are read with the native Tagalog numbers (isa, dalawa ...
sampu, labing isa, dalawampu't isa, isang daan, isang libo, isang milyon; "at" before the last
part: isang daan at dalawampu't lima), with the linker before a noun (limang kilometro, apat na
porsiyento). Two places follow the everyday Spanish-derived norm instead:
- clock times: alas + the Spanish hour (ala una, alas dos ... alas dose), minutes with i: 3:15 ->
  alas tres i kinse, 3:30 -> alas tres i medya, 3:45 -> alas tres i kuwarenta'y singko; hours
  13-23 are read on the 12-hour clock with ng hapon (13-17) or ng gabi (18-23) unless the text
  says the part of the day; 0:xx is alas dose ng hatinggabi;
- whole peso prices from 2 to 999 (₱50 -> singkuwenta pesos, ₱250 -> dos siyentos singkuwenta
  pesos); 1 peso, larger amounts and amounts with centavos use the native numbers with piso and
  sentimo (₱1,500 -> isang libo at limang daang piso).
Decimals: punto and the decimals digit by digit (3.14 -> tatlo punto isa apat); Philippine
marks (1,250.50). Dates are read as ika- + day + ng + month + year (11/19/2026, month first as in
the Philippines; 2026-11-19; Nobyembre 19, 2026; 19 Nobyembre 2026). Ordinals: ika-3 -> ikatlo,
ika-1 -> una. Phone numbers digit by digit with sero for 0. Letter names follow the English
alphabet as Filipinos spell acronyms (DOH -> di o eyts).
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

ONES = ("sero", "isa", "dalawa", "tatlo", "apat", "lima", "anim", "pito", "walo", "siyam")
TEENS = ("sampu", "labing isa", "labindalawa", "labintatlo", "labing apat", "labinlima",
         "labing anim", "labimpito", "labingwalo", "labinsiyam")
TENS = ("", "", "dalawampu", "tatlumpu", "apatnapu", "limampu", "animnapu", "pitumpu", "walumpu",
        "siyamnapu")
SCALES = ((10 ** 12, "trilyon"), (10 ** 9, "bilyon"), (10 ** 6, "milyon"), (1000, "libo"))
ES_ONES = ("", "uno", "dos", "tres", "kuwatro", "singko", "sais", "siyete", "otso", "nuwebe", "diyes",
           "onse", "dose", "trese", "katorse", "kinse", "disisais", "disisiyete", "disiotso",
           "disinuwebe")
ES_TENS = ("", "", "beynte", "treynta", "kuwarenta", "singkuwenta", "sesenta", "setenta", "otsenta",
           "nobenta")
ES_HUNDREDS = ("", "siyento", "dos siyentos", "tres siyentos", "kuwatro siyentos", "kinyentos",
               "sais siyentos", "siyete siyentos", "otso siyentos", "nobe siyentos")
MONTHS = ("", "enero", "pebrero", "marso", "abril", "mayo", "hunyo", "hulyo", "agosto", "setyembre",
          "oktubre", "nobyembre", "disyembre")
MONTH_ABBR = {"ene": 1, "peb": 2, "mar": 3, "abr": 4, "may": 5, "hun": 6, "hul": 7, "ago": 8,
              "set": 9, "okt": 10, "nob": 11, "dis": 12}
LETTERS = {"a": "ey", "b": "bi", "c": "si", "d": "di", "e": "i", "f": "ef", "g": "dyi", "h": "eyts",
           "i": "ay", "j": "dyey", "k": "key", "l": "el", "m": "em", "n": "en", "o": "o", "p": "pi",
           "q": "kyu", "r": "ar", "s": "es", "t": "ti", "u": "yu", "v": "vi", "w": "dobolyu",
           "x": "eks", "y": "way", "z": "zi"}
ACRONYM_WORDS = frozenset(("asean", "nato", "opec", "covid", "pin", "ram", "rom", "pagasa",
                           "unesco", "unicef"))
ABBREVIATIONS = {
    "atbp.": "at iba pa", "Gng.": "ginang", "Bb.": "binibini", "Dr.": "doktor", "Dra.": "doktora",
    "Sto.": "santo", "Sta.": "santa", "Brgy.": "barangay", "Bgy.": "barangay", "Hen.": "heneral",
    "Kgg.": "kagalang galang", "Blg.": "bilang", "blg.": "bilang", "Pres.": "presidente",
    "Sen.": "senador", "Gob.": "gobernador", "Kap.": "kapitan", "Engr.": "inhinyero",
    "Atty.": "abogado", "Jr.": "dyunyor", "Sr.": "senyor", "Mt.": "bundok", "St.": "santo",
    "Hwy.": "haywey", "pp.": "pahina",
}
UNITS = {"km/h": "kilometro bawat oras", "km/hr": "kilometro bawat oras", "kph": "kilometro bawat oras",
         "km": "kilometro", "m": "metro", "cm": "sentimetro", "mm": "milimetro", "kg": "kilo",
         "g": "gramo", "mg": "miligramo", "l": "litro", "L": "litro", "ml": "mililitro",
         "mL": "mililitro", "GB": "gigabayt", "MB": "megabayt", "TB": "terabayt",
         "kWh": "kilowat oras", "kW": "kilowat", "W": "wat", "V": "bolt", "mAh": "miliamper oras",
         "GHz": "gigaherts", "MHz": "megaherts", "ha": "ektarya", "°C": "digri selsiyus",
         "℃": "digri selsiyus", "°": "digri"}
CURRENCY = {"₱": "piso", "PHP": "piso", "Php": "piso", "US$": "dolyar", "$": "dolyar", "€": "euro",
            "£": "pound", "¥": "yen"}
SYMBOLS = {"&": " at ", "+": " plus ", "=": " katumbas ng ", "@": " at ", "#": " numero ",
           "×": " beses ", "/": " bawat ", "%": " porsiyento "}

_A = r"(?<![\w.,])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
# Full month names, or abbreviations with their dot (May, Set are also words).
_MONTH_KEYS = "|".join([m for m in MONTHS if m] + [a + r"\." for a in sorted(MONTH_ABBR, key=len, reverse=True)])
DATE_MDY = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
DATE_MONTH_DAY = re.compile(r"(?<![\w])(" + _MONTH_KEYS + r")\s+(\d{1,2})(?:,?\s+(\d{4}))?(?![\d])",
                            re.IGNORECASE)
DATE_DAY_MONTH = re.compile(r"(?<![\w.,])(\d{1,2})\s+(" + _MONTH_KEYS + r")(?:,?\s+(\d{4}))?(?![\w])",
                            re.IGNORECASE)
TIME = re.compile(r"(?:(?<![\w])(?:alas|ala)[\s-]+)?(?<![\d:.])([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?(?![\d:])"
                  r"(\s+(?:ng\s+(?:umaga|tanghali|hapon|gabi|madaling\s+araw|hatinggabi)|[ap]\.?m\.?(?![\w])))?",
                  re.IGNORECASE)
PHONE = re.compile(r"(?<![\d])(?:\+\d{1,3}[\s-])?\d{2,4}(?:[\s-]\d{2,4}){2,4}(?![\d])"
                   r"|(?<![\d.,])0\d{2,}(?![\d]|[.,]\d)")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")(\s?(?:libo|milyon|bilyon|trilyon))?")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(r"(?<![\w])([Ii]ka)-?(\d+)(?![\d])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])")
# A number before a noun takes the linker (dalawampu't isang tao); not before these words.
NO_LINKER = frozenset(("na", "ng", "nang", "at", "ay", "sa", "ang", "o", "hanggang", "mula", "pa",
                       "lang", "lamang", "din", "rin", "ba", "ka", "ko", "mo", "po", "ho", "noon",
                       "kay", "ni", "si", "nina", "sina", "para", "kung", "dahil", "pero", "naman",
                       "nga", "pala", "daw", "raw", "ito", "iyon", "iyan", "mga"))
NEXT_WORD = re.compile(r"\s+([a-zñ']+)")
REDUPLICATION = re.compile(r"(?<![\w'])([^\W\d_]+)-\1(?![\w'])", re.IGNORECASE)  # araw-araw: two words
GLOTTAL_HYPHEN = re.compile(r"(?<=[b-df-hj-np-tv-zñ])-(?=[aeiouáéíóúàèìòùâêîôû])", re.IGNORECASE)


def _below_1000(n: int) -> str:
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts.append(f"{linked(ONES[h])} {'raan' if ONES[h][-1] not in 'aeiou' else 'daan'}")
    if r:
        parts.append(_below_100(r))
    return " at ".join(parts)


def _below_100(n: int) -> str:
    if n < 10:
        return ONES[n]
    if n < 20:
        return TEENS[n - 10]
    t, u = divmod(n, 10)
    return TENS[t] + (f"'t {ONES[u]}" if u else "")


def linked(words: str) -> str:
    """The number words with the linker before a noun: isa -> isang, apat -> apat na, milyon ->
    milyong, dalawampu't isa -> dalawampu't isang."""
    if words.endswith(("a", "e", "i", "o", "u")):
        return words + "ng"
    if words.endswith("n"):
        return words + "g"
    return words + " na"


def cardinal(n: int) -> str:
    """Native Tagalog cardinal: 11 -> labing isa, 21 -> dalawampu't isa, 100 -> isang daan,
    400 -> apat na raan, 1250 -> isang libo at dalawang daan at limampu."""
    if n < 0:
        return "minus " + cardinal(-n)
    if n == 0:
        return "sero"
    if n >= 10 ** 15:
        return " ".join(ONES[int(c)] for c in str(n))
    parts = []
    for scale, name in SCALES:
        q, n = divmod(n, scale)
        if q:
            parts.append(f"{linked(cardinal(q))} {name}")
    if n:
        parts.append(_below_1000(n))
    return " at ".join(parts)


def spanish(n: int) -> str:
    """Spanish-derived numbers 1-999 in Filipino spelling (prices, clock minutes)."""
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts.append("siyen" if h == 1 and not r else ES_HUNDREDS[h])
    if r and r < 20:
        parts.append(ES_ONES[r])
    elif r:
        t, u = divmod(r, 10)
        tens = ES_TENS[t]
        parts.append(tens if not u else f"{tens} {ES_ONES[u]}" if t == 2 else f"{tens}'y {ES_ONES[u]}")
    return " ".join(parts)


def ordinal(n: int) -> str:
    """1 -> una, 2 -> ikalawa, 3 -> ikatlo, 4 -> ikaapat, 21 -> ikadalawampu't isa."""
    return {1: "una", 2: "ikalawa", 3: "ikatlo"}.get(n) or "ika" + cardinal(n)


def parse_number(s: str) -> tuple[int, str | None]:
    """(integer part, decimals) with Philippine marks: comma for thousands, point for decimals."""
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
    if frac:  # digits only: 1.234,5 splits at the first mark (frac "234,5")
        out += " punto " + " ".join(ONES[int(c)] for c in frac if c.isdigit())
    return ("minus " if neg else "") + out


def _date(m: int, d: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{ordinal(d)} ng {MONTHS[m]}"
    if y is not None:
        out += f" , {cardinal(int(y) + (2000 if len(y) == 2 else 0))}"
    return f" {out} "


def _month(name: str) -> int:
    """Month number of a name the date patterns matched (re.IGNORECASE: also ſ, ı, İ, K)."""
    key = name.rstrip(".")
    names = [(m, k) for k, m in enumerate(MONTHS) if m] + list(MONTH_ABBR.items())
    return next(k for m, k in names if re.fullmatch(m, key, re.IGNORECASE))


def _time(m: re.Match) -> str:
    h, mi, part = int(m.group(1)), int(m.group(2)), m.group(3)
    h12 = h % 12 or 12
    out = "ala una" if h12 == 1 else f"alas {ES_ONES[h12]}"
    if mi == 30:
        out += " i medya"
    elif mi:
        out += f" i {spanish(mi)}"
    if part:
        p = part.strip().lower().replace(".", "")
        out += {"am": " ng umaga", "pm": " ng hapon" if h12 < 6 or h12 == 12 else " ng gabi"}.get(p, " " + p)
    elif h == 0:
        out += " ng hatinggabi"
    elif 13 <= h <= 17:
        out += " ng hapon"
    elif h >= 18:
        out += " ng gabi"
    return f" {out} "


def _money(m: re.Match) -> str:
    cur, num, scale = m.group(1), m.group(2), m.group(3)
    name = CURRENCY[cur]
    if scale:
        return f" {number(num)} {scale.strip()} {name} "
    n, frac = parse_number(num)
    cents = int(frac[:2].ljust(2, "0")) if frac else 0
    if name == "piso" and not cents and 2 <= n <= 999:
        return f" {spanish(n)} pesos "
    out = f"{linked(cardinal(n))} {name}" if n or not cents else ""
    if cents and name == "piso":
        out += (" at " if out else "") + f"{linked(cardinal(cents))} sentimo"
    elif cents:
        out = f"{number(num)} {name}"
    return f" {out} "


def _number_before_word(m: re.Match) -> str:
    """A number; a whole number before a lower-case word (a noun) takes the linker."""
    words = number(m.group(1) + m.group(2))
    nxt = NEXT_WORD.match(m.string, m.end())
    if nxt and nxt.group(1) not in NO_LINKER and parse_number(m.group(2))[1] is None:
        words = linked(words)
    return f" {words} "


def _ordinal_before_word(m: re.Match) -> str:
    """ika-3 -> ikatlo; before a noun with the linker (ika-3 puwesto -> ikatlong puwesto)."""
    words = ordinal(int(m.group(2)))
    nxt = NEXT_WORD.match(m.string, m.end())
    return f" {linked(words) if nxt and nxt.group(1) not in NO_LINKER else words} "


def normalize_tl(text: str) -> str:
    t = apply_abbreviations(text, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(2)), int(m.group(3)), m.group(1)) or m.group(0), t)
    t = DATE_MDY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3))
                     or _date(int(m.group(2)), int(m.group(1)), m.group(3)) or m.group(0), t)
    t = DATE_MONTH_DAY.sub(lambda m: _date(_month(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = DATE_DAY_MONTH.sub(lambda m: _date(_month(m.group(2)), int(m.group(1)), m.group(3)) or m.group(0), t)
    t = TIME.sub(_time, t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), ONES, "plus"), t)
    t = MONEY_BEFORE.sub(_money, t)
    t = PERCENT.sub(lambda m: f" {linked(number(m.group(1) + m.group(2)))} porsiyento ", t)
    t = UNIT.sub(lambda m: f" {linked(number(m.group(1) + m.group(2)))} {UNITS[m.group(3)]} ", t)
    t = ORDINAL.sub(_ordinal_before_word, t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} hanggang {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, ONES)} ", t)
    t = NUMBER.sub(_number_before_word, t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = REDUPLICATION.sub(r"\1 \1", t)
    t = GLOTTAL_HYPHEN.sub("'", t)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    return finish(t)
