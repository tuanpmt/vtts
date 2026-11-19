"""Polish text normalization for one Polish run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces (Polish letters kept).

Rules, in order: abbreviations (np., tj., itd., ul., r. ...), quotes and brackets dropped, dates
(15.03.2026, 2026-03-15: piętnasty marca dwa tysiące dwudziestego szóstego roku), years before
rok/roku/r. (ordinal in that case: w 2026 roku -> w dwa tysiące dwudziestym szóstym roku),
centuries in Roman numerals (XX wiek, w XX wieku), times (14:30 -> czternasta trzydzieści, o 14:30 -> o czternastej trzydzieści),
phone numbers (digit by digit), numbers with tys./mln/mld, money (100 zł, 10,50 zł -> dziesięć
złotych pięćdziesiąt groszy, $5, 20 €), percentages, units after a number (5 km, 128 GB, 25 °C),
ordinals written 1. before a month name, ranges (10-20 -> od dziesięciu do dwudziestu), pause
marks, product codes (ESP32: letters by Polish name, digits one by one), numbers (decimal comma:
trzy przecinek pięć), symbols, acronyms (PKP -> pe ka pe; a few read as words: NATO, ZUS), and
the one-letter prepositions w z joined to the next word with a hyphen (w domu -> w-domu) so the
voicing rules see them together.

Agreement: 1 takes the gender of the noun after it where it is cheap (jedna książka, jedno
okno: a following word ending in a / o e ę um; dwa / dwie is not guessed, the plural endings of
masculine and feminine nouns are the same), units and currencies have
their gender and noun forms by the number (1 złoty, 2 złote, 5 złotych; 12-14 take the many
form); a whole number after od, do, około, ponad, powyżej, poniżej, z is genitive (do
trzydziestu stopni). Other cases are read nominative.
"""

from __future__ import annotations

import re

from ..latin_norm import DROP, NUM, PAUSE, PRODUCT_CODE, digits, finish, parse_number, spell

ONES = ("zero", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć",
        "dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście",
        "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście")
TENS = ("", "", "dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt", "sześćdziesiąt",
        "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt")
HUNDREDS = ("", "sto", "dwieście", "trzysta", "czterysta", "pięćset", "sześćset", "siedemset",
            "osiemset", "dziewięćset")
ONES_GEN = ("zera", "jednego", "dwóch", "trzech", "czterech", "pięciu", "sześciu", "siedmiu",
            "ośmiu", "dziewięciu", "dziesięciu", "jedenastu", "dwunastu", "trzynastu",
            "czternastu", "piętnastu", "szesnastu", "siedemnastu", "osiemnastu", "dziewiętnastu")
TENS_GEN = ("", "", "dwudziestu", "trzydziestu", "czterdziestu", "pięćdziesięciu", "sześćdziesięciu",
            "siedemdziesięciu", "osiemdziesięciu", "dziewięćdziesięciu")
HUNDREDS_GEN = ("", "stu", "dwustu", "trzystu", "czterystu", "pięciuset", "sześciuset",
                "siedmiuset", "ośmiuset", "dziewięciuset")
# (value, one, few, many)
SCALES = ((10 ** 12, "bilion", "biliony", "bilionów"), (10 ** 9, "miliard", "miliardy", "miliardów"),
          (10 ** 6, "milion", "miliony", "milionów"), (1000, "tysiąc", "tysiące", "tysięcy"))
SCALES_GEN = {1000: ("tysiąca", "tysięcy"), 10 ** 6: ("miliona", "milionów"),
              10 ** 9: ("miliarda", "miliardów"), 10 ** 12: ("biliona", "bilionów")}
DIGITS = ONES[:10]

# Ordinal stems and declension class (h: -y, k: -i after k/g, c: trzeci).
ORD_ONES = (("", ""), ("pierwsz", "h"), ("drug", "k"), ("trzec", "c"), ("czwart", "h"),
            ("piąt", "h"), ("szóst", "h"), ("siódm", "h"), ("ósm", "h"), ("dziewiąt", "h"),
            ("dziesiąt", "h"), ("jedenast", "h"), ("dwunast", "h"), ("trzynast", "h"),
            ("czternast", "h"), ("piętnast", "h"), ("szesnast", "h"), ("siedemnast", "h"),
            ("osiemnast", "h"), ("dziewiętnast", "h"))
