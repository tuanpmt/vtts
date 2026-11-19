"""German text normalization for one German run (Standard German, Germany).

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces. Umlauts and ß are kept.

Rules, in order: abbreviations (z. B., d. h., usw., bzw., Dr., Nr., Mio. ...), quotes and brackets
dropped, dates (3.5.2026, 03.05.26, 2026-05-03 -> dritter Mai zweitausendsechsundzwanzig; after
am/im/vom ... dritten), times (14:30, 14.30 Uhr, 14 Uhr -> vierzehn Uhr dreißig), phone numbers
(digit by digit), money (5,50 €, € 5, 20 EUR, $ 3, CHF -> fünf Euro fünfzig, null Komma ...),
percentages, units after a number (5 km, 25 °C, 3 Minuten), ordinals with a dot (3. Mai, am
3. Mai -> dritten, die 2. Klasse -> zweite), ranges (10-20 -> zehn bis zwanzig), pause marks,
product codes (ESP32: letters by German name, digits one by one), numbers (1.250,5 or 1,250.5;
einundzwanzig, zweitausendsechsundzwanzig, years 1100-1999 as neunzehnhundert...; "eins" alone,
"ein"/"eine" before a noun; decimals digit by digit after Komma), symbols, acronyms (spelled:
USB -> u ess be; a few read as words: NATO, UNESCO).

split_sentences_de() splits a German text into sentences without cutting after an ordinal dot
(am 3. Mai), an abbreviation (z. B., Dr.) or an initial (J. S. Bach); lang.split_sentences_raw
uses it in mode "de".
"""

from __future__ import annotations

import re

from ..latin_norm import (
    DROP,
    PAUSE,
    PRODUCT_CODE,
    acronyms,
    apply_abbreviations,
    finish,
    parse_number,
)

DIGITS = ("null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun")
ONES = ("", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn", "elf",
        "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn")
