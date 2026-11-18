"""Hindi text normalization for one Hindi run.

Output follows the other modules' convention: words and the punctuation tokens , . ? ! ; :
separated by single spaces. Devanagari words are kept as written (NFC); Latin parts go through
the English normalizer (lower case) and are read by the English module.

Rules, in order: Devanagari digits ०-९ -> 0-9, danda । and double danda ॥ -> "." (lang.py
already ends a sentence there), abbreviations (डॉ., प्रो., कि.मी.), quotes and brackets
dropped, dates (15/08/1947, 2026-11-19: day, month name, year), times (7:30 -> सात बजकर तीस
मिनट, 7:00 -> सात बजे; a following बजे is absorbed), years after सन / सन् (उन्नीस सौ
सैंतालीस), phone numbers (10+ digits or +CC: digit by digit), money (₹500, Rs 99, रु. 250, ₹1.50
-> एक रुपया पचास पैसे, $20), percentages, units after a number (5 km, 128GB, 30°C), ordinals
with a Hindi suffix (10वीं -> दसवीं, 1ला / 1st are not handled), ranges (10-20 -> दस से बीस),
pause marks, product codes (ESP32: Latin letters by their Hindi names, digits one by one),
numbers (Indian 1,25,000 or Western 125,000 grouping; the decimal point is दशमलव and the
decimals are read digit by digit), symbols, hyphens.

Numbers 0-99 are irregular in Hindi and come from lexicons/hi/numbers.tsv; larger numbers use
सौ (100), हज़ार (1,000), लाख (1,00,000) and करोड़ (1,00,00,000); the count of crores may itself
exceed 99 (एक सौ करोड़ = 10^9).
"""

from __future__ import annotations

import functools
import re
import unicodedata

from ..latin_norm import DROP, PAUSE, PRODUCT_CODE
from ..lexicons import load_table

DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
SCALES = ((10 ** 7, "करोड़"), (10 ** 5, "लाख"), (1000, "हज़ार"), (100, "सौ"))
MONTHS = ("", "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर",
          "अक्टूबर", "नवंबर", "दिसंबर")
LETTERS = {"a": "ए", "b": "बी", "c": "सी", "d": "डी", "e": "ई", "f": "एफ़", "g": "जी", "h": "एच",
           "i": "आई", "j": "जे", "k": "के", "l": "एल", "m": "एम", "n": "एन", "o": "ओ", "p": "पी",
           "q": "क्यू", "r": "आर", "s": "एस", "t": "टी", "u": "यू", "v": "वी", "w": "डब्ल्यू",
           "x": "एक्स", "y": "वाई", "z": "ज़ेड"}
ABBREVIATIONS = {"डॉ.": "डॉक्टर", "प्रो.": "प्रोफ़ेसर", "कि.मी.": "किलोमीटर", "कि.ग्रा.": "किलोग्राम",
                 "नं.": "नंबर", "पृ.": "पृष्ठ", "लि.": "लिमिटेड", "स्व.": "स्वर्गीय"}
UNITS = {"km/h": "किलोमीटर प्रति घंटा", "km": "किलोमीटर", "cm": "सेंटीमीटर", "mm": "मिलीमीटर",
         "m": "मीटर", "kg": "किलोग्राम", "mg": "मिलीग्राम", "g": "ग्राम", "ml": "मिलीलीटर",
         "l": "लीटर", "L": "लीटर", "KB": "किलोबाइट", "MB": "मेगाबाइट", "GB": "गीगाबाइट",
         "TB": "टेराबाइट", "kWh": "किलोवाट घंटा", "kW": "किलोवाट", "W": "वाट", "V": "वोल्ट",
         "mAh": "मिलीएम्पियर घंटा", "GHz": "गीगाहर्ट्ज़", "MHz": "मेगाहर्ट्ज़", "Hz": "हर्ट्ज़",
         "°C": "डिग्री सेल्सियस", "℃": "डिग्री सेल्सियस", "°": "डिग्री"}
CURRENCY = {"₹": "रुपये", "Rs.": "रुपये", "Rs": "रुपये", "INR": "रुपये", "रु.": "रुपये",
            "रु": "रुपये", "$": "डॉलर", "US$": "डॉलर", "€": "यूरो", "£": "पाउंड"}
# Plain Latin words of the tables: lang.py tags them Hindi in mode "hi" (5 km, Rs 99), so they are
# read here with their number; single letters stay English.
LATIN_WORDS = frozenset(k for k in (*UNITS, *CURRENCY)
                        if len(k.rstrip(".")) > 1 and k.rstrip(".").isascii()
                        and k.rstrip(".").isalpha())
SYMBOLS = {"&": " और ", "+": " प्लस ", "=": " बराबर ", "@": " ऐट ", "×": " गुणा ",
           "%": " प्रतिशत ", "°": " डिग्री ", "/": " "}
ORDINAL_STEMS = {1: "पहल", 2: "दूसर", 3: "तीसर", 4: "चौथ", 6: "छठ"}
ORDINAL_ENDINGS = {"वाँ": "ा", "वां": "ा", "वीं": "ी", "वी": "ी", "वें": "े", "वे": "े"}