ORD_TENS = ("", "", "dwudziest", "trzydziest", "czterdziest", "pięćdziesiąt", "sześćdziesiąt",
            "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt")
ORD_HUNDREDS = ("", "setn", "dwusetn", "trzechsetn", "czterechsetn", "pięćsetn", "sześćsetn",
                "siedemsetn", "osiemsetn", "dziewięćsetn")
CASES = ("nom_m", "nom_f", "nom_n", "gen_m", "dat_m", "loc_m", "gen_f", "acc_f", "nom_pl",
         "gen_pl")
ENDINGS = {
    "h": ("y", "a", "e", "ego", "emu", "ym", "ej", "ą", "e", "ych"),
    "k": ("i", "a", "ie", "iego", "iemu", "im", "iej", "ą", "ie", "ich"),
    "c": ("i", "ia", "ie", "iego", "iemu", "im", "iej", "ią", "ie", "ich"),
}
MONTHS = ("", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
          "września", "października", "listopada", "grudnia")
YEAR_NOUN = {"rok": "nom_m", "roku": "gen_m", "rokiem": "loc_m", "r.": "gen_m"}
CENTURY_NOUN = {"wiek": "nom_m", "wieku": "gen_m", "wiekiem": "loc_m", "w.": "nom_m",
                "wieki": "nom_pl", "wieków": "gen_pl"}
# Hours after these words take the -ej form (o czternastej, do siódmej, od dziewiątej).
TIME_OBLIQUE = frozenset(("o", "po", "od", "do", "około", "koło", "przy"))
LOC_PREPOSITIONS = frozenset(("w", "we", "o", "po", "przy"))
GEN_COUNT = frozenset(("od", "do", "około", "ponad", "powyżej", "poniżej", "z", "ze", "dla",
                       "bez", "spośród", "wśród", "u", "koło", "blisko", "niż"))

LETTERS = {"a": "a", "ą": "ą", "b": "be", "c": "ce", "ć": "cie", "d": "de", "e": "e", "ę": "ę",
           "f": "ef", "g": "gie", "h": "ha", "i": "i", "j": "jot", "k": "ka", "l": "el", "ł": "eł",
           "m": "em", "n": "en", "ń": "eń", "o": "o", "ó": "o kreskowane", "p": "pe", "q": "ku",
           "r": "er", "s": "es", "ś": "eś", "t": "te", "u": "u", "v": "fał", "w": "wu", "x": "iks",
           "y": "igrek", "z": "zet", "ź": "ziet", "ż": "żet"}
ACRONYM_WORDS = frozenset(("nato", "zus", "pis", "pesel", "nik", "pzpn", "uefa", "fifa", "nasa",
                           "unesco", "onz", "pck", "lot", "pkp", "pko", "regon", "nip"))