TENS = ("", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig", "neunzig")
MONTHS = ("", "januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september",
          "oktober", "november", "dezember")
MONTH_NAMES = frozenset(MONTHS[1:]) | {"jänner"}
ORD_IRREGULAR = {1: "erst", 3: "dritt", 7: "siebt", 8: "acht"}
LETTERS = {"a": "a", "b": "be", "c": "ze", "d": "de", "e": "e", "f": "eff", "g": "ge", "h": "ha",
           "i": "i", "j": "jott", "k": "ka", "l": "ell", "m": "emm", "n": "enn", "o": "o", "p": "pe",
           "q": "kuh", "r": "err", "s": "ess", "t": "te", "u": "u", "v": "fau", "w": "we", "x": "ix",
           "y": "ypsilon", "z": "zett", "ä": "ä", "ö": "ö", "ü": "ü", "ß": "eszett"}
ACRONYM_WORDS = frozenset(("nato", "uno", "unesco", "nasa", "fifa", "uefa", "aids", "dax", "pin",
                           "tan", "ram", "rom", "opec", "unicef", "esa", "kita"))
ABBREVIATIONS = {
    "z. B.": "zum Beispiel", "z.B.": "zum Beispiel", "d. h.": "das heißt", "d.h.": "das heißt",
    "u. a.": "unter anderem", "u.a.": "unter anderem", "z. T.": "zum Teil", "z.T.": "zum Teil",
    "u. U.": "unter Umständen", "o. Ä.": "oder Ähnliches", "o.Ä.": "oder Ähnliches",
    "s. o.": "siehe oben", "s. u.": "siehe unten", "v. Chr.": "vor Christus",
    "n. Chr.": "nach Christus", "usw.": "und so weiter", "bzw.": "beziehungsweise",
    "ca.": "circa", "Dr.": "Doktor", "Prof.": "Professor", "Nr.": "Nummer", "Str.": "Straße",
    "etc.": "et cetera", "vgl.": "vergleiche", "ggf.": "gegebenenfalls", "evtl.": "eventuell",
    "inkl.": "inklusive", "exkl.": "exklusive", "Hr.": "Herr", "Hrn.": "Herrn", "Fr.": "Frau",
    "St.": "Sankt", "Mio.": "Millionen", "Mrd.": "Milliarden", "Tsd.": "tausend",
    "bspw.": "beispielsweise", "sog.": "sogenannte", "Jh.": "Jahrhundert", "Jhd.": "Jahrhundert",
    "MwSt.": "Mehrwertsteuer", "Tel.": "Telefon", "Abs.": "Absatz", "Kap.": "Kapitel",
    "Std.": "Stunden", "max.": "maximal", "zzgl.": "zuzüglich",
    "geb.": "geboren", "gest.": "gestorben", "E-Mail": "ihmehl",
    "E-Mails": "ihmehls", "e-mail": "ihmehl", "WLAN": "we lahn", "Lkw": "el ka we", "LKW": "el ka we",
    "Pkw": "pe ka we", "PKW": "pe ka we", "GmbH": "ge emm be ha", "km/h": "Kilometer pro Stunde",
}
# Units after a number: (singular, plural).
UNITS = {"km/h": ("Kilometer pro Stunde", "Kilometer pro Stunde"), "km": ("Kilometer", "Kilometer"),
         "m": ("Meter", "Meter"), "cm": ("Zentimeter", "Zentimeter"), "mm": ("Millimeter", "Millimeter"),
         "m²": ("Quadratmeter", "Quadratmeter"), "qm": ("Quadratmeter", "Quadratmeter"),
         "km²": ("Quadratkilometer", "Quadratkilometer"), "m³": ("Kubikmeter", "Kubikmeter"),
         "kg": ("Kilogramm", "Kilogramm"), "g": ("Gramm", "Gramm"), "mg": ("Milligramm", "Milligramm"),
         "t": ("Tonne", "Tonnen"), "l": ("Liter", "Liter"), "L": ("Liter", "Liter"),
         "ml": ("Milliliter", "Milliliter"), "min": ("Minute", "Minuten"), "Min.": ("Minute", "Minuten"),
         "h": ("Stunde", "Stunden"), "s": ("Sekunde", "Sekunden"), "Sek.": ("Sekunde", "Sekunden"),
         "ms": ("Millisekunde", "Millisekunden"),
         "GB": ("Gigabyte", "Gigabyte"), "MB": ("Megabyte", "Megabyte"), "TB": ("Terabyte", "Terabyte"),
         "kB": ("Kilobyte", "Kilobyte"), "KB": ("Kilobyte", "Kilobyte"),
         "kWh": ("Kilowattstunde", "Kilowattstunden"), "kW": ("Kilowatt", "Kilowatt"),
         "W": ("Watt", "Watt"), "V": ("Volt", "Volt"), "A": ("Ampere", "Ampere"),
         "mAh": ("Milliamperestunde", "Milliamperestunden"), "GHz": ("Gigahertz", "Gigahertz"),
         "MHz": ("Megahertz", "Megahertz"), "Hz": ("Hertz", "Hertz"), "PS": ("PS", "PS"),
         "°C": ("Grad", "Grad"), "℃": ("Grad", "Grad"), "°": ("Grad", "Grad")}
FEMININE_UNITS = frozenset(("t", "min", "Min.", "h", "s", "Sek.", "ms", "kWh", "mAh"))
CURRENCY = {"€": ("Euro", "Euro"), "EUR": ("Euro", "Euro"), "Euro": ("Euro", "Euro"),
            "US$": ("Dollar", "Dollar"), "$": ("Dollar", "Dollar"), "USD": ("Dollar", "Dollar"),
            "£": ("Pfund", "Pfund"), "CHF": ("Franken", "Franken"), "¥": ("Yen", "Yen")}
CENTS = {"€": "Cent", "EUR": "Cent", "Euro": "Cent", "US$": "Cent", "$": "Cent", "USD": "Cent",
         "£": "Pence", "CHF": "Rappen"}
SYMBOLS = {"&": " und ", "+": " plus ", "=": " gleich ", "@": " ät ", "#": " Raute ", "×": " mal ",
           "/": " ", "%": " Prozent ", "‰": " Promille ", "§": " Paragraf ", "°": " Grad "}
# Before these words an ordinal ends in -en (am 3. Mai -> am dritten Mai).
ORD_EN = frozenset(("am", "im", "vom", "zum", "beim", "dem", "den", "des", "zur", "einem", "einen",
                    "eines", "seinem", "seinen", "seines", "ihrem", "ihren", "ihres", "unserem",
                    "unseren", "diesem", "diesen", "dieses", "jedem", "jeden", "ab", "seit", "bis"))
ORD_E = frozenset(("der", "die", "das", "jeder", "jede", "jedes", "dieser", "diese", "seine", "ihre"))
FEMININE_END = ("e", "ung", "heit", "keit", "schaft", "ion", "tät", "ik", "ei", "ur")

# Only ASCII digits are numbers (other decimal digits are left as they are).
NUM = r"[0-9]{1,3}(?:[.,][0-9]{3})+(?:[.,][0-9]+)?|[0-9]+(?:[.,][0-9]+)?"
LOWER = "abcdefghijklmnopqrstuvwxyzäöüß"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ"
_A = r"(?<![\w.,])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?<![0-9.])([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4}|[0-9]{2})?(?![0-9])")
DATE_ISO = re.compile(r"(?<![0-9-])([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})(?![0-9-])")
TIME = re.compile(r"(?<![0-9:.,])([01]?[0-9]|2[0-4])(?::([0-5][0-9])(?::([0-5][0-9]))?(?:\s?Uhr\b)?(?![0-9])"
                  r"|\.([0-5][0-9])\s?Uhr\b)|(?<![\w:.,])([01]?[0-9]|2[0-4])\s?Uhr\b")
