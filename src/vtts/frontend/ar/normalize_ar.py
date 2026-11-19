"""Arabic text normalization for one Arabic run (Modern Standard Arabic).

Output follows the other modules' convention: words and the punctuation tokens , . ? ! ; :
separated by single spaces. Arabic words are kept as written (NFC, without tatweel); the words
this module writes (numbers, months, units ...) carry their vowels so that g2p_ar reads them
exactly. Latin parts go through the English normalizer (lower case) and are read in English.

Rules, in order: Arabic-Indic digits ٠-٩ and Eastern (Persian) digits ۰-۹ -> 0-9, the Arabic
decimal and thousands separators ٫ ٬ and percent sign ٪, punctuation ، ؛ ؟ ۔ -> , ; ? .,
abbreviations (د. -> دكتور, إلخ, ق.م, ص.ب), quotes and brackets dropped, dates (15/08/2024,
2024-08-15: day, month name, year), times (10:30 -> عشرة ونصف; a following ص / م is read
صباحا / مساء), years of 3-4 digits with هـ / م (1445 هـ -> هجري), phone numbers (10+ digits or +CC: digit by
digit), money ($100, 100 $, 50 ر.س, € £: the currency after the number in the form the count
takes), percentages, units after a number (5 km, 5 كم, 128GB, 30°C), ranges (10-20 -> من عشرة
إلى عشرين, in the genitive; a من before the range is kept once), pause marks, product codes (ESP32: Latin letters by their Arabic names, digits one
by one), numbers, symbols, hyphens.

Numbers are read in the masculine (the default when the counted noun is not known) and without
case endings, as in pausal reading: 21 = واحد وعشرون, 1.5 = واحد فاصلة خمسة (decimals digit by
digit), -5 = سالب خمسة. Hundreds, thousands (ألف ألفان آلاف ألفا), millions (مليون مليونان
ملايين مليونا) and billions (مليار) take their number forms. A year after عام / سنة / العام and
the year of a date are read in the genitive (ألفين وأربعة وعشرين), as newsreaders do.
"""

from __future__ import annotations

import re
import unicodedata

from ..latin_norm import DROP, PAUSE, PRODUCT_CODE

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
PUNCT = str.maketrans({"،": ",", "؛": ";", "؟": "?", "۔": ".", "٫": ".", "٬": ",", "٪": "%",
                       "ـ": None})

ONES = ("صِفْر", "وَاحِد", "اِثْنَان", "ثَلَاثَة", "أَرْبَعَة", "خَمْسَة", "سِتَّة", "سَبْعَة",
        "ثَمَانِيَة", "تِسْعَة", "عَشَرَة")
ONES_GEN = {2: "اِثْنَيْن"}
TEENS = {11: "أَحَدَ عَشَرَ", 12: "اِثْنَا عَشَرَ"}
TEENS_GEN = {12: "اِثْنَيْ عَشَرَ"}
TENS = ("", "", "عِشْرُون", "ثَلَاثُون", "أَرْبَعُون", "خَمْسُون", "سِتُّون", "سَبْعُون",
        "ثَمَانُون", "تِسْعُون")
TENS_GEN = ("", "", "عِشْرِين", "ثَلَاثِين", "أَرْبَعِين", "خَمْسِين", "سِتِّين", "سَبْعِين",
            "ثَمَانِين", "تِسْعِين")
HUNDREDS = ("", "مِئَة", "مِئَتَان", "ثَلَاثُمِئَة", "أَرْبَعُمِئَة", "خَمْسُمِئَة", "سِتُّمِئَة",
            "سَبْعُمِئَة", "ثَمَانِمِئَة", "تِسْعُمِئَة")
HUNDREDS_GEN = {2: "مِئَتَيْن"}
# Scales: (value, one, two (nom, gen), 3-10, 11-99 (accusative singular), 100+)
SCALES = (
    (10 ** 9, "مِلْيَار", ("مِلْيَارَان", "مِلْيَارَيْن"), "مِلْيَارَات", "مِلْيَارًا", "مِلْيَار"),
    (10 ** 6, "مِلْيُون", ("مِلْيُونَان", "مِلْيُونَيْن"), "مَلَايِين", "مِلْيُونًا", "مِلْيُون"),
    (1000, "أَلْف", ("أَلْفَان", "أَلْفَيْن"), "آلَاف", "أَلْفًا", "أَلْف"),
)
AND = "وَ"
MONTHS = ("", "يَنَايِر", "فِبْرَايِر", "مَارِس", "أَبْرِيل", "مَايُو", "يُونْيُو", "يُولْيُو",
          "أُغُسْطُس", "سِبْتَمْبَر", "أُكْتُوبَر", "نُوفَمْبَر", "دِيسَمْبَر")
