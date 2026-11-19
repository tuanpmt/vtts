"""Lao text normalization for one Lao run (the passes of th/normalize_th.py with Lao tables).

Output follows the other modules' convention: words and the punctuation tokens , . ? ! ; :
separated by single spaces. A "word" is either a run of Lao letters (Lao has no spaces between
words, so a whole clause is one word; numbers become Lao number words inside it) or a lower-case
Latin word that the English module reads (letters of product codes, Latin text in a neutral chunk).

Lao puts spaces between clauses and sentences, and around numbers and foreign words. A space
between two runs of Lao letters is read as a pause (","); spaces around numbers, ໆ and ຯ are not.

Rules, in order: Lao digits to ASCII, pause marks, quotes and brackets dropped, abbreviations
(ຄ.ສ., ພ.ສ., ກມ., ຯລຯ; any other ຯ is dropped), product codes (letters in English, digits one by
one), dates (19/11/2026, 2026-11-19: day, month name, year), times (14:30: ໂມງ and ນາທີ), money
(₭, $, €, £, ¥, ฿ before the number), percentages (ເປີເຊັນ), units after a number, phone numbers
(digit by digit), ranges (10-20 -> ຫາ), negative numbers (ລົບ), decimals (ຈຸດ and digits one by
one), grouped numbers, digit strings with a leading 0 or of 8 or more digits one by one, other
integers (ເອັດ for a final 1 after tens, ຊາວ for 20, ໝື່ນ ແສນ ລ້ານ). Latin words go to the English
normalizer.
"""

from __future__ import annotations

import re

DIGITS = ("ສູນ", "ໜຶ່ງ", "ສອງ", "ສາມ", "ສີ່", "ຫ້າ", "ຫົກ", "ເຈັດ", "ແປດ", "ເກົ້າ")
PLACES = ("", "ສິບ", "ຮ້ອຍ", "ພັນ", "ໝື່ນ", "ແສນ")
MILLION = "ລ້ານ"
MONTHS = ("", "ມັງກອນ", "ກຸມພາ", "ມີນາ", "ເມສາ", "ພຶດສະພາ", "ມິຖຸນາ", "ກໍລະກົດ", "ສິງຫາ", "ກັນຍາ",
          "ຕຸລາ", "ພະຈິກ", "ທັນວາ")
ABBREVIATIONS = {
    "ຯລຯ": "ແລະອື່ນໆ", "ຄ.ສ.": "ຄິດສະຕະສັກກະລາດ", "ພ.ສ.": "ພຸດທະສັກກະລາດ", "ກມ.": "ກິໂລແມັດ",
    "ຊມ.": "ຊັງຕີແມັດ", "ມມ.": "ມິນລີແມັດ", "ກກ.": "ກິໂລກຣາມ", "ດຣ.": "ດອກເຕີ", "ທ.": "ທ້າວ",
    "ນ.": "ນາງ", "ສ.ປ.ປ.": "ສາທາລະນະລັດປະຊາທິປະໄຕປະຊາຊົນ",
}
UNITS = {"km/h": "ກິໂລແມັດຕໍ່ຊົ່ວໂມງ", "km": "ກິໂລແມັດ", "kg": "ກິໂລກຣາມ", "cm": "ຊັງຕີແມັດ",
         "mm": "ມິນລີແມັດ", "°C": "ອົງສາເຊ", "℃": "ອົງສາເຊ", "°": "ອົງສາ", "GB": "ກິກະໄບ",
         "MB": "ເມກະໄບ", "m": "ແມັດ", "g": "ກຣາມ", "ml": "ມິນລີລິດ", "l": "ລິດ"}
CURRENCY = {"₭": "ກີບ", "$": "ໂດລາ", "€": "ເອີໂຣ", "£": "ປອນ", "¥": "ເຢນ", "฿": "ບາດ"}
SYMBOLS = {"+": "ບວກ", "=": "ເທົ່າກັບ", "&": " and ", "@": " at ", "×": "ຄູນ"}

_LAO_DIGITS = {ord("໐") + k: ord("0") + k for k in range(10)}
_FULLWIDTH = {c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)}
_DROP = "“”‘’\"«»「」『』()[]{}<>·•"
_PAUSE = re.compile(r"…+|—+|–(?!\d)|\.{3,}")
_GLUE = "\x01"  # number words: spaces next to them are dropped
LAO = "ກ-ໍໜ-ໟ"

_A = r"(?<![A-Za-z0-9])"
_Z = r"(?![A-Za-z0-9])"
NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
PRODUCT_CODE = re.compile(_A + r"(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+" + _Z)
DATE_DMY = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])")
MONEY_BEFORE = re.compile(r"([₭$€£¥฿])\s?(" + NUM + r")")
PERCENT = re.compile(r"(-?)(" + NUM + r")\s?%")
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
UNIT = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![A-Za-z])")
RANGE = re.compile(r"(?<![\d.,])(" + NUM + r")\s?[-–]\s?(?=\d)")
NEGATIVE = re.compile(r"(?<![\w\d])-(?=\d)")
PHONE = re.compile(r"(?<![\d.,-])(?:\+\d{1,3}[\s-]?)?0?\d{1,2}(?:[\s-]\d{3,4}){2}(?![\d-])"
                   r"|(?<![\d.,-])0\d{1,2}-\d{3,4}-?\d{0,4}(?![\d-])")
LONG_DIGITS = re.compile(r"(?<![\d.,])(?:0\d{2,}|\d{8,})(?![\d.,]\d)")
NUMBER = re.compile(r"(?<![\d.,])(" + NUM + r")(?![\d])")
ABBREV = re.compile(r"(?<![" + LAO + r".])(?:" + "|".join(
    re.escape(k) for k in sorted(ABBREVIATIONS, key=len, reverse=True) if "." in k) + ")")