SPELLED = frozenset(("pzpn", "pck", "pkp", "pko", "nip"))
ABBREVIATIONS = {
    "np.": "na przykład", "tj.": "to jest", "tzn.": "to znaczy", "itd.": "i tak dalej",
    "itp.": "i tym podobne", "ok.": "około", "tzw.": "tak zwany", "ul.": "ulica", "al.": "aleja",
    "pl.": "plac", "dr": "doktor", "prof.": "profesor", "mgr": "magister", "inż.": "inżynier",
    "św.": "święty", "nr": "numer", "wg": "według", "m.in.": "między innymi",
    "ds.": "do spraw", "br.": "bieżącego roku", "ang.": "angielski", "łac.": "łaciński",
    "godz.": "godzina", "pt.": "pod tytułem", "woj.": "województwo", "pow.": "powiat",
    "gm.": "gmina", "ur.": "urodzony", "zm.": "zmarły", "p.n.e.": "przed naszą erą",
    "n.e.": "naszej ery",
}
# (gender, one, few, many)
UNITS = {
    "km/h": ("m", "kilometr na godzinę", "kilometry na godzinę", "kilometrów na godzinę"),
    "km": ("m", "kilometr", "kilometry", "kilometrów"), "m": ("m", "metr", "metry", "metrów"),
    "cm": ("m", "centymetr", "centymetry", "centymetrów"),
    "mm": ("m", "milimetr", "milimetry", "milimetrów"),
    "kg": ("m", "kilogram", "kilogramy", "kilogramów"), "g": ("m", "gram", "gramy", "gramów"),
    "mg": ("m", "miligram", "miligramy", "miligramów"), "t": ("f", "tona", "tony", "ton"),
    "l": ("m", "litr", "litry", "litrów"), "L": ("m", "litr", "litry", "litrów"),
    "ml": ("m", "mililitr", "mililitry", "mililitrów"), "ha": ("m", "hektar", "hektary", "hektarów"),
    "h": ("f", "godzina", "godziny", "godzin"), "min": ("f", "minuta", "minuty", "minut"),
    "s": ("f", "sekunda", "sekundy", "sekund"),
    "KB": ("m", "kilobajt", "kilobajty", "kilobajtów"), "MB": ("m", "megabajt", "megabajty", "megabajtów"),
    "GB": ("m", "gigabajt", "gigabajty", "gigabajtów"), "TB": ("m", "terabajt", "terabajty", "terabajtów"),
    "Mb/s": ("m", "megabit na sekundę", "megabity na sekundę", "megabitów na sekundę"),
    "kWh": ("f", "kilowatogodzina", "kilowatogodziny", "kilowatogodzin"),
    "kW": ("m", "kilowat", "kilowaty", "kilowatów"), "W": ("m", "wat", "waty", "watów"),
    "V": ("m", "wolt", "wolty", "woltów"), "mAh": ("f", "miliamperogodzina", "miliamperogodziny",
                                                    "miliamperogodzin"),
    "GHz": ("m", "gigaherc", "gigaherce", "gigaherców"), "MHz": ("m", "megaherc", "megaherce", "megaherców"),
    "Hz": ("m", "herc", "herce", "herców"),
    "°C": ("m", "stopień Celsjusza", "stopnie Celsjusza", "stopni Celsjusza"),
    "℃": ("m", "stopień Celsjusza", "stopnie Celsjusza", "stopni Celsjusza"),
    "°": ("m", "stopień", "stopnie", "stopni"),
}
CURRENCY = {
    "zł": ("m", "złoty", "złote", "złotych"), "PLN": ("m", "złoty", "złote", "złotych"),
    "gr": ("m", "grosz", "grosze", "groszy"),
    "$": ("m", "dolar", "dolary", "dolarów"), "USD": ("m", "dolar", "dolary", "dolarów"),
    "€": ("n", "euro", "euro", "euro"), "EUR": ("n", "euro", "euro", "euro"),
    "£": ("m", "funt", "funty", "funtów"),
}
# Genitive singular of the unit nouns (after a decimal: 2,5 kilograma; after do 1: jednego metra).
GEN_SG = {"kilometr": "kilometra", "metr": "metra", "centymetr": "centymetra",
          "milimetr": "milimetra", "kilogram": "kilograma", "gram": "grama", "miligram": "miligrama",
          "tona": "tony", "litr": "litra", "mililitr": "mililitra", "hektar": "hektara",
          "godzina": "godziny", "minuta": "minuty", "sekunda": "sekundy", "kilobajt": "kilobajta",
          "megabajt": "megabajta", "gigabajt": "gigabajta", "terabajt": "terabajta",
          "megabit na sekundę": "megabita na sekundę", "kilowatogodzina": "kilowatogodziny",
          "kilowat": "kilowata", "wat": "wata", "wolt": "wolta",
          "miliamperogodzina": "miliamperogodziny", "gigaherc": "gigaherca",
          "megaherc": "megaherca", "herc": "herca", "stopień Celsjusza": "stopnia Celsjusza",
          "stopień": "stopnia", "złoty": "złotego", "grosz": "grosza", "dolar": "dolara",
          "euro": "euro", "funt": "funta", "cent": "centa",
          "kilometr na godzinę": "kilometra na godzinę", "tysiąc": "tysiąca", "milion": "miliona",
          "miliard": "miliarda", "bilion": "biliona"}