LETTERS = {"a": "إِيه", "b": "بِي", "c": "سِي", "d": "دِي", "e": "إِي", "f": "إِفْ", "g": "جِي",
           "h": "إِتْشْ", "i": "آي", "j": "جِيه", "k": "كِيه", "l": "إِلْ", "m": "إِمْ", "n": "إِنْ",
           "o": "أُو", "p": "بِي", "q": "كِيُو", "r": "آرْ", "s": "إِسْ", "t": "تِي", "u": "يُو",
           "v": "فِي", "w": "دَبْلِيُو", "x": "إِكْسْ", "y": "وَاي", "z": "زِدْ"}
ABBREVIATIONS = {"د.": "دُكْتُور", "أ.د.": "أُسْتَاذ دُكْتُور", "م.": "مُهَنْدِس",
                 "إلخ": "إِلَى آخِرِه", "الخ": "إِلَى آخِرِه", "ق.م": "قَبْل الْمِيلَاد",
                 "ص.ب": "صُنْدُوق بَرِيد", "ت.": "تُوُفِّي"}
UNITS = {"km/h": "كِيلُومِتْر فِي السَّاعَة", "كم/س": "كِيلُومِتْر فِي السَّاعَة",
         "km": "كِيلُومِتْر", "كم": "كِيلُومِتْر", "cm": "سَنْتِيمِتْر", "سم": "سَنْتِيمِتْر",
         "mm": "مِلِّيمِتْر", "مم": "مِلِّيمِتْر", "m": "مِتْر", "kg": "كِيلُوغْرَام",
         "كغ": "كِيلُوغْرَام", "كجم": "كِيلُوغْرَام", "mg": "مِلِّيغْرَام", "g": "غْرَام",
         "ml": "مِلِّيلِتْر", "l": "لِتْر", "L": "لِتْر", "KB": "كِيلُوبَايْت",
         "MB": "مِيغَابَايْت", "GB": "غِيغَابَايْت", "TB": "تِيرَابَايْت",
         "kWh": "كِيلُووَاط سَاعَة", "kW": "كِيلُووَاط", "W": "وَاط", "V": "فُولْت",
         "mAh": "مِلِّي أَمْبِير سَاعَة", "GHz": "غِيغَاهِرْتْز", "MHz": "مِيغَاهِرْتْز",
         "Hz": "هِرْتْز", "°C": "دَرَجَة مِئَوِيَّة", "℃": "دَرَجَة مِئَوِيَّة", "°": "دَرَجَة"}
# Currency: name forms (1, 2, 3-10, 11-99, 100+).
CURRENCIES = {
    "dollar": ("دُولَار", "دُولَارَان", "دُولَارَات", "دُولَارًا", "دُولَار"),
    "euro": ("يُورُو", "يُورُو", "يُورُو", "يُورُو", "يُورُو"),
    "pound": ("جُنَيْه", "جُنَيْهَان", "جُنَيْهَات", "جُنَيْهًا", "جُنَيْه"),
    "riyal": ("رِيَال", "رِيَالَان", "رِيَالَات", "رِيَالًا", "رِيَال"),
    "dirham": ("دِرْهَم", "دِرْهَمَان", "دَرَاهِم", "دِرْهَمًا", "دِرْهَم"),
    "dinar": ("دِينَار", "دِينَارَان", "دَنَانِير", "دِينَارًا", "دِينَار"),
}
CURRENCY = {"$": ("dollar", ""), "US$": ("dollar", ""), "USD": ("dollar", ""),
            "€": ("euro", ""), "EUR": ("euro", ""), "£": ("pound", "إِسْتِرْلِينِيّ"),
            "ر.س": ("riyal", "سُعُودِيّ"), "SAR": ("riyal", "سُعُودِيّ"), "﷼": ("riyal", ""),
            "د.إ": ("dirham", "إِمَارَاتِيّ"), "AED": ("dirham", "إِمَارَاتِيّ"),
            "د.ك": ("dinar", "كُوَيْتِيّ"), "ج.م": ("pound", "مِصْرِيّ"), "EGP": ("pound", "مِصْرِيّ")}
