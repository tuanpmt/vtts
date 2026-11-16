"""English text normalization: numbers, money, dates, times, units and abbreviations to words.

Output follows the Vietnamese normalizer's convention: lowercase words and the punctuation
tokens , . ? ! ; : separated by single spaces. Acronyms are spelled ("USB" -> "u s b") and
CamelCase is split ("ChatGPT" -> "chat g p t"), since case is lost after normalization.
"""

from __future__ import annotations

import re

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
        "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
SCALES = [(10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand")]
ORD_IRREG = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
             "nine": "ninth", "twelve": "twelfth"}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]
MONTH_ABBR = {m[:3]: m for m in MONTHS}
ABBREV = {"Dr.": "doctor", "Mr.": "mister", "Mrs.": "missus", "Ms.": "miz", "Prof.": "professor",
          "etc.": "et cetera", "vs.": "versus", "e.g.": "for example", "i.e.": "that is",
          "St.": "saint", "Jr.": "junior", "Sr.": "senior"}
UNITS = {"km": "kilometers", "kg": "kilograms", "cm": "centimeters", "mm": "millimeters",
         "m": "meters", "g": "grams", "mg": "milligrams", "l": "liters", "ml": "milliliters",
         "mph": "miles per hour", "km/h": "kilometers per hour", "kb": "kilobytes",
         "mb": "megabytes", "gb": "gigabytes", "tb": "terabytes", "°c": "degrees celsius",
         "°f": "degrees fahrenheit", "°": "degrees", "ms": "milliseconds", "hz": "hertz",
         "khz": "kilohertz", "mhz": "megahertz", "ghz": "gigahertz", "w": "watts", "kw": "kilowatts",
         "v": "volts", "mah": "milliamp hours", "h": "hours", "min": "minutes", "s": "seconds"}
UNIT_ONE = {"kilometers": "kilometer", "kilograms": "kilogram", "meters": "meter", "grams": "gram",
            "liters": "liter", "degrees": "degree", "hours": "hour", "minutes": "minute",
            "seconds": "second", "watts": "watt", "volts": "volt"}
CURRENCY = {"$": ("dollar", "dollars", "cent", "cents"), "€": ("euro", "euros", "cent", "cents"),
            "£": ("pound", "pounds", "penny", "pence")}
PUNCT = ",.?!;:"


def cardinal(n: int) -> str:
    if n < 0:
        return "minus " + cardinal(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + ("" if rest == 0 else " " + cardinal(rest))
    for value, name in SCALES:
        if n >= value:
            rest = n % value
            return cardinal(n // value) + f" {name}" + ("" if rest == 0 else " " + cardinal(rest))
    raise AssertionError


def ordinal(n: int) -> str:
    words = cardinal(n).split()
    last = words[-1]
    if last in ORD_IRREG:
        words[-1] = ORD_IRREG[last]
    elif last.endswith("y"):
        words[-1] = last[:-1] + "ieth"
    else:
        words[-1] = last + "th"
    return " ".join(words)


def year(n: int) -> str:
    if 2000 <= n <= 2009:
        return cardinal(n)
    hi, lo = divmod(n, 100)
    if lo == 0:
        return cardinal(hi) + " hundred"
    return cardinal(hi) + " " + (("oh " + ONES[lo]) if lo < 10 else cardinal(lo))


def digits(s: str) -> str:
    return " ".join(ONES[int(c)] for c in s)


def number(s: str) -> str:
    """'1,250' -> words; '3.14' -> 'three point one four'."""
    s = s.replace(",", "")
    if "." in s:
        a, b = s.split(".", 1)
        return cardinal(int(a or 0)) + " point " + digits(b)
    return cardinal(int(s))


def _money(m: re.Match) -> str:
    one, many, sub1, subn = CURRENCY[m.group(1)]
    whole = int(m.group(2).replace(",", ""))
    cents = int((m.group(3) or "0").ljust(2, "0")[:2])
    scale = m.group(4)
    if scale:
        return f"{number(m.group(2) + ('.' + m.group(3) if m.group(3) else ''))} {scale} {many}"
    out = f"{cardinal(whole)} {one if whole == 1 else many}" if whole or not cents else ""
    if cents:
        out += (" " if out else "") + f"{cardinal(cents)} {sub1 if cents == 1 else subn}"
    return f" {out} "


def _time(m: re.Match) -> str:
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3)
    words = cardinal(h) + (" o'clock" if mi == 0 and not ap else "" if mi == 0
                           else " oh " + ONES[mi] if mi < 10 else " " + cardinal(mi))
    if ap:
        words += " " + " ".join(ap.lower().replace(".", ""))
    return f" {words} "


def _date(m: re.Match) -> str:
    mo, d, y = int(m.group(1)), int(m.group(2)), m.group(3)
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return m.group(0)
    out = f"{MONTHS[mo - 1]} {ordinal(d)}"
    if y:
        out += " " + year(int(y)) if len(y) == 4 else " " + cardinal(int(y))
    return f" {out} "


def _unit(m: re.Match) -> str:
    val, unit = m.group(1), m.group(2)
    name = UNITS[unit.lower()]
    if val.replace(",", "") in ("1", "1.0"):
        first = name.split()[0]
        name = " ".join([UNIT_ONE.get(first, first)] + name.split()[1:])
    return f" {number(val)} {name} "


def _spell_caps(word: str) -> str:
    """Split CamelCase and spell all-caps runs of <= 5 letters."""
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z']+|[a-z']+", word)
    if not parts or "".join(parts) != word:
        return word.lower()
    out = []
    for p in parts:
        if p.isupper() and len(p) <= 5 and len(parts) + len(p) > 2:
            out.append(" ".join(p.lower()))
        else:
            out.append(p.lower())
    return " ".join(out)


