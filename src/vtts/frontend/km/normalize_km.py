"""Khmer text normalization for one Khmer run (engine: frontend/nospace_norm.py).

Khmer puts spaces between phrases, not between words; a space between two runs of Khmer letters
is read as a pause (","), like Thai. Khmer digits ០-៩ are read like ASCII digits. The full stop
។ and ៕ end a sentence (lang.SENTENCE_END) and are read as ".", ៖ as ":". Zero-width spaces
(word separators some writers insert) are dropped. ៗ (lek too) is joined to the word before it
(g2p_km repeats that word).

Numbers: មួយ .. ប្រាំបួន (5 + n for 6-9), ដប់ ម្ភៃ សាមសិប ... កៅសិប, រយ ពាន់ ម៉ឺន សែន, លាន for
millions (2026 = ពីរពាន់ម្ភៃប្រាំមួយ, 15000 = មួយម៉ឺនប្រាំពាន់); decimals with ចុច and the
digits one by one; ដក for minus; dates "ថ្ងៃទី 19 ខែវិច្ឆិកា ឆ្នាំ 2026"; times "ម៉ោង 14 30 នាទី";
riel ៛ and other currencies before or after the number; ភាគរយ for %; units after a number;
ranges with ដល់; dotted abbreviations ព.ស. គ.ស. គ.ម. ល.រ.
"""

from __future__ import annotations

from ..nospace_norm import Normalizer, Spec

DIGITS = ("សូន្យ", "មួយ", "ពីរ", "បី", "បួន", "ប្រាំ", "ប្រាំមួយ", "ប្រាំពីរ", "ប្រាំបី", "ប្រាំបួន")
TENS = ("", "ដប់", "ម្ភៃ", "សាមសិប", "សែសិប", "ហាសិប", "ហុកសិប", "ចិតសិប", "ប៉ែតសិប", "កៅសិប")
PLACES = ((100000, "សែន"), (10000, "ម៉ឺន"), (1000, "ពាន់"), (100, "រយ"))
MILLION = "លាន"
MINUS = "ដក"
MONTHS = ("", "មករា", "កុម្ភៈ", "មីនា", "មេសា", "ឧសភា", "មិថុនា", "កក្កដា", "សីហា", "កញ្ញា",
          "តុលា", "វិច្ឆិកា", "ធ្នូ")
UNITS = {"km/h": "គីឡូម៉ែត្រក្នុងមួយម៉ោង", "km": "គីឡូម៉ែត្រ", "kg": "គីឡូក្រាម",
         "cm": "សង់ទីម៉ែត្រ", "mm": "មីលីម៉ែត្រ", "°C": "អង្សាសេ", "℃": "អង្សាសេ", "°": "ដឺក្រេ",
         "GB": "ជីហ្គាបៃ", "MB": "មេហ្គាបៃ", "m": "ម៉ែត្រ", "g": "ក្រាម", "ml": "មីលីលីត្រ",
         "l": "លីត្រ"}
CURRENCY = {"៛": "រៀល", "$": "ដុល្លារ", "€": "អឺរ៉ូ", "£": "ផោន", "¥": "យ៉េន", "฿": "បាត"}
ABBREVIATIONS = {"ព.ស.": "ពុទ្ធសករាជ", "គ.ស.": "គ្រិស្តសករាជ", "គ.ម.": "គីឡូម៉ែត្រ",
                 "ល.រ.": "លេខរៀង"}
SYMBOLS = {"+": "បូក", "=": "ស្មើ", "&": " and ", "@": " at ", "×": "គុណ"}
PUNCT = {"។": ".", "៕": ".", "៚": ".", "៖": ":"}
LETTERS = "ក-៓ៗ៝"  # letters and signs, ៗ, ៝ (not digits, ។ ៕ ៖ ៘-៛)
_ZW = {0x200B: None, 0x200C: None, 0x200D: None, 0x2060: None, 0xFEFF: None}


def _below_million(n: int) -> str:
    out = ""
    for place, word in PLACES:
        d, n = divmod(n, place)
        if d:
            out += DIGITS[d] + word
    t, u = divmod(n, 10)
    return out + TENS[t] + (DIGITS[u] if u else "")


def cardinal(n: int) -> str:
    """Integer in Khmer: 21 -> ម្ភៃមួយ, 2026 -> ពីរពាន់ម្ភៃប្រាំមួយ, 3_000_000 -> បីលាន."""
    if n < 0:
        return MINUS + cardinal(-n)
    if n == 0:
        return DIGITS[0]
    high, low = divmod(n, 1_000_000)
    return (cardinal(high) + MILLION if high else "") + (_below_million(low) if low else "")


def _digits(s: str) -> str:
    return "".join(DIGITS[int(c)] for c in s)


def _date(d: int, m: int, y: str) -> str:
    return f"ថ្ងៃទី{cardinal(d)}ខែ{MONTHS[m]}ឆ្នាំ" + (cardinal(int(y)) if len(y) == 4 else _digits(y))


def _time(h: int, m: int, s: int) -> str:
    out = "ម៉ោង" + cardinal(h)
    if m:
        out += cardinal(m) + "នាទី"
    if s:
        out += cardinal(s) + "វិនាទី"
    return out


SPEC = Spec(lang="km", letters=LETTERS, digit0=0x17E0, cardinal=cardinal, digit_words=DIGITS,
            point="ចុច", minus=MINUS, to="ដល់", percent="ភាគរយ", currency=CURRENCY, units=UNITS,
            date=_date, time=_time, symbols=SYMBOLS, abbreviations=ABBREVIATIONS, punct=PUNCT,
            repeat="ៗ", space_pause=True, pre=lambda t: t.translate(_ZW), dedupe=("ថ្ងៃទី", "ម៉ោង"))
normalize_km = Normalizer(SPEC)


def is_khmer_word(word: str) -> bool:
    """A normalized word of Khmer letters (U+1780..U+17D3, ៗ, ៝)."""
    return bool(word) and all("ក" <= ch <= "៓" or ch in "ៗ៝" for ch in word)