# Plain Latin words of the tables: lang.py tags them Arabic in mode "ar" (5 km, 100 USD), so they
# are read here with their number; single letters stay English.
LATIN_WORDS = frozenset(k for k in (*UNITS, *CURRENCY)
                        if len(k) > 1 and k.isascii() and k.isalpha())
SYMBOLS = {"&": " وَ ", "+": " زَائِد ", "=": " يُسَاوِي ", "@": " آت ", "×": " ضَرْب ",
           "%": " بِالْمِئَة ", "°": " دَرَجَة ", "/": " ", "#": " "}

AR = "ء-غف-ٰٟ-ۓۺ-ۿﭐ-﷿ﹰ-ﻼ"
NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_A = r"(?<![\w.,])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?<![\d/.-])(\d{1,2})([/.-])(\d{1,2})\2(\d{4})(?![\d/.-])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])"
                  rf"(?:\s*(ص|م|صباحا|مساء)(?![{AR}]))?")
ERA = re.compile(rf"(?<![\d.,])(\d{{3,4}})\s*(هـ|ه|م)(?![{AR}])")  # a year, not 5 م (metres)
YEAR_AFTER = re.compile(rf"((?<![{AR}])(?:[وب]?ال)?(?:عام|سنة)\s+)(\d{{3,4}})(?![\d]|[.,]\d)")
PHONE = re.compile(r"(?<![\d.,])(?:\+\d{1,3}[\s-]?)?\d{2,12}(?:[\s-]\d{2,5}){0,3}(?![\d.,])")
MONEY_BEFORE = re.compile(rf"(?<![\w{AR}])({_CUR_KEYS})\s?({NUM})")
MONEY_AFTER = re.compile(rf"{_A}({NUM})\s?({_CUR_KEYS})(?![\w{AR}])")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + rf")(?![\w{AR}])")
RANGE = re.compile(rf"((?<![{AR}])من\s+)?" + _A + r"(\d+)\s?[-–]\s?(\d+)(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])")
LATIN = re.compile(r"[A-Za-zÀ-ɏ](?:[A-Za-zÀ-ɏ'-]*[A-Za-zÀ-ɏ])?")
WORD = re.compile(rf"[{AR}]+|[^\W\d_]+(?:'[^\W\d_]+)*|[,.?!;:]")
MARKS = ",.?!;:"


def _form(n: int, forms: tuple[str, ...]) -> str:
    """forms = (1, 2, 3-10, 11-99, 100+): the counted-noun form a number takes."""
    r = n % 100
    if n in (1, 2):
        return forms[n - 1]
    if 3 <= r <= 10:
        return forms[2]
    if 11 <= r <= 99:
        return forms[3]
    return forms[4]


def _below_1000(n: int, gen: bool) -> list[str]:
    """Words of 1..999 (each part a word or two; "و" is attached to the parts after the first)."""
    parts: list[str] = []
    h, r = divmod(n, 100)
    if h:
        parts.append(HUNDREDS_GEN.get(h, HUNDREDS[h]) if gen else HUNDREDS[h])
    if r:
        if r <= 10:
            parts.append(ONES_GEN.get(r, ONES[r]) if gen else ONES[r])
        elif r < 20:
            parts.append((TEENS_GEN.get(r) if gen else None) or TEENS.get(r)
                         or f"{ONES[r - 10]}َ عَشَرَ")
        else:
            t, u = divmod(r, 10)
            tens = TENS_GEN[t] if gen else TENS[t]
            if u:
                parts.append(ONES_GEN.get(u, ONES[u]) if gen else ONES[u])
                parts.append(tens)
            else:
                parts.append(tens)
    return parts


def cardinal(n: int, gen: bool = False) -> str:
    """Arabic cardinal (masculine): 21 -> واحد وعشرون, 2500 -> ألفان وخمسمئة."""
    if n < 0:
        return "سَالِب " + cardinal(-n, gen)
    if n <= 10:
        return ONES_GEN.get(n, ONES[n]) if gen else ONES[n]
    if n >= 10 ** 12:
        return digits(str(n))
    parts: list[str] = []
    for scale, one, two, few, many, hundred in SCALES:
        q, n = divmod(n, scale)
        if not q:
            continue
        if q == 1:
            parts.append(one)
        elif q == 2:
            parts.append(two[1] if gen else two[0])
        else:
            parts.append(f"{cardinal(q, gen)} {_form(q, (one, two[0], few, many, hundred))}")
    if n:
        parts += _below_1000(n, gen)
    return " ".join([parts[0], *(AND + p for p in parts[1:])])


