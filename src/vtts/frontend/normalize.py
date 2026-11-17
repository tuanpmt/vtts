"""Raw Vietnamese text -> lowercase syllables and punctuation separated by single spaces.

Every word in the output parses with `parse_syllable`, so the result can always be
fed to `g2p`. Order: NFC, punctuation cleanup, abbreviations, emails/URLs, dates,
times, percent, currency, units, numbers, then per-word handling (keep valid
syllables, replace loanwords, spell everything else letter by letter).
"""

from __future__ import annotations

import re
import unicodedata

from .lexicon import ABBREVIATIONS, CURRENCIES, LETTER_NAMES, LOANWORDS, SYMBOLS, UNITS
from .numbers import read_digits, read_int, read_number_token
from .phoneme_set import PUNCTUATION
from .syllable import canonical_spelling, parse_syllable

_NUM = r"-?\d+(?:[.,]\d+)*"
_PUNCT_MAP = {"…": ".", "–": ",", "—": ","}
_DROP = "“”\"‘’'()[]{}«»"


def _sub(pattern: str, repl, text: str, flags: int = 0) -> str:
    return re.sub(pattern, lambda m: f" {repl(m)} ", text, flags=flags)


def _read_word_like(part: str) -> str:
    """Read one alphanumeric piece of an email/URL: syllable if valid, else spelled."""
    out = []
    for piece in re.findall(r"[^\W\d_]+|\d+", part):
        if piece.isdecimal():
            out.append(read_number_token(piece))
        elif any(ch.isalpha() for ch in piece):
            out.append(_word("".join(ch for ch in piece if ch.isalpha())))
    return " ".join(out)


def _read_address(m: re.Match) -> str:
    s = m.group(0)
    s = re.sub(r"^https?://", "", s)
    words = []
    for tok in re.split(r"([@./:?=&_-])", s):
        if not tok:
            continue
        sep = {"@": "a còng", ".": "chấm", "/": "gạch chéo", ":": "hai chấm", "-": "gạch ngang",
               "_": "gạch dưới", "?": "", "=": "bằng", "&": "và"}
        words.append(sep[tok] if tok in sep else _read_word_like(tok))
    return " ".join(w for w in words if w)


_NGAY = r"(?P<pre>(?<!\w)[nN]gày\s+)?"


def _read_date(pre: str | None, d: int, mo: int, y: int | None) -> str:
    """Read a day/month(/year); a preceding "ngày" in the text is absorbed, not repeated."""
    prefix = (pre or "").strip()
    if 1 <= d <= 31 and 1 <= mo <= 12:
        year = f" năm {read_int(y)}" if y is not None else ""
        return f"ngày {read_int(d)} tháng {read_int(mo)}{year}"
    tail = f" {read_int(y)}" if y is not None else ""
    return f"{prefix} {read_int(d)} trên {read_int(mo)}{tail}".strip()


def _date3(m: re.Match) -> str:
    return _read_date(m.group("pre"), int(m.group("d")), int(m.group("m")), int(m.group("y")))


def _date2(m: re.Match) -> str:
    return _read_date(m.group("pre"), int(m.group("d")), int(m.group("m")), None)


def _time(m: re.Match) -> str:
    h, mi = int(m.group(1)), int(m.group(2))
    if h <= 24 and mi < 60:
        return f"{read_int(h)} giờ {read_int(mi)} phút"
    return f"{read_int(h)} {read_int(mi)}"


# Product codes: upper-case ASCII letters and digits with at least one of each, standing alone
# (ESP32, S3, RTX3060, MP3). Their digits are read one by one ("ESP32" -> "ESP ba hai"); the
# letters are spelled later as usual. See docs/frontend/pronunciation-rules.md.
PRODUCT_CODE = r"(?<!\w)(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+(?!\w)"


def _read_code(m: re.Match) -> str:
    return re.sub(r"[0-9]+", lambda d: f" {read_digits(d.group(0))} ", m.group(0))


def _spell(word: str) -> str:
    names = []
    for ch in word:
        base = ch if ch in LETTER_NAMES else unicodedata.normalize("NFD", ch)[0]
        if base in LETTER_NAMES:
            names.append(LETTER_NAMES[base])
    return " ".join(names)


