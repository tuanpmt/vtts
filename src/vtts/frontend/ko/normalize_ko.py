"""Korean text normalization for one Korean run.

Output follows the other modules' convention: words and the punctuation tokens , . ? ! ; :
separated by single spaces. A word is a run of Hangul syllables (Korean is written with spaces
between words, 어절) or a lower-case Latin word that the English module reads.

Numbers are Sino-Korean (삼백오십) except before a native counter (개 명 살 시 ...), where 1-99 are
native (세 개, 스무 살, 아홉 시). A number is joined to a following particle or to 년/월/일
(이천이십육년, 십일월) and separated from other counters by a space (세 개, 삼십 분).

Rules, in order: full-width forms, pause marks, symbols, quotes and brackets dropped, units,
product codes (letters and digits in English), dates (ISO and 2026. 6. 10.), phone numbers
(digit by digit, 0 = 공), times (9:30), money, percentages, ranges (3~5, 10-20), numbers with their
counter, Latin words to the English normalizer.
"""

from __future__ import annotations

import re

from ..en.normalize_en import ONES

SINO_DIGITS = ("영", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구")
PHONE_DIGITS = ("공",) + SINO_DIGITS[1:]
_SECTION_UNITS = ((1000, "천"), (100, "백"), (10, "십"), (1, ""))
_GROUP_UNITS = ("", "만", "억", "조", "경")
NATIVE_ONES = ("", "하나", "둘", "셋", "넷", "다섯", "여섯", "일곱", "여덟", "아홉")
NATIVE_ONES_COUNTER = ("", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉")
NATIVE_TENS = ("", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔")
MONTHS = {6: "유월", 10: "시월"}

# Counters read with native numbers (1-99). Matched as the start of the word after the number,
# longest first, together with SINO_COUNTERS (so 개월 is Sino, 개 native).
NATIVE_COUNTERS = ("개", "명", "시", "살", "번째", "마리", "잔", "시간", "사람", "권", "병",
                   "장", "그릇", "켤레", "송이", "달", "군데", "가지", "벌", "채", "곳", "척", "통",
                   "줄", "자루", "봉지", "그루", "알", "쌍", "판", "배")
# Sino-Korean counters and units that stand as a separate word after the number.
SINO_COUNTERS = ("분", "초", "원", "달러", "유로", "엔", "위안", "층", "번", "호", "개월", "주",
                 "주년", "회", "차", "등", "위", "세", "도", "퍼센트", "인분", "인", "킬로미터",
                 "킬로그램", "미터", "센티미터", "밀리미터", "그램", "리터", "밀리리터", "기가바이트",
                 "메가바이트", "평", "학년", "년간", "일간", "부", "편", "점")
JOINED = ("년", "월", "일")  # date units written together with the number
_COUNTERS = sorted([(c, "native") for c in NATIVE_COUNTERS] + [(c, "sino") for c in SINO_COUNTERS]
                   + [(c, "joined") for c in JOINED], key=lambda x: -len(x[0]))

_FULLWIDTH = {c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)}
_FULLWIDTH.update({0x3000: 0x20, ord("。"): ord("."), ord("、"): ord(","), ord("￦"): ord("₩")})
_DROP = "“”‘’\"「」『』《》〈〉【】〔〕()[]{}<>"
_PAUSE = re.compile(r"…+|—+|\.{3,}|·|ㆍ")
_SYMBOLS = {"℃": "도", "°C": "도", "°c": "도", "°": "도", "+": " 플러스 ", "&": " and ",
            "@": " at "}
UNITS = {"km": "킬로미터", "kg": "킬로그램", "cm": "센티미터", "mm": "밀리미터", "ml": "밀리리터",
         "m": "미터", "g": "그램", "l": "리터", "L": "리터", "GB": "기가바이트", "MB": "메가바이트"}
CURRENCY = {"₩": "원", "$": "달러", "€": "유로", "¥": "엔", "£": "파운드"}

_A = r"(?<![A-Za-z0-9])"  # not inside an ASCII word or number (Hangul neighbours are fine)
_Z = r"(?![A-Za-z0-9])"
_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
UNIT = re.compile(_A + r"(-?" + _NUM + r")\s?(" + "|".join(sorted(UNITS, key=len, reverse=True))
                  + r")(?![A-Za-z])")
PRODUCT_CODE = re.compile(_A + r"(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+" + _Z)
PHONE = re.compile(r"(?<![\d-])0\d{1,2}-\d{3,4}-\d{4}(?![\d-])|(?<![\d.,])0\d{2,}(?![\d.,])")
ISO_DATE = re.compile(r"(?<!\d)(\d{4})(?:-(\d{1,2})-(\d{1,2})|\.\s?(\d{1,2})\.\s?(\d{1,2})\.?)(?!\d)")
TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])")
MONEY = re.compile(r"([₩$€¥£])\s?(" + _NUM + ")")
PERCENT = re.compile(r"(-?" + _NUM + r")\s?%")
RANGE = re.compile(r"(?<![\d.])(\d+)\s?[~-]\s?(\d+)(?![\d.])(\s?)([가-힣]*)")
NUMBER = re.compile(r"(?<![A-Za-z0-9.])(-?)(" + _NUM + r")(?![\d])(\s?)([가-힣]*)")

_WORDS = re.compile(r"[가-힣]+|[a-z][a-z']*|[,.?!;:]")


def _section(n: int) -> str:
    """1..9999: 천, 백, 십 without a leading 일 (천이백, 백오, 십일)."""
    out = ""
    for div, unit in _SECTION_UNITS:
        d = n // div % 10
        if d:
            out += ("" if d == 1 and unit else SINO_DIGITS[d]) + unit
    return out