NUM = r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_A = r"(?<![\w.,])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?<![\d/.-])(\d{1,2})([/.-])(\d{1,2})\2(\d{4}|\d{2})(?![\d/.-])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])(\s*बजे)?")
YEAR = re.compile(r"(सन्?|ईस्वी)\s+(\d{4})(?!\d)")
PHONE = re.compile(r"(?<![\d.,])(?:\+\d{1,3}[\s-]?)?\d{2,12}(?:[\s-]\d{2,5}){0,3}(?![\d.,])")
MONEY = re.compile(r"(?<![\wऀ-ॿ])(" + _CUR_KEYS + r")\s?(" + NUM + r")(\s?(?:हज़ार|लाख|करोड़))?")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(r"(?<![\w])(\d+)\s?(" + "|".join(ORDINAL_ENDINGS) + r")(?![ऀ-ॿ])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])")
LATIN = re.compile(r"[A-Za-zÀ-ɏ](?:[A-Za-zÀ-ɏ'-]*[A-Za-zÀ-ɏ])?")
WORD = re.compile(r"[ऀ-ॣॱ-ॿ꣠-ꣿ]+|[^\W\d_]+(?:'[^\W\d_]+)*|[,.?!;:]")
MARKS = ",.?!;:"


@functools.cache
def number_words() -> dict[int, str]:
    """0..99 -> Hindi word (lexicons/hi/numbers.tsv)."""
    return {int(k): v for k, v in load_table("hi", "numbers").items()}


def digit_names() -> tuple[str, ...]:
    return tuple(number_words()[d] for d in range(10))


def digits(s: str) -> str:
    return " ".join(number_words()[int(c)] for c in s if c.isdigit())


def cardinal(n: int) -> str:
    """Hindi cardinal: 25 -> पच्चीस, 125000 -> एक लाख पच्चीस हज़ार, 10**9 -> एक सौ करोड़."""
    if n < 0:
        return "माइनस " + cardinal(-n)
    if n < 100:
        return number_words()[n]
    if n >= 10 ** 15:
        return digits(str(n))
    parts = []
    for scale, name in SCALES:
        q, n = divmod(n, scale)
        if q:
            parts.append(f"{cardinal(q)} {name}")
    if n:
        parts.append(number_words()[n])
    return " ".join(parts)


def year(y: int) -> str:
    """1100-1999 by hundreds (उन्नीस सौ सैंतालीस); other years as cardinals (दो हज़ार छब्बीस)."""
    if 1100 <= y <= 1999:
        h, r = divmod(y, 100)
        return f"{cardinal(h)} सौ" + (f" {cardinal(r)}" if r else "")
    return cardinal(y)


def number(s: str) -> str:
    """A written number: commas group digits (Indian or Western), the point is दशमलव and the
    decimals are read digit by digit."""
    neg = s.startswith("-")
    whole, _, frac = s.lstrip("-").replace(",", "").partition(".")
    out = cardinal(int(whole or 0))
    if frac:
        out += " दशमलव " + digits(frac)
    return ("माइनस " if neg else "") + out


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{cardinal(d)} {MONTHS[m]}"
    if y is not None:
        out += f" {year(int(y) + (2000 if len(y) == 2 else 0))}"
    return f" {out} "


def _time(m: re.Match) -> str:
    h, mi, sec, _ = m.groups()
    h, mi = int(h), int(mi)
    out = f"{cardinal(h)} बजे" if not mi else f"{cardinal(h)} बजकर {cardinal(mi)} मिनट"
    if sec and int(sec):
        out += f" {cardinal(int(sec))} सेकंड"
    return f" {out} "


def _phone(m: re.Match) -> str:
    s = m.group(0)
    if sum(c.isdigit() for c in s) < 10 and not s.startswith("+"):
        return s
    return f" {'प्लस ' if s.startswith('+') else ''}{digits(s)} "


def _money(m: re.Match) -> str:
    cur, num, scale = m.groups()
    name = CURRENCY[cur]
    whole, _, frac = num.replace(",", "").partition(".")
    if name == "रुपये" and not scale:
        rupees = "रुपया" if int(whole) == 1 else "रुपये"
        if len(frac) == 2:
            paise = f" {cardinal(int(frac))} पैसे" if int(frac) else ""
            return f" {cardinal(int(whole))} {rupees}{paise} "
        if not frac:
            return f" {cardinal(int(whole))} {rupees} "
    return f" {number(num)}{' ' + scale.strip() if scale else ''} {name} "


def _ordinal(m: re.Match) -> str:
    n, suffix = int(m.group(1)), m.group(2)
    if n in ORDINAL_STEMS:
        return f" {ORDINAL_STEMS[n]}{ORDINAL_ENDINGS[suffix]} "
    return f" {cardinal(n)}{suffix} "


def _spell(code: str) -> str:
    return " ".join(number_words()[int(c)] if c.isdigit() else LETTERS[c.lower()]
                    for c in code if c.isdigit() or c.lower() in LETTERS)


def _latin(m: re.Match) -> str:
    from ..en.normalize_en import normalize_en

    folded = "".join(c for c in unicodedata.normalize("NFKD", m.group(0)) if c.isascii())
    return f" {normalize_en(folded)} "


def _abbreviations(t: str) -> str:
    for key in sorted(ABBREVIATIONS, key=len, reverse=True):
        t = re.sub(r"(?<![ऀ-ॿ\w])" + re.escape(key), f" {ABBREVIATIONS[key]} ", t)
    return t


def normalize_hi(text: str) -> str:
    t = unicodedata.normalize("NFC", text).translate(DIGITS)
    t = t.replace("॰", ".")
    t = _abbreviations(t)
    t = t.replace("॥", " . ").replace("।", " . ")
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(3)), m.group(4)) or m.group(0), t)
    t = TIME.sub(_time, t)
    t = YEAR.sub(lambda m: f" {m.group(1)} {year(int(m.group(2)))} ", t)
    t = MONEY.sub(_money, t)
    t = PHONE.sub(_phone, t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} प्रतिशत ", t)
    t = UNIT.sub(lambda m: f" {number(m.group(1) + m.group(2))} {UNITS[m.group(3)]} ", t)
    t = ORDINAL.sub(_ordinal, t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} से {cardinal(int(m.group(2)))} ", t)
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
