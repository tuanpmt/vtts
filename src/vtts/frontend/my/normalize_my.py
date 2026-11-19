"""Burmese text normalization for one Burmese run (engine: frontend/nospace_norm.py).

Zawgyi text is converted to Unicode first, and Unicode text is put in canonical order
(my/zawgyi.to_unicode). Burmese digits ၀-၉ (and the Shan digits U+1090-U+1099 left after that
step) are read like ASCII digits; the letter ဝ written for
zero after a digit (၁၉၅၄ဝဝဝ) is a digit. ။ ends a sentence (lang.SENTENCE_END) and is read ".", ၊
is ",". Spaces between Burmese runs are word boundaries, not pauses (Burmese writers put spaces
between words and phrases alike).

Numbers: တစ် နှစ် သုံး ... ကိုး with ဆယ် ရာ ထောင် သောင်း သိန်း သန်း; ဆယ် ရာ ထောင် take the
creaky tone before more digits (ဆယ့် ရာ့ ထောင့်: 2026 = နှစ်ထောင့်နှစ်ဆယ့်ခြောက်); millions
beyond nine with သန်း (25,000,000 = နှစ်ဆယ့်ငါးသန်း); decimals with ဒသမ and the digits one by
one; အနုတ် for minus; dates "2026 ခုနှစ် နိုဝင်ဘာလ 19 ရက်"; times "14 နာရီ 30 မိနစ်"; money,
percent (ရာခိုင်နှုန်း), units (Ks = ကျပ်) after the number; ranges with မှ. A space
follows ဒသမ and the month and year of a date, so their last syllable ends a run (read a̰,
not the reduced ə, g2p_my).
"""

from __future__ import annotations

from ..nospace_norm import Normalizer, Spec
from .zawgyi import to_unicode

DIGITS = ("သုည", "တစ်", "နှစ်", "သုံး", "လေး", "ငါး", "ခြောက်", "ခုနစ်", "ရှစ်", "ကိုး")
PLACES = ((1_000_000, "သန်း"), (100_000, "သိန်း"), (10_000, "သောင်း"), (1000, "ထောင်"),
          (100, "ရာ"), (10, "ဆယ်"))
CREAKY = {"ထောင်": "ထောင့်", "ရာ": "ရာ့", "ဆယ်": "ဆယ့်"}
MINUS = "အနုတ်"
MONTHS = ("", "ဇန်နဝါရီ", "ဖေဖော်ဝါရီ", "မတ်", "ဧပြီ", "မေ", "ဇွန်", "ဇူလိုင်", "ဩဂုတ်",
          "စက်တင်ဘာ", "အောက်တိုဘာ", "နိုဝင်ဘာ", "ဒီဇင်ဘာ")
UNITS = {"km/h": "ကီလိုမီတာနှုန်း", "km": "ကီလိုမီတာ", "kg": "ကီလိုဂရမ်", "cm": "စင်တီမီတာ",
         "mm": "မီလီမီတာ", "°C": "ဒီဂရီစင်တီဂရိတ်", "℃": "ဒီဂရီစင်တီဂရိတ်", "°": "ဒီဂရီ",
         "GB": "ဂစ်ဂါဘိုက်", "MB": "မဂ္ဂါဘိုက်", "MMK": "ကျပ်", "Ks": "ကျပ်", "m": "မီတာ",
         "g": "ဂရမ်", "ml": "မီလီလီတာ", "l": "လီတာ"}
CURRENCY = {"$": "ဒေါ်လာ", "€": "ယူရို", "£": "ပေါင်", "¥": "ယန်း", "฿": "ဘတ်"}
SYMBOLS = {"+": "အပေါင်း", "=": "ညီမျှ", "&": " and ", "@": " at ", "×": "အမြှောက်"}
PUNCT = {"။": ".", "၊": ","}
LETTERS = "က-ဿ၌-၏"  # letters and signs, ၌ ၍ ၎ ၏ (not digits, ၊ ။)
_ZW = {0x200B: None, 0x200C: None, 0x200D: None, 0x2060: None, 0xFEFF: None}


def _below_million(n: int) -> str:
    out = ""
    for place, word in PLACES[1:]:
        d, n = divmod(n, place)
        if d:
            out += DIGITS[d] + (CREAKY.get(word, word) if n else word)
    return out + (DIGITS[n] if n else "")


def cardinal(n: int) -> str:
    """Integer in Burmese: 21 -> နှစ်ဆယ့်တစ်, 2026 -> နှစ်ထောင့်နှစ်ဆယ့်ခြောက်, 3_000_000 -> သုံးသန်း."""
    if n < 0:
        return MINUS + cardinal(-n)
    if n == 0:
        return DIGITS[0]
    high, low = divmod(n, 1_000_000)
    return (cardinal(high) + "သန်း" if high else "") + (_below_million(low) if low else "")


def _digits(s: str) -> str:
    return "".join(DIGITS[int(c)] for c in s)


def _date(d: int, m: int, y: str) -> str:
    year = cardinal(int(y)) if len(y) == 4 else _digits(y)
    return f"{year}ခုနှစ် {MONTHS[m]}လ {cardinal(d)}ရက်"


def _time(h: int, m: int, s: int) -> str:
    out = cardinal(h) + "နာရီ"
    if m:
        out += cardinal(m) + "မိနစ်"
    if s:
        out += cardinal(s) + "စက္ကန့်"
    return out


def _zero_wa(t: str) -> str:
    """ဝ after a digit is the digit zero (၁၉၅၄ဝဝဝ), unless a sign or a final follows it (၅ဝန်)."""
    out = list(t)
    n = len(out)
    for k, ch in enumerate(out):
        if (ch == "ဝ" and k and ("0" <= out[k - 1] <= "9" or "၀" <= out[k - 1] <= "၉")
                and not (k + 1 < n and "ါ" <= out[k + 1] <= "ှ")
                and not (k + 2 < n and "က" <= out[k + 1] <= "အ" and out[k + 2] == "်")):
            out[k] = "၀"
    return "".join(out)


# Myanmar Shan digits U+1090..U+1099 left after the conversion (Zawgyi uses these code points for
# other glyphs) are digits too.
_SHAN_DIGITS = {0x1090 + k: ord("0") + k for k in range(10)}


def _pre(t: str) -> str:
    return _zero_wa(to_unicode(t.translate(_ZW)).translate(_SHAN_DIGITS))


SPEC = Spec(lang="my", letters=LETTERS, digit0=0x1040, cardinal=cardinal, digit_words=DIGITS,
            point="ဒသမ ", minus=MINUS, to="မှ", percent="ရာခိုင်နှုန်း", currency=CURRENCY,
            units=UNITS, date=_date, time=_time, symbols=SYMBOLS, punct=PUNCT, pre=_pre)
normalize_my = Normalizer(SPEC)


def is_burmese_word(word: str) -> bool:
    """A normalized word of Burmese letters (U+1000..U+103F, ၌ ၍ ၎ ၏)."""
    return bool(word) and all("က" <= ch <= "ဿ" or "၌" <= ch <= "၏" for ch in word)