def digits(s: str) -> str:
    return " ".join(ONES[int(c)] for c in s if c.isdigit())


def number(s: str, gen: bool = False) -> str:
    """A written number: commas group thousands, the point is فاصلة and the decimals are read
    digit by digit."""
    neg = s.startswith("-")
    whole, _, frac = s.lstrip("-").replace(",", "").partition(".")
    out = cardinal(int(whole or 0), gen)
    if frac:
        out += " فَاصِلَة " + digits(frac)
    return ("سَالِب " if neg else "") + out


def _date(d: int, m: int, y: str) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    return f" {cardinal(d)} {MONTHS[m]} {cardinal(int(y), gen=True)} "


def _time(m: re.Match) -> str:
    h, mi, sec, part = m.groups()
    h, mi = int(h), int(mi)
    out = cardinal(h)
    if mi == 15:
        out += " وَرُبْع"
    elif mi == 30:
        out += " وَنِصْف"
    elif mi:
        out += f" {AND}{cardinal(mi)} دَقِيقَة"
    if sec and int(sec):
        out += f" {AND}{cardinal(int(sec))} ثَانِيَة"
    if part:
        out += " صَبَاحًا" if part in ("ص", "صباحا") else " مَسَاءً"
    return f" {out} "


def _phone(m: re.Match) -> str:
    s = m.group(0)
    if sum(c.isdigit() for c in s) < 10 and not s.startswith("+"):
        return s
    return f" {'زَائِد ' if s.startswith('+') else ''}{digits(s)} "


def _money(num: str, key: str) -> str:
    kind, adj = CURRENCY[key]
    whole, _, frac = num.replace(",", "").partition(".")
    n = int(whole or 0)
    if frac and int(frac):
        name = CURRENCIES[kind][4]
        return f" {number(num)} {name}{' ' + adj if adj else ''} "
    name = _form(n, CURRENCIES[kind])
    words = name if n in (1, 2) else f"{cardinal(n)} {name}"
    return f" {words}{' ' + adj if adj else ''} "


def _spell(code: str) -> str:
    return " ".join(ONES[int(c)] if c.isdigit() else LETTERS[c.lower()]
                    for c in code if c.isdigit() or c.lower() in LETTERS)


def _latin(m: re.Match) -> str:
    from ..en.normalize_en import normalize_en

    folded = "".join(c for c in unicodedata.normalize("NFKD", m.group(0)) if c.isascii())
    return f" {normalize_en(folded)} "


def _abbreviations(t: str) -> str:
    for key in sorted(ABBREVIATIONS, key=len, reverse=True):
        t = re.sub(rf"(?<![{AR}\w])" + re.escape(key) + (rf"(?![{AR}])" if key[-1] != "." else ""),
                   f" {ABBREVIATIONS[key]} ", t)
    return t


def _era(m: re.Match) -> str:
    y, era = m.groups()
    return f" {cardinal(int(y), gen=True)} {'مِيلَادِيّ' if era == 'م' else 'هِجْرِيّ'} "


def normalize_ar(text: str) -> str:
    t = unicodedata.normalize("NFC", text).translate(DIGITS).translate(PUNCT)
    t = _abbreviations(t)
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(3)), m.group(4)) or m.group(0), t)
    t = TIME.sub(_time, t)
    t = ERA.sub(_era, t)
    t = YEAR_AFTER.sub(lambda m: f"{m.group(1)}{cardinal(int(m.group(2)), gen=True)} ", t)
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(2)), t)
    t = PHONE.sub(_phone, t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} بِالْمِئَة ", t)
    t = UNIT.sub(lambda m: f" {number(m.group(1) + m.group(2))} {UNITS[m.group(3)]} ", t)
    t = RANGE.sub(lambda m: f" مِنْ {cardinal(int(m.group(2)), gen=True)} إِلَى "
                  f"{cardinal(int(m.group(3)), gen=True)} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {_spell(m.group(0))} ", t)
    t = NUMBER.sub(lambda m: f" {number(m.group(1) + m.group(2))} ", t)
    t = LATIN.sub(_latin, t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ").replace("–", " ")
    out: list[str] = []
    for w in WORD.findall(t.lower()):
        if w in MARKS and out and out[-1] in MARKS:
            continue
        out.append(w)
    return " ".join(out)