def normalize_en(text: str) -> str:
    t = " " + text + " "
    for k, v in ABBREV.items():
        t = re.sub(rf"(?<![\w.]){re.escape(k)}", f" {v} ", t)
    t = re.sub(r"([$€£])(\d[\d,]*)(?:\.(\d+))?(?:\s?(million|billion|thousand))?", _money, t)
    t = re.sub(r"\b(\d{1,2}):(\d{2})\s?([AaPp]\.?[Mm]\.?)?(?![\w])", _time, t)
    t = re.sub(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?\b", _date, t)
    t = re.sub(r"\b(\d{1,2})\s+(" + "|".join(m.capitalize() for m in MONTHS) + r")\b",
               lambda m: f" the {ordinal(int(m.group(1)))} of {m.group(2).lower()} ", t)
    t = re.sub(r"\b(" + "|".join(m.capitalize() for m in MONTHS) + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?!\d)",
               lambda m: f" {m.group(1).lower()} {ordinal(int(m.group(2)))} ", t)
    t = re.sub(r"\b(\d{1,2})\s?([AaPp])\.?[Mm]\.?(?![\w])", lambda m: f" {cardinal(int(m.group(1)))} {m.group(2).lower()} m ", t)
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s?%", lambda m: f" {number(m.group(1))} percent ", t)
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s?(" + "|".join(sorted(map(re.escape, UNITS), key=len, reverse=True))
               + r")(?![\w])", _unit, t, flags=re.IGNORECASE)
    t = re.sub(r"\b(\d+)(st|nd|rd|th)\b", lambda m: f" {ordinal(int(m.group(1)))} ", t)
    t = re.sub(r"(?<![\w.,])(1[1-9]\d\d|20\d\d)(?![\d,.]\d|\w)", lambda m: f" {year(int(m.group(1)))} ", t)
    t = re.sub(r"(?<![\w])-(\d)", r" minus \1", t)
    t = re.sub(r"(\d)([A-Za-z])", r"\1 \2", t)
    t = re.sub(r"\d(?:[\d,]*\d)?(?:\.\d+)?", lambda m: f" {number(m.group(0))} ", t)
    t = t.replace("&", " and ").replace("+", " plus ").replace("@", " at ")
    out = []
    for tok in re.findall(r"[A-Za-z][A-Za-z']*(?:-[A-Za-z']+)*|[" + re.escape(PUNCT) + "]", t):
        if tok in PUNCT:
            if out and out[-1] not in PUNCT:
                out.append(tok)
            continue
        for piece in tok.split("-"):
            if piece:
                out.append(_spell_caps(piece))
    return " ".join(" ".join(out).split())