PHONE = re.compile(r"(?<![0-9])(?:\+[0-9]{1,3}[\s-])?(?:\(0[0-9]{1,4}\)\s?)?0?[0-9]{2,5}(?:[\s/-][0-9]{2,8}){1,4}(?![0-9])"
                   r"|(?<![0-9.,])0[0-9]{5,}(?![0-9]|[.,][0-9])")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(-?)(" + NUM + r")(?:,-)?(?![0-9])")
MONEY_AFTER = re.compile(_A + r"(-?)(" + NUM + r")(?:,-)?\s?(" + _CUR_KEYS + r")(?![\w])")
PERCENT = re.compile(_A + r"([-−]?)(" + NUM + r")\s?(%|‰)")
UNIT = re.compile(_A + r"([-−]?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w²³])")
ORDINAL = re.compile(r"(?<![\w.,])([0-9]{1,4})\.(?=\s+([A-Za-zÄÖÜäöüß]+))")
RANGE = re.compile(_A + r"([0-9]+)\s?[-–]\s?([0-9]+)(?![\w.,])")
NUMBER = re.compile(r"(?<![\w.,])([-−]?)(" + NUM + r")(?![0-9])")
ABBREV_DOT = re.compile(r"(?:^|(?<=\s))(?:" + "|".join(re.escape(k[:-1]) for k in ABBREVIATIONS if k.endswith("."))
                        + r")$")


def _below_1000(n: int, final: bool) -> str:
    h, r = divmod(n, 100)
    out = ("" if h == 1 else ONES[h]) + "hundert" if h else ""
    if r == 1:
        out += "eins" if final else "ein"
    elif r < 20:
        out += ONES[r]
    else:
        t, u = divmod(r, 10)
        out += (ONES[u] + "und" if u else "") + TENS[t]
    return out


def cardinal(n: int, final: bool = True) -> str:
    """German cardinal: 1 -> eins (final) / ein, 21 -> einundzwanzig, 100 -> einhundert,
    2026 -> zweitausendsechsundzwanzig, 2_000_000 -> zwei Millionen. Words below a million are one
    word; Millionen and Milliarden are separate words."""
    if n < 0:
        return "minus " + cardinal(-n, final)
    if n == 0:
        return "null"
    if n >= 10 ** 15:
        return " ".join(DIGITS[int(c)] for c in str(n))
    parts: list[str] = []
    for scale, one, many in ((10 ** 12, "Billion", "Billionen"), (10 ** 9, "Milliarde", "Milliarden"),
                             (10 ** 6, "Million", "Millionen")):
        q, n = divmod(n, scale)
        if q == 1:
            parts.append(f"eine {one}")
        elif q:
            parts.append(f"{cardinal(q, False)} {many}")
    if n:
        th, r = divmod(n, 1000)
        word = ("" if th == 1 else _below_1000(th, False)) + "tausend" if th else ""
        if r:
            word += _below_1000(r, final)
        parts.append(word)
    return " ".join(parts)