SUBUNIT = {"złoty": ("m", "grosz", "grosze", "groszy"), "dolar": ("m", "cent", "centy", "centów"),
           "euro": ("m", "cent", "centy", "centów")}
SCALE_ABBR = {"tys.": 1000, "tys": 1000, "mln": 10 ** 6, "mld": 10 ** 9, "bln": 10 ** 12}
SYMBOLS = {"&": " i ", "+": " plus ", "=": " równa się ", "@": " małpa ", "×": " razy ",
           "#": " numer ", "%": " procent ", "/": " ", "§": " paragraf "}
FRACTION = (("", "", ""), ("dziesiąta", "dziesiąte", "dziesiątych"), ("setna", "setne", "setnych"),
            ("tysięczna", "tysięczne", "tysięcznych"))

_A = r"(?<![\w.,])"
_Z = r"(?![\w])"
_PL = "a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
_SCALE_KEYS = "|".join(re.escape(s) for s in sorted(SCALE_ABBR, key=len, reverse=True))
_NUMS = r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:,\d+)?|" + NUM
DATE_DMY = re.compile(r"(?<![\d.])(\d{1,2})([./])(\d{1,2})\2(\d{4})(?![\d])(\s*(?:r\.|roku))?")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
DAY_MONTH = re.compile(r"(?<![\d,.])(\d{1,2})\.?\s+(" + "|".join(MONTHS[1:]) + r")" + _Z)
YEAR = re.compile(r"(?<![\d,.])(\d{3,4})\s*(r\.|" + "|".join(YEAR_NOUN) + r")(?![\w])")
ROMAN = r"[IVXLC]+"
CENTURY = re.compile(r"(?<![\w])(" + ROMAN + r")\s+(" +
                     "|".join(re.escape(k) for k in sorted(CENTURY_NOUN, key=len, reverse=True)) +
                     r")(?![\w])")
TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?(?![\d:])")
PHONE = re.compile(r"(?<![\d\w])(?:\+\d{1,3}[\s-]*)?\d{3}[\s-]\d{3}[\s-]\d{3}(?![\d])"
                   r"|(?<![\d\w])\+\d{1,3}[\s-]*\d{2}[\s-]\d{3}[\s-]\d{2}[\s-]\d{2}(?![\d])")
SCALED = re.compile(_A + r"(" + _NUMS + r")\s*(" + _SCALE_KEYS + r")(?:\s*(" + _CUR_KEYS + r"))?(?![\w])")
MONEY_BEFORE = re.compile(r"(?<![\w])(\$|€|£)\s?(" + _NUMS + r")(?![\d])")
MONEY_AFTER = re.compile(_A + r"(" + _NUMS + r")\s?(" + _CUR_KEYS + r")(?![\w])")
PERCENT = re.compile(_A + r"(-?)(" + _NUMS + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + _NUMS + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
RANGE = re.compile(_A + r"(\d+)\s?[-–—]\s?(\d+)" + _Z)
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + _NUMS + r")(?![\d])(?=(\s+[" + _PL + r"]+)?)")
ACRONYM = re.compile(r"(?<![\w])[A-ZĄĆĘŁŃÓŚŹŻ]{2,5}(?![\w])")
CLITICS = frozenset(("w", "z"))


def prev_word(m: re.Match) -> str | None:
    """The whitespace-separated chunk right before a match (in the pass's input), or None when no
    whitespace or nothing precedes it: do in "do 30 °C". It is looked at, not replaced."""
    s, k = m.string, m.start()
    j = k
    while j > 0 and s[j - 1].isspace():
        j -= 1
    if j == k or j == 0:
        return None
    i = j
    while i > 0 and not s[i - 1].isspace():
        i -= 1
    return s[i:j]
