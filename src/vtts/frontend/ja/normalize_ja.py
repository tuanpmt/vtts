"""Japanese text normalization for one Japanese run.

Output follows the other modules' convention: words and the punctuation tokens , . ? ! ; :
separated by single spaces. A word is either a run of Japanese characters (kanji and kana;
Japanese has no spaces, so a whole clause is one word and numbers become katakana inside it) or a
lower-case Latin word that the English module reads.

Numbers are read in Sino-Japanese and written in katakana as pronounced (ニセンニジューロク), with
the sound changes of 百 and 千 (サンビャク, ロッピャク, ハッピャク, サンゼン, ハッセン) and of the
counter that follows (COUNTERS: イッポン, サンボン, ロッポン; サンジュップン; ヨニン; ツイタチ ...).

Rules, in order: full-width forms to ASCII, Japanese punctuation to , . ! ? (quotes and brackets
dropped), pause marks, symbols, units, product codes (letters and digits in English), ISO dates,
times (9:30), money, percentages, ranges (3〜5), numbers with the counter that follows, Latin words
to the English normalizer.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..en.normalize_en import ONES

DIGITS = ("ゼロ", "イチ", "ニ", "サン", "ヨン", "ゴ", "ロク", "ナナ", "ハチ", "キュー")
THOUSANDS = {1: "セン", 3: "サンゼン", 8: "ハッセン"}
HUNDREDS = {1: "ヒャク", 3: "サンビャク", 6: "ロッピャク", 8: "ハッピャク"}
GROUPS = ("", "マン", "オク", "チョー")

J = r"一-鿿々〆ヶぁ-ゖァ-ヺー"  # Japanese characters (character class body)


@dataclass(frozen=True)
class Count:
    """How a counter is read after a number.

    base: the counter's reading; gem: its reading after a geminated number (イッ ロッ ハッ ジュッ
    ヒャッ), None when the number does not geminate before it; gem_digits: last digits whose
    number geminates (1, 6, 8; 10 and 100 for numbers ending in 十 and 百); nasal: its reading
    after サン, セン, マン and ナン (サンボン); last: reading of the last digit when it changes
    (4 -> ヨ in ヨニン); whole: readings of whole numbers (1 ヒトリ, 20 ハタチ)."""
    base: str
    gem: str | None = None
    gem_digits: tuple[int, ...] = (1, 6, 8, 10, 100)
    nasal: str | None = None
    nasal_after: tuple[str, ...] = ("サン", "セン", "マン")
    last: dict[int, str] | None = None
    whole: dict[int, str] | None = None


_H = (1, 6, 8, 10, 100)
_S = (1, 8, 10, 100)  # counters starting with s/t/k-sounds where ロク stays (ロクサイ)
DAYS = {1: "ツイタチ", 2: "フツカ", 3: "ミッカ", 4: "ヨッカ", 5: "イツカ", 6: "ムイカ", 7: "ナノカ",
        8: "ヨーカ", 9: "ココノカ", 10: "トーカ", 14: "ジューヨッカ", 20: "ハツカ",
        24: "ニジューヨッカ"}
NATIVE = {1: "ヒトツ", 2: "フタツ", 3: "ミッツ", 4: "ヨッツ", 5: "イツツ", 6: "ムッツ", 7: "ナナツ",
          8: "ヤッツ", 9: "ココノツ", 10: "トー"}
COUNTERS: dict[str, Count] = {
    "本": Count("ホン", "ポン", _H, "ボン"),
    "匹": Count("ヒキ", "ピキ", _H, "ビキ"),
    "杯": Count("ハイ", "パイ", _H, "バイ"),
    "分の": Count("ブンノ"),  # fractions: 3分の1 サンブンノイチ
    "分": Count("フン", "プン", _H, "プン", ("サン", "ヨン", "セン", "マン", "ナン")),
    "個": Count("コ", "コ", _H),
    "回": Count("カイ", "カイ", _H),
    "階": Count("カイ", "カイ", _H, "ガイ", ("サン",)),
    "件": Count("ケン", "ケン", _H),
    "軒": Count("ケン", "ケン", _H, "ゲン", ("サン",)),
    "冊": Count("サツ", "サツ", _S),
    "歳": Count("サイ", "サイ", _S, whole={20: "ハタチ"}),
    "才": Count("サイ", "サイ", _S, whole={20: "ハタチ"}),
    "点": Count("テン", "テン", _S),
    "頭": Count("トー", "トー", _S),
    "通": Count("ツー", "ツー", _S),
    "週間": Count("シューカン", "シューカン", _S),
    "週": Count("シュー", "シュー", _S),
    "か月": Count("カゲツ", "カゲツ", _H),
    "ヶ月": Count("カゲツ", "カゲツ", _H),
    "カ月": Count("カゲツ", "カゲツ", _H),
    "ケ月": Count("カゲツ", "カゲツ", _H),
    "カ国": Count("カコク", "カコク", _H),
    "ヶ国": Count("カコク", "カコク", _H),
    "か国": Count("カコク", "カコク", _H),
    "円": Count("エン", last={4: "ヨ"}),
    "年": Count("ネン", last={4: "ヨ"}),
    "人": Count("ニン", last={4: "ヨ", 7: "シチ"}, whole={1: "ヒトリ", 2: "フタリ"}),
    "時間": Count("ジカン", last={4: "ヨ", 7: "シチ", 9: "ク"}),
    "時": Count("ジ", last={4: "ヨ", 7: "シチ", 9: "ク"}),
    "月": Count("ガツ", whole={4: "シガツ", 7: "シチガツ", 9: "クガツ"}),
    "日間": Count("ニチカン", whole={k: v + "カン" for k, v in DAYS.items() if k != 1}),
    "日": Count("ニチ", whole=DAYS),
    "つ": Count("", whole=NATIVE),
    "秒": Count("ビョー"),
    "度": Count("ド"),
    "番目": Count("バンメ"),
    "番": Count("バン"),
    "枚": Count("マイ"),
    "台": Count("ダイ"),
    "名": Count("メー"),
    "倍": Count("バイ"),
    "号": Count("ゴー"),
    "位": Count("イ"),
    "割": Count("ワリ"),
}
_COUNTER_RE = "|".join(sorted(map(re.escape, COUNTERS), key=len, reverse=True))

_FULLWIDTH = {c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)}
_FULLWIDTH.update({0x3000: 0x20, ord("。"): ord("."), ord("、"): ord(","), ord("｡"): ord("."),
                   ord("､"): ord(","), ord("￥"): ord("¥"), ord("〜"): ord("~")})
_DROP = "“”‘’\"「」『』《》〈〉【】〔〕()[]{}<>・･"
_PAUSE = re.compile(r"…+|‥+|—+|―+|\.{3,}")
_SYMBOLS = {"℃": "ド", "°C": "ド", "°c": "ド", "°": "ド", "+": "プラス", "&": " and ", "@": " at ",
            "×": "カケル", "÷": "ワル", "=": "イコール"}
UNITS = {"km": "キロメートル", "kg": "キログラム", "cm": "センチメートル", "mm": "ミリメートル",
         "ml": "ミリリットル", "mL": "ミリリットル", "m": "メートル", "g": "グラム", "l": "リットル",
         "L": "リットル", "GB": "ギガバイト", "MB": "メガバイト", "km/h": "キロメートルジソク"}
CURRENCY = {"¥": "エン", "$": "ドル", "€": "ユーロ", "£": "ポンド"}

_A = r"(?<![A-Za-z0-9])"  # not inside an ASCII word or number (Japanese neighbours are fine)
_Z = r"(?![A-Za-z0-9])"
_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
UNIT = re.compile(_A + r"(-?" + _NUM + r")\s?(" + "|".join(
    sorted(map(re.escape, UNITS), key=len, reverse=True)) + r")(?![A-Za-z])")
PHONE = re.compile(r"(?<![\d-])0\d{1,4}-\d{1,4}-\d{3,4}(?![\d-])")
# 3万, 1億2000万, 1.5万: digits with the kanji units 万 億 兆 become one number, marked so that it
# is read as a number (not digit by digit) even with 5 or more digits
BIG_UNITS = (("万", 10**4), ("億", 10**8), ("兆", 10**12))
MARK = "\u2060"  # word joiner: "read as a number"
BIG = {u: re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)" + u + MARK
                     + rf"?(\d{{1,{len(str(v // 10))}}})?(?![\d.])") for u, v in BIG_UNITS}
PRODUCT_CODE = re.compile(_A + r"(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+" + _Z)
ISO_DATE = re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?![\d])")
TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])")
MONEY = re.compile(r"([¥$€£])\s?(" + MARK + "?)(" + _NUM + ")")
PERCENT = re.compile(r"(" + MARK + "?)(-?" + _NUM + r")\s?%")
RANGE = re.compile(r"(?<![\d.])(" + MARK + "?)(" + _NUM + r")\s?[~〜-]\s?(?=" + MARK + r"?\d)")
NUMBER = re.compile(r"(?<![A-Za-z0-9.])(-?)(" + MARK + "?)(" + _NUM + r")(?![\d])\s?(" + _COUNTER_RE + ")?")

_WORDS = re.compile("[" + J + "]+|[a-z][a-z']*|[,.?!;:]")


def _section(n: int, unit_after: bool = False) -> str:
    """1..9999. unit_after: a group unit follows (1000 is イッセン in イッセンマン)."""
    out = ""
    th, h, t, o = n // 1000, n // 100 % 10, n // 10 % 10, n % 10
    if th:
        out += "イッセン" if th == 1 and unit_after else THOUSANDS.get(th, DIGITS[th] + "セン")
    if h:
        out += HUNDREDS.get(h, DIGITS[h] + "ヒャク")
    if t:
        out += ("" if t == 1 else DIGITS[t]) + "ジュー"
    if o:
        out += DIGITS[o]
    return out


def cardinal(n: int) -> str:
    """Sino-Japanese integer in katakana: 2026 -> ニセンニジューロク, 10000 -> イチマン."""
    if n < 0:
        return "マイナス" + cardinal(-n)
    if n == 0:
        return DIGITS[0]
    groups = []
    while n:
        groups.append(n % 10000)
        n //= 10000
    if len(groups) > len(GROUPS):
        return digits("".join(f"{g:04d}" for g in reversed(groups)).lstrip("0"))
    out = ""
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if not g:
            continue
        sec = _section(g, unit_after=idx > 0)
        if idx == 3 and g in (1, 8, 10):  # イッチョー, ハッチョー, ジュッチョー
            sec = {1: "イッ", 8: "ハッ", 10: "ジュッ"}[g]
        out += sec + GROUPS[idx]
    return out


def digits(s: str) -> str:
    return "".join(DIGITS[int(c)] for c in s if c.isdigit())


def decimal(s: str) -> str:
    """'1,250' -> センニヒャクゴジュー, '3.14' -> サンテンイチヨン, '-5' -> マイナスゴ."""
    s = s.replace(",", "")
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "." in s:
        a, b = s.split(".", 1)
        out = cardinal(int(a or 0)) + "テン" + digits(b)
    else:
        out = cardinal(int(s))
    return ("マイナス" if neg else "") + out


def _geminate(reading: str) -> str | None:
    for end, gem in (("イチ", "イッ"), ("ロク", "ロッ"), ("ハチ", "ハッ"), ("ジュー", "ジュッ"),
                     ("ヒャク", "ヒャッ")):
        if reading.endswith(end):
            return reading[: -len(end)] + gem
    return None


def _ending(n: int) -> int:
    """Last digit; for numbers ending in 0, 10 (…十) or 100 (…百), else 0."""
    if n % 10:
        return n % 10
    if n % 100:
        return 10
    if n % 1000:
        return 100
    return 0


def with_counter(num: str, counter: str, after_month: bool = False) -> str:
    """A number (digits, maybe with commas, sign or decimals) and the counter after it."""
    c = COUNTERS[counter]
    plain = num.replace(",", "")
    if not plain.isdigit():
        return decimal(num) + (c.base or counter)
    n = int(plain)
    if counter == "日" and n == 1 and not after_month:
        return "イチニチ"  # 1日 is ツイタチ only as a date (11月1日)
    if c.whole and n in c.whole:
        return c.whole[n]
    if counter == "つ":
        return cardinal(n)  # 11 and above take no つ
    last = n % 10
    if c.last and last in c.last:
        return (cardinal(n - last) if n > last else "") + c.last[last] + c.base
    if counter in ("日", "日間") and n % 10 == 4 and n > 10:  # 14日, 24日
        return cardinal(n - 4) + "ヨッカ" + ("カン" if counter == "日間" else "")
    reading = cardinal(n)
    if c.gem is not None and _ending(n) in c.gem_digits:
        gem = _geminate(reading)
        if gem is not None:
            return gem + c.gem
    if c.nasal is not None and reading.endswith(c.nasal_after):
        return reading + c.nasal
    return reading + c.base


def _big(m: re.Match, value: int) -> str:
    n = float(m.group(1)) * value + int(m.group(2) or 0)
    return MARK + (str(int(n)) if n == int(n) else str(n))


def _number(m: re.Match) -> str:
    sign, marked, num, counter = m.group(1), m.group(2), m.group(3), m.group(4)
    prefix = "マイナス" if sign else ""
    plain = num.replace(",", "")
    if counter is None:
        if plain.isdigit() and not marked and (len(plain) >= 5 and "," not in num or
                                (len(plain) > 1 and plain.startswith("0"))):
            return prefix + digits(plain)  # long digit strings and codes: one digit at a time
        return prefix + decimal(num)
    after_month = m.string[:m.start()].rstrip().endswith(("月", "ガツ"))
    return prefix + with_counter(num, counter, after_month)


def _code(m: re.Match) -> str:
    return " " + re.sub(r"[A-Z]|[0-9]",
                        lambda p: f" {p.group(0).lower() if p.group(0).isalpha() else ONES[int(p.group(0))]} ",
                        m.group(0)) + " "


def _iso_date(m: re.Match) -> str:
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return m.group(0)
    return with_counter(str(y), "年") + with_counter(str(mo), "月") + \
        with_counter(str(d), "日", after_month=True)


def _time(m: re.Match) -> str:
    h, mi, sec = int(m.group(1)), int(m.group(2)), m.group(3)
    out = with_counter(str(h), "時")
    if mi:
        out += with_counter(str(mi), "分")
    if sec and int(sec):
        out += with_counter(str(int(sec)), "秒")
    return out


def _latin(m: re.Match) -> str:
    from ..en.normalize_en import normalize_en

    return f" {normalize_en(m.group(0))} "


def normalize_ja(text: str) -> str:
    t = unicodedata.normalize("NFKC", text.replace("〜", "~").replace("～", "~"))
    t = t.translate(_FULLWIDTH)
    t = _PAUSE.sub(",", t)
    for k, v in _SYMBOLS.items():
        t = t.replace(k, v)
    t = t.translate({ord(c): " " for c in _DROP})
    # no spaces inside Japanese text or between a number and the Japanese word after it
    t = re.sub(rf"(?<=[{J}\d])\s+(?=[{J}])|(?<=[{J}])\s+(?=\d)", "", t)
    for unit, value in BIG_UNITS:
        t = BIG[unit].sub(lambda m, v=value: _big(m, v), t)
    t = UNIT.sub(lambda m: decimal(m.group(1)) + UNITS[m.group(2)], t)
    t = PRODUCT_CODE.sub(_code, t)
    t = PHONE.sub(lambda m: "ノ".join(digits(g) for g in m.group(0).split("-")), t)
    t = ISO_DATE.sub(_iso_date, t)
    t = TIME.sub(_time, t)
    t = MONEY.sub(lambda m: decimal(m.group(3)) + CURRENCY[m.group(1)], t)
    t = PERCENT.sub(lambda m: decimal(m.group(2)) + "パーセント", t)
    t = RANGE.sub(lambda m: decimal(m.group(2)) + "カラ", t)
    t = NUMBER.sub(_number, t)
    t = re.sub(r"[A-Za-z](?:[A-Za-z'-]*[A-Za-z])?", _latin, t)
    t = t.replace(MARK, "")
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


def is_ja_word(word: str) -> bool:
    from .g2p_ja import is_ja_char

    return bool(word) and all(is_ja_char(ch) for ch in word)