def _word(word: str, spelled: list[str] | None = None) -> str:
    low = unicodedata.normalize("NFC", word.lower())
    if parse_syllable(low) is not None:
        return canonical_spelling(low)
    if low in LOANWORDS:
        return LOANWORDS[low]
    if spelled is not None:
        spelled.append(low)
    return _spell(low)


def _expand(text: str) -> str:
    for src, dst in _PUNCT_MAP.items():
        text = text.replace(src, dst)
    text = text.translate({ord(c): " " for c in _DROP})

    for abbr in sorted(ABBREVIATIONS, key=len, reverse=True):
        tail = "" if abbr.endswith(".") else r"(?!\w)"
        text = re.sub(rf"(?<!\w){re.escape(abbr)}{tail}", f" {ABBREVIATIONS[abbr]} ", text)

    text = _sub(PRODUCT_CODE, _read_code, text)
    text = _sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", _read_address, text)
    text = _sub(r"(?:https?://|www\.)[^\s]+", _read_address, text)
    text = _sub(r"(?<![\d.])0\d{2,3}[. ]?\d{3}[. ]?\d{3,4}(?!\d|\.\d)",
                lambda m: read_digits(re.sub(r"\D", "", m.group(0))), text)
    text = _sub(rf"{_NGAY}(?<!\d)(?P<y>\d{{4}})-(?P<m>\d{{2}})-(?P<d>\d{{2}})(?!\d)", _date3, text)
    text = _sub(rf"{_NGAY}(?<!\d)(?P<d>\d{{1,2}})/(?P<m>\d{{1,2}})/(?P<y>\d{{4}})(?!\d)", _date3, text)
    text = _sub(rf"{_NGAY}(?<![\d/])(?P<d>\d{{1,2}})/(?P<m>\d{{1,2}})(?![\d/])", _date2, text)
    text = _sub(r"(?<!\d)(\d{1,2})[:h](\d{2})(?!\d)", _time, text)
    text = _sub(r"(?<!\d)(\d{1,2})h(?!\w)", lambda m: f"{read_int(int(m.group(1)))} giờ", text)
    text = _sub(rf"(?<![\w.,])({_NUM})\s?%",
                lambda m: f"{read_number_token(m.group(1))} phần trăm", text)
    text = _sub(rf"\$\s?({_NUM})", lambda m: f"{read_number_token(m.group(1))} đô la", text)
    cur = "|".join(sorted((re.escape(c) for c in CURRENCIES), key=len, reverse=True))
    text = _sub(rf"(?<![\w.,])({_NUM})\s?({cur})(?!\w)",
                lambda m: f"{read_number_token(m.group(1))} {CURRENCIES[m.group(2).lower()]}",
                text, flags=re.IGNORECASE)
    text = _sub(rf"(?<![\w.,])({_NUM})\s?\$",
                lambda m: f"{read_number_token(m.group(1))} đô la", text)
    units = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
    text = _sub(rf"(?<![\w.,])({_NUM})\s?({units})(?!\w)",
                lambda m: f"{read_number_token(m.group(1))} {UNITS[m.group(2)]}", text)
    # split letter/digit runs: iPhone15 -> iPhone 15, A4 -> A 4
    text = re.sub(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])", " ", text)
    text = _sub(rf"(?<![\w.,])({_NUM})(?![\w])", lambda m: read_number_token(m.group(1)), text)
    for sym, name in SYMBOLS.items():
        text = text.replace(sym, f" {name} ")
    return text


def spelled_words(text: str) -> list[str]:
    """Words that normalize() would read letter by letter (unknown loanwords, abbreviations)."""
    spelled: list[str] = []
    _normalize(text, spelled)
    return spelled


def normalize(text: str) -> str:
    return _normalize(text, None)


def _normalize(text: str, spelled: list[str] | None) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _expand(text)
    for p in PUNCTUATION:
        text = text.replace(p, f" {p} ")
    out: list[str] = []
    for raw in text.split():
        if raw in PUNCTUATION:
            if out and out[-1] not in PUNCTUATION:
                out.append(raw)
            continue
        for piece in re.findall(r"[^\W\d_]+|\d+", raw):
            if piece.isdecimal():
                out.extend(read_number_token(piece).split())
                continue
            letters = "".join(ch for ch in piece if ch.isalpha())
            if letters:
                out.extend(_word(letters, spelled).split())
    return " ".join(out)