MARKS = ",.?!;:"


def plural(n: int, forms: tuple[str, str, str]) -> str:
    """forms (one, few, many): 1 -> one, 2-4 22-24 (not 12-14) -> few, else many (5, 11, 21)."""
    if n == 1:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def _below_1000(n: int, gender: str = "m", final: bool = True) -> list[str]:
    h, r = divmod(n, 100)
    out = [HUNDREDS[h]] if h else []
    if r >= 20:
        t, r = divmod(r, 10)
        out.append(TENS[t])
    if r:
        word = ONES[r]
        if final and r == 1 and n == 1 and gender != "m":
            word = "jedna" if gender == "f" else "jedno"
        elif final and r == 2 and gender == "f":
            word = "dwie"
        out.append(word)
    return out


def cardinal(n: int, gender: str = "m") -> str:
    """Polish cardinal in the nominative; gender (m, f, n) of the counted noun for 1 (jeden /
    jedna / jedno) and 2 (dwa / dwie): 2026 -> dwa tysiące dwadzieścia sześć."""
    if n < 0:
        return "minus " + cardinal(-n, gender)
    if n == 0:
        return "zero"
    if n >= 10 ** 15:
        return digits(str(n), DIGITS)
    out: list[str] = []
    for value, *forms in SCALES:
        q, n = divmod(n, value)
        if q:
            if q > 1:
                out += cardinal(q).split()
            out.append(plural(q, tuple(forms)))
    out += _below_1000(n, gender)
    return " ".join(out)


def cardinal_gen(n: int) -> str:
    """Genitive cardinal (od dziesięciu do dwudziestu, dwóch tysięcy)."""
    if n >= 10 ** 15:
        return digits(str(n), DIGITS)
    if n == 0:
        return "zera"
    out: list[str] = []
    for value, *_forms in SCALES:
        q, n = divmod(n, value)
        if q:
            if q > 1:
                out.append(cardinal_gen(q))
            one, many = SCALES_GEN[value]
            out.append(one if q == 1 else many)
    h, r = divmod(n, 100)
    if h:
        out.append(HUNDREDS_GEN[h])
    if r >= 20:
        t, r = divmod(r, 10)
        out.append(TENS_GEN[t])
    if r:
        out.append(ONES_GEN[r])
    return " ".join(out)


def _ord_word(stem: str, cls: str, case: str) -> str:
    return stem + ENDINGS[cls][CASES.index(case)]


