"""Turkish text normalization for one Turkish run.

Output follows the other modules' convention: lower-case words (Turkish lower case: I -> ı,
İ -> i) and the punctuation tokens , . ? ! ; : separated by single spaces. An apostrophe inside a
word is kept (İstanbul'da: g2p_tr reads the suffix without stress).

Rules, in order: abbreviations (Dr., Prof., vb., vs.), quotes and brackets dropped, dates
(19.11.2026, 19/11/2026, 2026-11-19), times (14:30, saat 14.30), phone numbers (digit by digit),
money (50 TL, ₺50, 12,50 TL -> on iki lira elli kuruş, $5, 20 €), percentages (%25 and 25%),
units after a number (5 km, 25 °C, 120 km/h -> saatte yüz yirmi kilometre), ordinals (5. sınıf,
1'inci), ranges (10-20), pause marks (… —), product codes (ESP32: letters by Turkish name, digits
one by one), numbers (1.250,5; a suffix after an apostrophe is joined to the last word:
2026'da -> iki bin yirmi altıda, 4'üncü -> dördüncü), symbols, acronyms (spelled: THY -> te ha ye;
some read as words: NATO).
"""

from __future__ import annotations

import re

from ..latin_norm import (
    DROP,
    NUM,
    PAUSE,
    PRODUCT_CODE,
    acronyms,
    apply_abbreviations,
    digits,
    finish,
    parse_number,
    phone_digits,
    read_number,
    spell,
)
from .g2p_tr import SUFFIX_MARK, tr_lower

ONES = ("sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz")
TENS = ("", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan")
DIGITS = ONES
MONTHS = ("", "ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül",
          "ekim", "kasım", "aralık")
LETTERS = {"a": "a", "b": "be", "c": "ce", "ç": "çe", "d": "de", "e": "e", "f": "fe", "g": "ge",
           "ğ": "yumuşak ge", "h": "he", "ı": "ı", "i": "i", "j": "je", "k": "ke", "l": "le",
           "m": "me", "n": "ne", "o": "o", "ö": "ö", "p": "pe", "q": "kü", "r": "re", "s": "se",
           "ş": "şe", "t": "te", "u": "u", "ü": "ü", "v": "ve", "w": "çift ve", "x": "iks",
           "y": "ye", "z": "ze"}
ACRONYM_WORDS = frozenset(("nato", "nasa", "unesco", "unicef", "fifa", "uefa", "opec", "covid",
                           "ram", "rom", "led", "pin", "sim", "aselsan", "aids", "ikea"))
ABBREVIATIONS = {
    "Prof. Dr.": "profesör doktor", "Doç. Dr.": "doçent doktor", "Dr.": "doktor",
    "Prof.": "profesör", "Doç.": "doçent", "Av.": "avukat", "Sn.": "sayın", "vb.": "ve benzeri",
    "vs.": "vesaire", "örn.": "örneğin", "bkz.": "bakınız", "Bkz.": "bakınız", "No.": "numara",
    "no.": "numara", "Tel.": "telefon", "tel.": "telefon", "Mah.": "mahallesi",
    "Cad.": "caddesi", "Sok.": "sokak", "yy.": "yüzyıl", "M.Ö.": "milattan önce",
    "M.S.": "milattan sonra", "T.C.": "te ce", "A.Ş.": "anonim şirketi", "Ltd.": "limited",
    "Şti.": "şirketi", "slm": "selam", "tşk": "teşekkürler", "tmm": "tamam", "nbr": "ne haber",
}
# Units after a number (Turkish nouns stay singular after a number).
UNITS = {"km": "kilometre", "m": "metre", "cm": "santimetre", "mm": "milimetre", "kg": "kilogram",
         "g": "gram", "mg": "miligram", "l": "litre", "L": "litre", "ml": "mililitre",
         "sa": "saat", "h": "saat", "dk": "dakika", "sn": "saniye", "GB": "gigabayt",
         "MB": "megabayt", "TB": "terabayt", "kWh": "kilovatsaat", "kW": "kilovat", "W": "vat",
         "V": "volt", "mAh": "miliamper saat", "GHz": "gigahertz", "MHz": "megahertz",
         "°C": "derece", "℃": "derece", "°": "derece"}
SPEED = {"km/h", "km/sa"}
CURRENCY = {"TL": "lira", "₺": "lira", "US$": "dolar", "$": "dolar", "€": "avro", "EUR": "avro",
            "£": "sterlin", "¥": "yen"}
CENTS = {"lira": "kuruş", "dolar": "sent", "avro": "sent"}
SYMBOLS = {"&": " ve ", "+": " artı ", "=": " eşittir ", "@": " et ", "#": " diyez ", "×": " çarpı ",
           "/": " ", "%": " yüzde "}
MARK_WORDS = {",": "virgül", ".": "nokta"}
SUFFIX = r"(?:'([^\W\d_]+))?"  # 2026'da: a suffix after an apostrophe

_A = r"(?<![\w.,])"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted([*UNITS, *SPEED], key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?<![\d/.])(\d{1,2})[/.](\d{1,2})[/.](\d{4})(?![\d/]|\.\d)" + SUFFIX)
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])" + SUFFIX)
TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])" + SUFFIX)
TIME_DOT = re.compile(r"\b(saat|Saat)\s+([01]?\d|2[0-4])\.([0-5]\d)(?![\d.,])" + SUFFIX)
PHONE = re.compile(r"(?<![\d])(?:\+\d{1,3}[\s-])?\(?0?\d{3}\)?[\s-]\d{3}[\s-]\d{2}[\s-]\d{2}(?![\d])"
                   r"|(?<![\d.,])0\d{10}(?![\d])")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")" + SUFFIX)