LAO_SPACE = re.compile(r"(?<=[" + LAO + r"])\s+(?=[" + LAO + r"])")
_WORDS = re.compile(r"[" + LAO + r"]+|[a-z][a-z']*|[,.?!;:]")


def _below_million(n: int, final_one: bool) -> str:
    """1..999999; a final 1 after other digits is ເອັດ (ສິບເອັດ, ຮ້ອຍເອັດ) when final_one; 20 is ຊາວ."""
    out = []
    ds = [int(c) for c in str(n)][::-1]
    for place in range(len(ds) - 1, -1, -1):
        d = ds[place]
        if d == 0:
            continue
        if place == 1:
            out.append({1: "ສິບ", 2: "ຊາວ"}.get(d, DIGITS[d] + "ສິບ"))
        elif place == 0:
            out.append("ເອັດ" if d == 1 and final_one and n > 1 and len(out) else DIGITS[d])
        else:
            out.append(DIGITS[d] + PLACES[place])
    return "".join(out)


def cardinal(n: int) -> str:
    """Integer in Lao: 21 -> ຊາວເອັດ, 101 -> ໜຶ່ງຮ້ອຍເອັດ, 2_000_000 -> ສອງລ້ານ."""
    if n < 0:
        return "ລົບ" + cardinal(-n)
    if n == 0:
        return DIGITS[0]
    high, low = divmod(n, 1_000_000)
    out = cardinal(high) + MILLION if high else ""
    if low:
        out += _below_million(low, final_one=True) if low > 1 or not high else DIGITS[1]
    return out


def digits(s: str) -> str:
    return "".join(DIGITS[int(c)] for c in s if c.isdigit())


def number(s: str) -> str:
    """'1,250' -> ໜຶ່ງພັນສອງຮ້ອຍຫ້າສິບ; '3.14' -> ສາມຈຸດໜຶ່ງສີ່."""
    s = s.replace(",", "")
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "." in s:
        a, b = s.split(".", 1)
        out = cardinal(int(a or 0)) + "ຈຸດ" + digits(b)
    else:
        out = cardinal(int(s))
    return ("ລົບ" if neg else "") + out


def _g(text: str) -> str:
    return _GLUE + text + _GLUE


def _date(d: int, m: int, y: str) -> str | None:
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    year = cardinal(int(y)) if len(y) == 4 else digits(y)
    return _g(f"{cardinal(d)}{MONTHS[m]}{year}")


def _time(m: re.Match) -> str:
    h, mi, sec = int(m.group(1)), int(m.group(2)), m.group(3)
    out = cardinal(h) + "ໂມງ"
    if mi:
        out += cardinal(mi) + "ນາທີ"
    if sec and int(sec):
        out += cardinal(int(sec)) + "ວິນາທີ"
    return _g(out)


def _code(m: re.Match) -> str:
    return " " + re.sub(r"[A-Z]|[0-9]+", lambda p: f" {p.group(0).lower()} " if p.group(0).isalpha()
                        else _g(digits(p.group(0))), m.group(0)) + " "


def _latin(m: re.Match) -> str:
    from ..en.normalize_en import normalize_en

    return f" {normalize_en(m.group(0))} "


def normalize_lo(text: str) -> str:
    t = text.translate(_LAO_DIGITS).translate(_FULLWIDTH)
    t = _PAUSE.sub(" , ", t)
    t = t.translate({ord(c): " " for c in _DROP})
    t = t.replace("ຯລຯ", ABBREVIATIONS["ຯລຯ"])
    t = ABBREV.sub(lambda m: _g(ABBREVIATIONS[m.group(0)]), t)
    t = t.replace("ຯ", "")
    t = re.sub(r"\s*ໆ\s*", "ໆ", t)
    t = PRODUCT_CODE.sub(_code, t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = TIME.sub(_time, t)
    t = MONEY_BEFORE.sub(lambda m: _g(number(m.group(2)) + CURRENCY[m.group(1)]), t)
    t = PERCENT.sub(lambda m: _g(("ລົບ" if m.group(1) else "") + number(m.group(2)) + "ເປີເຊັນ"), t)
    t = UNIT.sub(lambda m: _g(("ລົບ" if m.group(1) else "") + number(m.group(2)) + UNITS[m.group(3)]), t)
    t = PHONE.sub(lambda m: _g(digits(m.group(0))), t)
    t = RANGE.sub(lambda m: _g(number(m.group(1)) + "ຫາ"), t)
    t = NEGATIVE.sub(_g("ລົບ"), t)
    t = LONG_DIGITS.sub(lambda m: _g(digits(m.group(0))), t)
    t = NUMBER.sub(lambda m: _g(number(m.group(1))), t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, _g(v) if v.strip() == v else v)
    t = re.sub(r"[A-Za-z][A-Za-z']*", _latin, t)
    t = re.sub(r"\s*" + _GLUE + r"\s*", _GLUE, t)
    t = LAO_SPACE.sub(" , ", t)
    t = t.replace(_GLUE, "")
    out: list[str] = []
    for w in _WORDS.findall(t):
        if w in ",.?!;:":
            # A leading mark is kept: it may follow an English word of the previous run;
            # text.py drops marks that follow nothing.
            if not out or out[-1] not in ",.?!;:":
                out.append(w)
        else:
            out.append(w)
    return " ".join(out)


def is_lao_word(word: str) -> bool:
    return bool(word) and all("ກ" <= ch <= "ໍ" or "ໜ" <= ch <= "ໟ" for ch in word)