def ordinal(n: int, case: str = "nom_m") -> str:
    """Ordinal adjective; the tens and units are ordinals, larger parts cardinals: 1 -> pierwszy,
    2026 (gen_m) -> dwa tysiące dwudziestego szóstego, 1990 -> tysiąc dziewięćset
    dziewięćdziesiąty, 300 -> trzechsetny, 2000 -> dwutysięczny."""
    if n <= 0 or n >= 10 ** 9:
        return cardinal(n)
    r100 = n % 100
    if r100:
        head = cardinal(n - r100) if n >= 100 else ""
        if r100 < 20:
            words = [_ord_word(*ORD_ONES[r100], case)]
        else:
            t, u = divmod(r100, 10)
            words = [_ord_word(ORD_TENS[t], "h", case)]
            if u:
                words.append(_ord_word(*ORD_ONES[u], case))
        return " ".join(([head] if head else []) + words)
    if n % 1000:
        head = cardinal(n - n % 1000) if n >= 1000 else ""
        word = _ord_word(ORD_HUNDREDS[(n % 1000) // 100], "h", case)
        return f"{head} {word}".strip()
    q = n // 1000
    prefix = {1: "", 2: "dwu", 3: "trzy", 4: "cztero", 5: "pięcio", 10: "dziesięcio"}.get(q)
    if prefix is None:
        return cardinal(n)
    return _ord_word(prefix + "tysięczn", "h", case)


def number(s: str, gender: str = "m") -> str:
    """A written number: decimal comma or point (3,5 -> trzy i pięć dziesiątych, 1,25 -> jeden i
    dwadzieścia pięć setnych; more than three decimals: przecinek and the digits)."""
    s = re.sub(r"[ \u00a0\u202f]", "", s)
    neg = s.startswith("-")
    n, frac, _ = parse_number(s.lstrip("-"))
    if frac is None:
        out = cardinal(n, gender)
    elif len(frac) <= 3:
        k = int(frac)
        out = f"{cardinal(n)} i {cardinal(k, 'f')} {plural(k, FRACTION[len(frac)])}"
    else:
        out = cardinal(n) + " przecinek " + digits(frac, DIGITS)
    return ("minus " if neg else "") + out


def count(s: str, unit: tuple[str, str, str, str]) -> str:
    """A number and the unit noun in the form the number takes (1 złoty, 2 złote, 5 złotych;
    a decimal takes the genitive singular: 2,5 kilograma)."""
    gender, *forms = unit
    clean = re.sub(r"[ \u00a0\u202f]", "", s)
    n, frac, _ = parse_number(clean.lstrip("-"))
    noun = GEN_SG[forms[0]] if frac is not None else plural(n, tuple(forms))
    return f"{number(clean, gender)} {noun}"


def _gender_of(word: str) -> str:
    w = word.strip().lower()
    if w.endswith("a"):
        return "f"
    if w.endswith(("o", "e", "ę", "um")):
        return "n"
    return "m"


def _gen_count(prev: str | None, num: str) -> bool:
    return (prev or "").lower() in GEN_COUNT and parse_number(re.sub(r"\s", "", num))[1] is None


def _number(m: re.Match) -> str:
    sign, num, noun = m.groups()
    prev = prev_word(m)
    n, frac, _ = parse_number(re.sub(r"[ \u00a0\u202f]", "", num))
    if not sign and _gen_count(prev, num):
        return f" {cardinal_gen(n)} "
    gender = "m"
    if noun and frac is None:
        w = noun.strip().lower()
        if n == 1:
            gender = _gender_of(w)
    return f" {number(sign + num, gender)} "


def _date(d: int, m: int, y: str | None, prev_case: str = "nom_m") -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{ordinal(d, prev_case)} {MONTHS[m]}"
    if y is not None:
        out += f" {ordinal(int(y), 'gen_m')} roku"
    return f" {out} "


def _year(m: re.Match) -> str:
    y, noun = m.groups()
    p = (prev_word(m) or "").lower()
    end = " ." if noun.endswith(".") and not m.string[m.end():].strip() else ""
    if p in LOC_PREPOSITIONS:
        return f" {ordinal(int(y), 'loc_m')} roku{end} "
    if p in GEN_COUNT:
        return f" {ordinal(int(y), 'gen_m')} roku{end} "
    if noun == "r.":
        return f" {ordinal(int(y), 'gen_m')} roku{end} "
    return f" {ordinal(int(y), YEAR_NOUN[noun])} {noun} "


ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman(s: str) -> int:
    total = 0
    for a, b in zip(s, s[1:] + " "):
        v = ROMAN_VALUES[a]
        total += -v if b != " " and ROMAN_VALUES[b] > v else v
    return total


def _century(m: re.Match) -> str:
    r, noun = m.groups()
    prev = prev_word(m)
    case = CENTURY_NOUN[noun]
    if (prev or "").lower() in LOC_PREPOSITIONS and noun == "wieku":
        case = "loc_m"
    word = "wiek" if noun == "w." else noun
    return f" {ordinal(roman(r), case)} {word} "


def _time(m: re.Match) -> str:
    """14:30 -> czternasta trzydzieści, 9:05 -> dziewiąta zero pięć, 7:00 -> siódma."""
    prev, h, mi, sec = prev_word(m), int(m.group(1)), int(m.group(2)), m.group(3)
    case = "gen_f" if (prev or "").lower() in TIME_OBLIQUE else "nom_f"
    out = ordinal(h, case) if h else "zero"
    if mi:
        out += " " + (cardinal(mi) if mi >= 10 else "zero " + cardinal(mi))
    if sec and int(sec):
        out += f" i {cardinal(int(sec), 'f')} {plural(int(sec), ('sekunda', 'sekundy', 'sekund'))}"
    return f" {out} "


def _scaled(m: re.Match) -> str:
    num, key, cur = m.groups()
    value = SCALE_ABBR[key]
    forms = next(("m", one, few, many) for v, one, few, many in SCALES if v == value)
    out = count(num, forms)
    if cur:
        out += " " + CURRENCY[cur][3]
    return f" {out} "


def _money(num: str, cur: str) -> str:
    unit = CURRENCY[cur]
    clean = re.sub(r"[ \u00a0\u202f]", "", num)
    n, frac, _ = parse_number(clean)
    if frac is not None and len(frac) == 2 and unit[1] in SUBUNIT:
        out = count(str(n), unit)
        if int(frac):
            out += " " + count(str(int(frac)), SUBUNIT[unit[1]])
        return f" {out} "
    return f" {count(num, unit)} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    prev = prev_word(m)
    if not sign and _gen_count(prev, num):
        n = parse_number(re.sub(r"\s", "", num))[0]
        forms = UNITS[unit]
        return f" {cardinal_gen(n)} {GEN_SG[forms[1]] if n == 1 else forms[3]} "
    return f" {'minus ' if sign else ''}{count(num, UNITS[unit])} "


def _acronym(m: re.Match) -> str:
    w = m.group(0)
    low = w.lower()
    if low in ACRONYM_WORDS and low not in SPELLED:
        return low
    return " " + " ".join(LETTERS[c] for c in low if c in LETTERS) + " "


def _abbreviations(t: str) -> str:
    """Keys as written and with a capital first letter (Np. at the start of a sentence)."""
    table = {**{k[0].upper() + k[1:]: v for k, v in ABBREVIATIONS.items()}, **ABBREVIATIONS}
    for key in sorted(table, key=len, reverse=True):
        end = key.endswith(".")

        def sub(m: re.Match, key=key, end=end) -> str:
            last = end and not m.string[m.end():].strip()
            return f" {table[key]} {'.' if last else ''}"

        t = re.sub(r"(?<![\w])" + re.escape(key) + ("" if end else r"(?![\w])"), sub, t)
    return t


def _join_clitics(text: str) -> str:
    words = text.split()
    out: list[str] = []
    k = 0
    while k < len(words):
        w = words[k]
        if w in CLITICS and k + 1 < len(words) and words[k + 1] not in MARKS:
            out.append(f"{w}-{words[k + 1]}")
            k += 2
            continue
        out.append(w)
        k += 1
    return " ".join(out)


def normalize_pl(text: str) -> str:
    t = PHONE.sub(lambda m: f" {'plus ' if m.group(0).startswith('+') else ''}{digits(m.group(0), DIGITS)} ", text)
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(3)), m.group(4)) or m.group(0), t)
    t = YEAR.sub(_year, t)
    t = CENTURY.sub(_century, t)
    t = _abbreviations(t)
    t = t.translate({ord(c): " " for c in DROP})
    t = DAY_MONTH.sub(lambda m: f" {ordinal(int(m.group(1)), 'nom_m')} {m.group(2)} "
                      if 1 <= int(m.group(1)) <= 31 else m.group(0), t)
    t = TIME.sub(_time, t)
    t = SCALED.sub(_scaled, t)
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(2)), t)
    t = PERCENT.sub(lambda m: f" {'minus ' if m.group(1) else ''}{number(m.group(2))} procent ", t)
    t = UNIT.sub(_unit, t)
    t = RANGE.sub(lambda m: f" od {cardinal_gen(int(m.group(1)))} do {cardinal_gen(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, DIGITS)} ", t)
    t = NUMBER.sub(_number, t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = ACRONYM.sub(_acronym, t)
    return _join_clitics(finish(t))