MONEY_AFTER = re.compile(_A + r"(" + NUM + r")\s?(" + _CUR_KEYS + r")(?![\w])" + SUFFIX)
PERCENT_BEFORE = re.compile(r"%\s?(" + NUM + r")" + SUFFIX)
PERCENT_AFTER = re.compile(_A + r"(" + NUM + r")\s?%" + SUFFIX)
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])" + SUFFIX)
ORDINAL = re.compile(_A + r"(\d+)\.(?=\s+[a-zçğıöşü])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)(?![\w'])")
SUFFIX_START = re.compile(r"(?<![^\W\d_])'(?=[^\W\d_])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])" + SUFFIX)


def cardinal(n: int) -> str:
    """Turkish cardinal: 21 -> yirmi bir, 100 -> yüz, 1000 -> bin, 2026 -> iki bin yirmi altı."""
    if n < 0:
        return "eksi " + cardinal(-n)
    if n == 0:
        return "sıfır"
    if n >= 10 ** 15:
        return digits(str(n), DIGITS)
    parts: list[str] = []
    for scale, name in ((10 ** 12, "trilyon"), (10 ** 9, "milyar"), (10 ** 6, "milyon")):
        q, n = divmod(n, scale)
        if q:
            parts += [cardinal(q), name]
    th, n = divmod(n, 1000)
    if th:
        parts += ([] if th == 1 else [cardinal(th)]) + ["bin"]
    h, n = divmod(n, 100)
    if h:
        parts += ([] if h == 1 else [ONES[h]]) + ["yüz"]
    t, u = divmod(n, 10)
    if t:
        parts.append(TENS[t])
    if u:
        parts.append(ONES[u])
    return " ".join(parts)


def _last_vowel(word: str) -> str:
    return next((ch for ch in reversed(word) if ch in "aeıioöuü"), "e")


def harmony4(word: str) -> str:
    """The vowel of a four-way suffix (ı i u ü) after word."""
    return {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}[_last_vowel(word)]


def ordinal(n: int) -> str:
    """1 -> birinci, 4 -> dördüncü, 6 -> altıncı, 20 -> yirminci."""
    words = cardinal(n)
    last = words.split()[-1]
    head = words[:len(words) - len(last)]
    if last == "dört":
        last = "dörd"
    v = harmony4(last)
    return head + last + ("" if last[-1] in "aeıioöuü" else v) + "nc" + v


def join_suffix(words: str, suffix: str | None) -> str:
    """2026 + 'da -> ... altıda; dört + üncü -> dördüncü."""
    if not suffix:
        return words
    if words.endswith("dört") and suffix[0] in "aeıioöuü":
        words = words[:-1] + "d"
    return words + tr_lower(suffix)


def number(s: str) -> str:
    out = read_number(s.lstrip("-"), cardinal, MARK_WORDS, DIGITS)
    return ("eksi " if s.startswith("-") else "") + out


def _date(d: int, m: int, y: str, suffix: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    return f" {cardinal(d)} {MONTHS[m]} {join_suffix(cardinal(int(y)), suffix)} "


def _time(h: int, mi: int, sec: str | None, suffix: str | None) -> str:
    out = cardinal(h)
    if mi:
        out += " " + cardinal(mi)
    if sec and int(sec):
        out += " " + cardinal(int(sec))
    return f" {join_suffix(out, suffix)} "


def _money(num: str, cur: str, suffix: str | None) -> str:
    n, frac, _ = parse_number(num)
    name = CURRENCY[cur]
    if frac is not None and len(frac) == 2 and name in CENTS:
        out = f"{cardinal(n)} {name}"
        if int(frac):
            out += f" {cardinal(int(frac))} {CENTS[name]}"
        return f" {join_suffix(out, suffix)} "
    return f" {join_suffix(number(num) + ' ' + name, suffix)} "


def _unit(m: re.Match) -> str:
    sign, num, unit, suffix = m.groups()
    words = ("eksi " if sign else "") + number(num)
    if unit in SPEED:
        return f" saatte {join_suffix(words + ' kilometre', suffix)} "
    return f" {join_suffix(words + ' ' + UNITS[unit], suffix)} "


def normalize_tr(text: str) -> str:
    t = text.replace("’", "'")
    t = apply_abbreviations(t, ABBREVIATIONS)
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1), m.group(4))
                     or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3), m.group(4))
                     or m.group(0), t)
    t = TIME.sub(lambda m: _time(int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)), t)
    t = TIME_DOT.sub(lambda m: m.group(1) + _time(int(m.group(2)), int(m.group(3)), None,
                                                  m.group(4)), t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), DIGITS, "artı"), t)
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1), m.group(3)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(2), m.group(3)), t)
    t = PERCENT_BEFORE.sub(lambda m: f" yüzde {join_suffix(number(m.group(1)), m.group(2))} ", t)
    t = PERCENT_AFTER.sub(lambda m: f" yüzde {join_suffix(number(m.group(1)), m.group(2))} ", t)
    t = UNIT.sub(_unit, t)
    t = ORDINAL.sub(lambda m: f" {ordinal(int(m.group(1)))} ", t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} ile {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, DIGITS)} ", t)
    t = NUMBER.sub(lambda m: f" {join_suffix(number(m.group(1) + m.group(2)), m.group(3))} ", t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ")
    t = acronyms(t, LETTERS, ACRONYM_WORDS)
    t = SUFFIX_START.sub(SUFFIX_MARK, t)  # 'da after an English word: kept as a word, unstressed
    return finish(tr_lower(t))
