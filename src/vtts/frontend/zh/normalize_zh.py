"""Mandarin text normalization for one Chinese run.

Output follows the other modules' convention: words and the punctuation tokens , . ? ! ; :
separated by single spaces. A "word" is either a run of Han characters (Chinese has no spaces,
so a whole clause is one word; numbers become Han numerals inside it) or a lower-case Latin word
that the English module reads (letters of product codes, Latin text in a neutral chunk).

Rules, in order: full-width forms to ASCII, Chinese punctuation to , . ? ! ; :, quotes and
brackets dropped, product codes (letters spelled in English, digits one by one), ISO dates,
money, percentages, times, years before 年 digit by digit, ranges, negative numbers, decimals,
grouped numbers, digit strings of 5 or more digits one by one, other integers.
"""

from __future__ import annotations

import re

from .g2p_zh import is_han

DIGITS = "零一二三四五六七八九"
_SECTION_UNITS = ((1000, "千"), (100, "百"), (10, "十"), (1, ""))
_GROUP_UNITS = ("", "万", "亿", "万亿")

_FULLWIDTH = {c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)}
_FULLWIDTH.update({0x3000: 0x20, ord("。"): ord("."), ord("、"): ord(","), ord("｡"): ord("."),
                   ord("､"): ord(","), ord("￥"): ord("¥")})
_DROP = "“”‘’\"「」『』《》〈〉【】〔〕()[]{}<>·•"
_PAUSE = re.compile(r"…+|—+|\.{3,}")
_SYMBOLS = {"℃": "摄氏度", "°C": "摄氏度", "°c": "摄氏度", "°": "度", "+": "加", "&": " and ",
            "@": " at "}

_A = r"(?<![A-Za-z0-9])"  # not inside an ASCII word or number (Han neighbours are fine)
_Z = r"(?![A-Za-z0-9])"
PRODUCT_CODE = re.compile(_A + r"(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+" + _Z)
ISO_DATE = re.compile(_A + r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})" + r"(?!\d)")
MONEY = re.compile(r"([¥$€£])\s?(\d[\d,]*(?:\.\d+)?)")
PERCENT = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)\s?%")
TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])")
YEAR = re.compile(r"(?<!\d)(\d{4})(?=\s*年)")
RANGE = re.compile(r"(?<=\d)\s?[~-]\s?(?=\d)")
NEGATIVE = re.compile(_A + r"-(?=\d)")
DECIMAL = re.compile(r"(?<![\d.])(\d+)\.(\d+)(?![\d.])")
GROUPED = re.compile(r"(?<![\d,])\d{1,3}(?:,\d{3})+(?![\d,])")
LONG_DIGITS = re.compile(r"\d{5,}")
INTEGER = re.compile(r"\d+")
CURRENCY = {"¥": "元", "$": "美元", "€": "欧元", "£": "英镑"}

_WORDS = re.compile(r"[一-鿿]+|[a-z][a-z']*|[,.?!;:]")


def _section(n: int) -> str:
    """1..9999 with zeros read as 零 (一百零五, 一千零一十)."""
    out, zero = "", False
    for div, unit in _SECTION_UNITS:
        d = n // div % 10
        if d == 0:
            zero = bool(out)
        else:
            out += ("零" if zero else "") + DIGITS[d] + unit
            zero = False
    return out


def cardinal(n: int) -> str:
    """Integer in Chinese: 123 -> 一百二十三, 10010 -> 一万零一十, 15 -> 十五."""
    if n < 0:
        return "负" + cardinal(-n)
    if n == 0:
        return DIGITS[0]
    groups = []
    while n:
        groups.append(n % 10000)
        n //= 10000
    if len(groups) > len(_GROUP_UNITS):
        return digits("".join(str(g) for g in groups))
    out, gap = "", False
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if g == 0:
            gap = bool(out)
            continue
        if out and (gap or g < 1000):
            out += "零"
        out += _section(g) + _GROUP_UNITS[idx]
        gap = False
    return out[1:] if out.startswith("一十") else out


def digits(s: str) -> str:
    return "".join(DIGITS[int(c)] for c in s if c.isdigit())


def number(s: str) -> str:
    """'1,250' -> 一千二百五十; '3.14' -> 三点一四."""
    s = s.replace(",", "")
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "." in s:
        a, b = s.split(".", 1)
        out = cardinal(int(a or 0)) + "点" + digits(b)
    else:
        out = cardinal(int(s))
    return ("负" if neg else "") + out


def _code(m: re.Match) -> str:
    return " " + re.sub(r"[A-Z]|[0-9]+", lambda p: f" {p.group(0).lower()} " if p.group(0).isalpha()
                        else digits(p.group(0)), m.group(0)) + " "


def _iso_date(m: re.Match) -> str:
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return m.group(0)
    return f"{digits(y)}年{cardinal(mo)}月{cardinal(d)}日"


def _time(m: re.Match) -> str:
    h, mi, sec = int(m.group(1)), int(m.group(2)), m.group(3)
    out = cardinal(h) + "点"
    if mi or sec:
        out += ("零" + DIGITS[mi] if mi < 10 else cardinal(mi)) + "分"
    if sec and int(sec):
        out += cardinal(int(sec)) + "秒"
    return out


def _latin(m: re.Match) -> str:
    from ..en.normalize_en import normalize_en

    return f" {normalize_en(m.group(0))} "


def normalize_zh(text: str) -> str:
    t = text.translate(_FULLWIDTH)
    t = _PAUSE.sub(",", t)
    for k, v in _SYMBOLS.items():
        t = t.replace(k, v)
    t = t.translate({ord(c): " " for c in _DROP})
    t = PRODUCT_CODE.sub(_code, t)
    t = ISO_DATE.sub(_iso_date, t)
    t = MONEY.sub(lambda m: number(m.group(2)) + CURRENCY[m.group(1)], t)
    t = PERCENT.sub(lambda m: ("负" if m.group(1).startswith("-") else "") + "百分之"
                    + number(m.group(1).lstrip("-")), t)
    t = TIME.sub(_time, t)
    t = YEAR.sub(lambda m: digits(m.group(1)), t)
    t = RANGE.sub("到", t)
    t = NEGATIVE.sub("负", t)
    t = DECIMAL.sub(lambda m: number(m.group(0)), t)
    t = GROUPED.sub(lambda m: number(m.group(0)), t)
    t = LONG_DIGITS.sub(lambda m: digits(m.group(0)), t)
    t = INTEGER.sub(lambda m: cardinal(int(m.group(0))), t)
    t = re.sub(r"[A-Za-z][A-Za-z']*", _latin, t)
    t = re.sub(r"(?<=[一-鿿])\s+(?=[一-鿿])", "", t)
    out: list[str] = []
    for w in _WORDS.findall(t):
        if w in ",.?!;:":
            # A leading mark is kept: it may follow an English word of the previous run
            # ("Wi-Fi，然后"); text.py drops marks that follow nothing.
            if not out or out[-1] not in ",.?!;:":
                out.append(w)
        else:
            out.append(w)
    return " ".join(out)


def is_han_word(word: str) -> bool:
    return bool(word) and all(is_han(ch) for ch in word)