def year(n: int) -> str:
    """1100-1999 as hundreds (neunzehnhundertneunundneunzig), else the cardinal."""
    if 1100 <= n <= 1999:
        h, r = divmod(n, 100)
        return ONES[h] + "hundert" + (_below_1000(r, True) if r else "")
    return cardinal(n)


def ordinal_stem(n: int) -> str:
    """3 -> dritt, 20 -> zwanzigst, 101 -> hunderterst; endings are added by the caller."""
    if n <= 0:
        return cardinal(n) + "t"
    if n >= 10 ** 6:
        return cardinal(n).replace(" ", "") + "st"
    r = n % 100
    head = cardinal(n - r, False) if n >= 100 else ""
    if head and r == 0:
        return head + "st"
    if r in ORD_IRREGULAR:
        return head + ORD_IRREGULAR[r]
    if r < 20:
        return head + cardinal(r, False) + "t"
    return head + cardinal(r, False) + "st"


def number(s: str, final: bool = True) -> str:
    """A written number: decimal part after Komma digit by digit (3,14 -> drei Komma eins vier)."""
    neg = s[:1] in "-−"
    n, frac, _ = parse_number(s.lstrip("-−"))
    if frac is None and 1100 <= n <= 1999 and re.fullmatch(r"[0-9]{4}", s.lstrip("-−")):
        out = year(n)
    else:
        out = cardinal(n, final or frac is not None)
    if frac is not None:
        out += " Komma " + " ".join(DIGITS[int(c)] for c in frac if "0" <= c <= "9")
    return ("minus " if neg else "") + out


def _one(s: str) -> bool:
    n, frac, _ = parse_number(s.lstrip("-−"))
    return n == 1 and frac is None


def _count(s: str, feminine: bool) -> str:
    """A count before a noun: 1 -> ein / eine."""
    if _one(s):
        return ("minus " if s[:1] in "-−" else "") + ("eine" if feminine else "ein")
    return number(s)


def _date(d: int, m: int, y: str | None, prev: str) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    end = "en" if prev in ORD_EN else "e" if prev in ORD_E else "er"
    out = f"{ordinal_stem(d)}{end} {MONTHS[m]}"
    if y is not None:
        out += " " + year(int(y) + (2000 if len(y) == 2 else 0))
    return f" {out} "


def _prev_word(text: str, pos: int) -> str:
    m = re.search(r"([A-Za-zÄÖÜäöüß]+)\W*$", text[:pos])
    return m.group(1).lower() if m else ""


def _time(m: re.Match) -> str:
    if m.group(5) is not None:
        h, mi, sec = int(m.group(5)), 0, 0
    else:
        h, mi, sec = int(m.group(1)), int(m.group(2) or m.group(4)), int(m.group(3) or 0)
    out = f"{cardinal(h, False)} Uhr" + (f" {cardinal(mi)}" if mi else "")
    if sec:
        out += f" und {cardinal(sec)} {'Sekunde' if sec == 1 else 'Sekunden'}"
    return f" {out} "


def _money(sign: str, num: str, cur: str) -> str:
    """5,50 € -> fünf Euro fünfzig; 0,99 € -> neunundneunzig Cent; 1 € -> ein Euro."""
    n, frac, _ = parse_number(num)
    neg = "minus " if sign else ""
    if frac is not None and len(frac) == 2:
        cents = int(frac)
        if n == 0 and cents:
            return f" {neg}{cardinal(cents, False)} {CENTS.get(cur, 'Cent')} "
        out = f"{neg}{'ein' if n == 1 else cardinal(n)} {CURRENCY[cur][0]}"
        if cents:
            out += f" {cardinal(cents)}"
        return f" {out} "
    if frac is not None:
        return f" {neg}{number(num)} {CURRENCY[cur][1]} "
    return f" {neg}{'ein' if n == 1 else cardinal(n)} {CURRENCY[cur][0]} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    sing, plur = UNITS[unit]
    words = _count(sign + num, unit in FEMININE_UNITS)
    return f" {words} {sing if _one(num) else plur} "