def sino(n: int) -> str:
    """Sino-Korean integer: 350 -> 삼백오십, 10000 -> 만, 100000000 -> 일억."""
    if n < 0:
        return "마이너스 " + sino(-n)
    if n == 0:
        return SINO_DIGITS[0]
    groups = []
    while n:
        groups.append(n % 10000)
        n //= 10000
    if len(groups) > len(_GROUP_UNITS):
        return digits("".join(str(g) for g in groups), SINO_DIGITS)
    out = ""
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if g:
            out += ("" if g == 1 and idx == 1 else _section(g)) + _GROUP_UNITS[idx]
    return out


def native(n: int, counter: bool = False) -> str:
    """Native Korean 1..99: 3 -> 셋 (세 before a counter), 20 -> 스물 (스무), 21 -> 스물하나 (스물한)."""
    tens, ones = divmod(n, 10)
    if counter and n == 20:
        return "스무"
    return NATIVE_TENS[tens] + (NATIVE_ONES_COUNTER if counter else NATIVE_ONES)[ones]


def digits(s: str, names=PHONE_DIGITS) -> str:
    return "".join(names[int(c)] for c in s if c.isdigit())


def decimal(s: str) -> str:
    """'1,250' -> 천이백오십, '3.14' -> 삼 점 일사, '-5' -> 마이너스 오."""
    s = s.replace(",", "")
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "." in s:
        a, b = s.split(".", 1)
        out = sino(int(a or 0)) + " 점 " + digits(b, SINO_DIGITS)
    else:
        out = sino(int(s))
    return ("마이너스 " if neg else "") + out


def counter_kind(word: str) -> str | None:
    """'native', 'sino' or 'joined' for the counter a word starts with, None for no counter."""
    for c, kind in _COUNTERS:
        if word.startswith(c):
            return kind
    return None


def read_number(num: str, suffix: str, space: str = "") -> str:
    """A number with the Hangul word that follows it (counter, particle or nothing)."""
    kind = counter_kind(suffix) if suffix else None
    plain = num.replace(",", "")
    if kind == "native" and plain.isdigit() and 1 <= int(plain) <= 99:
        n = int(plain)
        if n == 1 and suffix.startswith("번째"):
            return "첫 " + suffix
        return native(n, counter=True) + " " + suffix
    if kind == "joined" and suffix.startswith("월") and plain.isdigit() and int(plain) in MONTHS:
        return MONTHS[int(plain)] + suffix[1:]
    if kind in ("native", "sino"):
        return decimal(num) + " " + suffix
    return decimal(num) + space + suffix


def _code(m: re.Match) -> str:
    return " " + re.sub(r"[A-Z]|[0-9]",
                        lambda p: f" {p.group(0).lower() if p.group(0).isalpha() else ONES[int(p.group(0))]} ",
                        m.group(0)) + " "


def _date(m: re.Match) -> str:
    y = m.group(1)
    mo, d = (m.group(2), m.group(3)) if m.group(2) else (m.group(4), m.group(5))
    if not (1 <= int(mo) <= 12 and 1 <= int(d) <= 31):
        return m.group(0)
    return f" {sino(int(y))}년 {read_number(str(int(mo)), '월')} {sino(int(d))}일 "


def _time(m: re.Match) -> str:
    h, mi, sec = int(m.group(1)), int(m.group(2)), m.group(3)
    out = read_number(str(h), "시")
    if mi:
        out += f" {sino(mi)} 분"
    if sec and int(sec):
        out += f" {sino(int(sec))} 초"
    return f" {out} "


def _range(m: re.Match) -> str:
    a, b, space, suffix = m.groups()
    native_ok = counter_kind(suffix) == "native" and 1 <= int(a) <= 99 and 1 <= int(b) <= 99
    first = native(int(a)) if native_ok else sino(int(a))
    return f"{first}에서 {read_number(b, suffix, space)}"


def _latin(m: re.Match) -> str:
    from ..en.normalize_en import normalize_en

    return f" {normalize_en(m.group(0))} "


def normalize_ko(text: str) -> str:
    t = text.translate(_FULLWIDTH)
    t = _PAUSE.sub(",", t)
    for k, v in _SYMBOLS.items():
        t = t.replace(k, v)
    t = t.translate({ord(c): " " for c in _DROP})
    t = UNIT.sub(lambda m: f" {decimal(m.group(1))} {UNITS[m.group(2)]} ", t)
    t = PRODUCT_CODE.sub(_code, t)
    t = ISO_DATE.sub(_date, t)
    t = PHONE.sub(lambda m: " " + " ".join(digits(g) for g in m.group(0).split("-")) + " ", t)
    t = TIME.sub(_time, t)
    t = MONEY.sub(lambda m: f" {decimal(m.group(2))} {CURRENCY[m.group(1)]} ", t)
    t = PERCENT.sub(lambda m: f" {decimal(m.group(1))} 퍼센트 ", t)
    t = RANGE.sub(_range, t)
    t = NUMBER.sub(lambda m: read_number(m.group(1) + m.group(2), m.group(4), m.group(3)), t)
    t = re.sub(r"[A-Za-z](?:[A-Za-z'-]*[A-Za-z])?", _latin, t)
    out: list[str] = []
    for w in _WORDS.findall(t):
        if w in ",.?!;:":
            # A leading mark is kept (it may follow an English word of the previous run);
            # text.py drops marks that follow nothing.
            if not out or out[-1] not in ",.?!;:":
                out.append(w)
        else:
            out.append(w)
    return " ".join(out)


def is_hangul_word(word: str) -> bool:
    return bool(word) and all("가" <= ch <= "힣" for ch in word)