def _ordinal(m: re.Match, text: str) -> str:
    n, nxt = int(m.group(1)), m.group(2)
    prev = _prev_word(text, m.start())
    nl = nxt.lower()
    if nl in MONTH_NAMES or nxt[0] in LOWER or prev in ORD_EN or prev in ORD_E or prev in ("ein", "zum"):
        end = "en" if prev in ORD_EN else "e" if prev in ORD_E else "er" if (
            nl in MONTH_NAMES or prev == "ein") else "e"
        return f" {ordinal_stem(n)}{end} "
    return m.group(0)


def _number(m: re.Match, text: str) -> str:
    sign, num = m.groups()
    nxt = re.match(r"\s*([A-Za-zÄÖÜäöüß]+)", text[m.end():])
    if _one(num) and nxt and nxt.group(1)[0] in UPPER:  # 1 Stunde -> eine Stunde
        word = nxt.group(1).lower()
        return " " + _count(sign + num, word.endswith(FEMININE_END)) + " "
    return f" {number(sign + num)} "


def spell(word: str) -> str:
    out = []
    for ch in word:
        if "0" <= ch <= "9":
            out.append(DIGITS[int(ch)])
        elif ch.lower() in LETTERS:
            out.append(LETTERS[ch.lower()])
    return " ".join(out)


def normalize_de(text: str) -> str:
    t = apply_abbreviations(text, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP.replace("(", "").replace(")", "")})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1),
                                     _prev_word(m.string, m.start())) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: (_date(int(m.group(1)), int(m.group(2)), m.group(3),
                                      _prev_word(m.string, m.start())) or m.group(0))
                     if m.group(3) or re.match(r"\s", m.string[m.end():] or " ") else m.group(0), t)
    t = TIME.sub(_time, t)
    t = PHONE.sub(lambda m: _phone(m.group(0)), t)
    t = t.replace("(", " ").replace(")", " ")
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(3), m.group(1)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(2), m.group(3)), t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} "
                              f"{'Prozent' if m.group(3) == '%' else 'Promille'} ", t)
    t = UNIT.sub(_unit, t)
    t = ORDINAL.sub(lambda m: _ordinal(m, m.string), t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} bis {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0))} ", t)
    t = NUMBER.sub(lambda m: _number(m, m.string), t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ").replace("−", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    return finish(t)


def _phone(s: str) -> str:
    """A phone number digit by digit (+ read as plus); short digit groups are left to the number
    rules."""
    n = sum(c.isdigit() for c in s)
    if n < 6 or not s.startswith(("0", "+", "(")):
        return s
    lead = "plus " if s.startswith("+") else ""
    return " " + lead + " ".join(DIGITS[int(c)] for c in s if c.isdigit()) + " "


# ---------------- sentence splitting ----------------

_END = re.compile(r"[.!?;]+(?=\s)|[。！？；।॥]")


def _ordinal_follows(left: str, number: str, rest: str) -> bool:
    """Is "number." an ordinal: followed by a lower-case word or a month, or after am, die ...?"""
    nxt = rest.split()[0].strip(".,;:!?").lower()
    prev = _prev_word(left, len(left) - len(number) - 1)
    return rest[0] in LOWER or nxt in MONTH_NAMES or prev in ORD_EN or prev in ORD_E


def split_sentences_de(text: str) -> list[str]:
    """Sentences of a German text: a dot after an ordinal number followed by a word (am 3. Mai, die
    2. Klasse), after an abbreviation of ABBREVIATIONS (z. B., Dr., Nr.) or after a single letter
    (J. S. Bach) does not end the sentence."""
    out: list[str] = []
    start = 0
    text = text.strip()
    for m in _END.finditer(text):
        end = m.end()
        left = text[start:end]
        if m.group(0) == ".":
            word = re.search(r"(\S+)\.$", left)
            w = word.group(1) if word else ""
            rest = text[end:].lstrip()
            if re.fullmatch(r"[0-9]{1,4}", w) and rest and _ordinal_follows(left, w, rest):
                continue
            abbrev = re.fullmatch(r"[A-Za-zÄÖÜ]", w) or w + "." in ABBREVIATIONS or ABBREV_DOT.search(left[:-1])
            if abbrev and rest and not (w + "." in ("usw.", "etc.") and rest[:1] in tuple(UPPER)):
                continue
        piece = left.strip()
        if piece:
            out.append(piece)
        start = end
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out
