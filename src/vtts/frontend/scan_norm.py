"""Scanner normalizer shared by the Dutch, Swedish and Norwegian front-ends (nl, sv, no).

One left-to-right pass over the code points of a run (no regular expressions, so the C port in
runtime/src/vtts_text_nx.c follows it step by step). Each language gives a Spec: its tables
(abbreviations, units, currencies, letter names, symbols, month names) and its number readers.
The output follows the other modules' convention: lower-case words and the marks , . ? ! ; :
separated by single spaces.

At each position, in this order:

1. space: a word boundary.
2. at a token start (the previous code point is not a word character): a currency before a number
   (€ 5, $5, kr 50, US$ 3), then an abbreviation of the table (case-sensitive, longest first; a key
   that does not end with "." must not be followed by a word character; a key ending with "." at
   the end of the text keeps the full stop).
3. "-" or "−" before a digit at the start of the text or after a space: minus and the number.
4. a digit at a token start: an ISO date (2026-05-03), a day-month-year date (3-5-2026, 3.5.2026,
   3/5/26), a time (14:30, 9:05:10; h.mm after "kl." / "kl" / "klockan" / "klokka" / "klokken" or
   before "uur"), a phone number ("+" or a leading 0, groups of digits separated by one space, "-"
   or "/", at least 8 digits), a number with an attached unit or ordinal suffix (5km, 2e, 3:e), a
   code of digits and letters (4G: digits one by one, letters by name), else a number: digits with
   thousands groups (1.000, 1 000 000 with a space or no-break space, groups of exactly three
   digits) and a decimal part after "," (komma) or "." (punt / punkt / punktum), a range (10-20),
   followed by (after at most one space) %, ‰, a unit, a currency or the language's ordinal mark.
   An integer of 1100-1999 without separators is read as a year.
5. a run of word characters starting with a letter: a code with digits (ESP32: letters by name,
   digits one by one; digits stay a number when the run has no capital letter), an acronym of 2-5
   capitals (spelled, except the language's ACRONYM_WORDS), else the word in lower case. An
   apostrophe between letters stays in the word (auto's); Dutch keeps a leading apostrophe ('s, 't).
6. marks , . ? ! ; : are kept; … ... — – and a hyphen between spaces are a pause (,); a hyphen
   between words separates them; symbols of the table are read (& + = @ # × § °); anything else is
   a word boundary.

A mark right after another mark is dropped (a leading mark is kept: text.py drops marks that follow
nothing).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

MARKS = ",.?!;:"
THOUSANDS_SPACES = "   "
PHONE_SEPS = " -/"
DASHES = "–—"  # – —
MINUS = "-−"


def is_w(c: str) -> bool:
    """Python re \\w of one code point (C: vtts_u_word)."""
    return c.isalnum() or c == "_"


def is_d(c: str) -> bool:
    return "0" <= c <= "9"


def is_sp(c: str) -> bool:
    return c.isspace()


def low(c: str) -> str:
    """str.lower() of one code point, first code point only (C: vtts_u_lower)."""
    return c.lower()[:1] or c


def is_up(c: str) -> bool:
    return low(c) != c


def is_letter(c: str) -> bool:
    """A word character other than an ASCII digit and _."""
    return is_w(c) and c != "_" and not is_d(c)


@dataclass(frozen=True)
class Currency:
    one: str
    many: str
    sub_one: str
    sub_many: str


@dataclass
class Spec:
    code: str
    digits: tuple[str, ...]                 # 0..9 one by one
    cardinal: Callable[[int], str]           # words of an integer >= 0 (below 10**15)
    ordinal: Callable[[int], str]            # words of an ordinal >= 1
    year: Callable[[int], str]               # a year 1100-1999
    date: Callable[[int, int, int | None], str]   # day, month, year (or None)
    time: Callable[[int, int, int | None], str]   # hours, minutes, seconds (or None)
    minus: str
    comma: str                               # decimal comma
    point: str                               # decimal point (3.14)
    percent: str
    permille: str
    range_word: str
    plus: str
    and_word: str                            # money: units and cents
    letters: dict[str, str]                  # lower-case letter -> name
    acronym_words: frozenset[str]
    abbreviations: dict[str, str]
    units: dict[str, tuple[str, str]]        # key -> (one, many)
    currency: dict[str, Currency]            # key after a number (also before when in CURRENCY_BEFORE)
    currency_before: tuple[str, ...]         # keys read before a number (€ 5)
    symbols: dict[str, str]
    months: tuple[str, ...]                  # 1..12 (index 0 unused)
    ordinal_suffixes: tuple[str, ...] = ()   # attached to the digits (nl 2e, 3de; sv 1:a, 3:e)
    ordinal_dot: bool = False                # no: "17. mai" (a dot, a space, a lower-case letter)
    month_ordinal: bool = False              # sv, no: "3 maj" -> tredje maj
    time_after: tuple[str, ...] = ()         # nl: "uur" after h.mm makes a time (and is consumed)
    time_before: tuple[str, ...] = ()        # sv, no: "kl." before h.mm makes a time
    leading_apostrophe: bool = False         # nl: 's 't 'n
    dash_money: tuple[str, ...] = ()         # ",-" / ":-" after an amount: the default currency
    default_currency: str = ""
    keys_sorted: dict[str, list[str]] = field(default_factory=dict)

    def sorted_keys(self, name: str) -> list[str]:
        """Keys of a table, longest first (ties in table order)."""
        if name not in self.keys_sorted:
            table = getattr(self, name)
            self.keys_sorted[name] = sorted(table, key=len, reverse=True)
        return self.keys_sorted[name]


def _at(s: str, i: int, key: str) -> bool:
    return s.startswith(key, i)


def _digits_end(s: str, i: int) -> int:
    while i < len(s) and is_d(s[i]):
        i += 1
    return i


class _Out:
    def __init__(self) -> None:
        self.items: list[str] = []

    def words(self, text: str) -> None:
        for w in text.split(" "):
            if w:
                self.items.append(w)

    def mark(self, m: str) -> None:
        self.items.append(m)

    def finish(self) -> str:
        out: list[str] = []
        for w in self.items:
            if w in MARKS and out and out[-1] in MARKS:
                continue
            out.append(w)
        return " ".join(out)


# ---------------- numbers ----------------

def scan_number(s: str, i: int) -> tuple[int, str, str | None, str | None]:
    """(end, integer digits, decimal digits or None, decimal mark or None) of the number at s[i]
    (a digit). Thousands groups: one separator (. or a space) used throughout, groups of exactly
    three digits after a first group of 1-3 digits that does not start with 0."""
    n = len(s)
    j = _digits_end(s, i)
    int_s = s[i:j]
    grouped = False
    if j - i <= 3 and s[i] != "0" and j < n and (s[j] == "." or s[j] in THOUSANDS_SPACES):
        sep = s[j]
        k = j
        while (k + 3 < n and s[k] == sep and is_d(s[k + 1]) and is_d(s[k + 2]) and is_d(s[k + 3])
               and not (k + 4 < n and is_d(s[k + 4]))):
            int_s += s[k + 1:k + 4]
            k += 4
        if k > j:
            j, grouped = k, True
    if j + 1 < n and s[j] == "," and is_d(s[j + 1]):
        e = _digits_end(s, j + 1)
        return e, int_s, s[j + 1:e], ","
    if not grouped and j + 1 < n and s[j] == "." and is_d(s[j + 1]):
        e = _digits_end(s, j + 1)
        return e, int_s, s[j + 1:e], "."
    return j, int_s, None, None


def read_digits(sp: Spec, digits: str) -> str:
    return " ".join(sp.digits[ord(c) - 48] for c in digits)


def read_int(sp: Spec, int_s: str, year: bool = False) -> str:
    """An integer as written: a leading zero or more than 15 digits are read digit by digit; with
    year, 1100-1999 is read as a year."""
    if len(int_s) > 15 or (len(int_s) > 1 and int_s[0] == "0"):
        return read_digits(sp, int_s)
    v = int(int_s)
    if year and 1100 <= v <= 1999:
        return sp.year(v)
    return sp.cardinal(v)


def read_number(sp: Spec, int_s: str, frac: str | None, mark: str | None, year: bool = False) -> str:
    out = read_int(sp, int_s, year and frac is None)
    if frac is not None:
        word = sp.comma if mark == "," else sp.point
        if len(frac) <= 2 and frac[0] != "0":
            out += f" {word} {sp.cardinal(int(frac))}"
        else:
            out += f" {word} {read_digits(sp, frac)}"
    return out


def _is_one(int_s: str, frac: str | None) -> bool:
    return frac is None and int_s == "1"


# ---------------- the pass ----------------

def _match_key(s: str, i: int, keys: list[str], word_end: bool = True) -> str | None:
    """The first (longest) key at s[i]; a key ending in a word character must not be followed by
    a word character."""
    for k in keys:
        if _at(s, i, k):
            e = i + len(k)
            if word_end and is_w(k[-1]) and e < len(s) and is_w(s[e]):
                continue
            return k
    return None


def _skip_space(s: str, i: int) -> int:
    """i past at most one space."""
    return i + 1 if i < len(s) and s[i] == " " else i


def _rest_blank(s: str, i: int) -> bool:
    return all(is_sp(c) for c in s[i:])


def _date(s: str, i: int) -> tuple[int, int, int, int | None] | None:
    """(end, day, month, year) of an ISO or day-month-year date at s[i]."""
    n = len(s)
    j = _digits_end(s, i)
    if j - i == 4 and j < n and s[j] == "-":  # yyyy-mm-dd
        a = j + 1
        b = _digits_end(s, a)
        if 1 <= b - a <= 2 and b < n and s[b] == "-":
            c = b + 1
            e = _digits_end(s, c)
            if 1 <= e - c <= 2 and not (e < n and (s[e] == "-" or is_w(s[e]))):
                d, m = int(s[c:e]), int(s[a:b])
                if 1 <= d <= 31 and 1 <= m <= 12:
                    return e, d, m, int(s[i:j])
        return None
    if 1 <= j - i <= 2 and j < n and s[j] in "./-":
        sep = s[j]
        a = j + 1
        b = _digits_end(s, a)
        if 1 <= b - a <= 2 and b < n and s[b] == sep:
            c = b + 1
            e = _digits_end(s, c)
            if e - c in (2, 4) and not (e < n and (is_w(s[e]) or (s[e] in "./-" and e + 1 < n and is_d(s[e + 1])))):
                d, m = int(s[i:j]), int(s[a:b])
                if 1 <= d <= 31 and 1 <= m <= 12:
                    y = int(s[c:e])
                    return e, d, m, y + 2000 if e - c == 2 else y
    return None


def _time_before(sp: Spec, s: str, i: int) -> bool:
    """One of sp.time_before (case-insensitive) right before s[i], after at most one space, at a
    token start."""
    j = i - 1 if i > 0 and s[i - 1] == " " else i
    for k in sp.time_before:
        a = j - len(k)
        if a >= 0 and "".join(low(c) for c in s[a:j]) == k and (a == 0 or not is_w(s[a - 1])):
            return True
    return False


def _time(sp: Spec, s: str, i: int) -> tuple[int, str] | None:
    """(end, reading) of a time at s[i]: h:mm[:ss], or h.mm with a time word before or after."""
    n = len(s)
    j = _digits_end(s, i)
    if not (1 <= j - i <= 2 and j + 2 < n and s[j] in ":." and is_d(s[j + 1]) and is_d(s[j + 2])):
        return None
    h, mi = int(s[i:j]), int(s[j + 1:j + 3])
    e = j + 3
    if h > 24 or mi > 59 or (e < n and is_d(s[e])):
        return None
    sec = None
    if s[j] == ":" and e + 2 < n and s[e] == ":" and is_d(s[e + 1]) and is_d(s[e + 2]) \
            and not (e + 3 < n and is_d(s[e + 3])) and int(s[e + 1:e + 3]) <= 59:
        sec = int(s[e + 1:e + 3])
        e += 3
    if e < n and is_w(s[e]):
        return None
    if s[j] == ".":
        after = _skip_space(s, e)
        word = next((k for k in sp.time_after if _at(s, after, k)
                     and not (after + len(k) < n and is_w(s[after + len(k)]))), None)
        if word is not None:
            return after + len(word), sp.time(h, mi, None)
        if not _time_before(sp, s, i):
            return None
        return e, sp.time(h, mi, None)
    after = _skip_space(s, e)
    word = next((k for k in sp.time_after if _at(s, after, k)
                 and not (after + len(k) < n and is_w(s[after + len(k)]))), None)
    if word is not None:
        e = after + len(word)
    return e, sp.time(h, mi, sec)


def _two_digits(s: str, i: int) -> bool:
    return i + 1 < len(s) and is_d(s[i]) and is_d(s[i + 1])


def _phone(s: str, i: int) -> int | None:
    """End of a phone number at s[i] ("+" or a digit)."""
    n = len(s)
    j = i
    plus = s[j] == "+"
    if plus:
        j += 1
    if j >= n or not is_d(s[j]) or (not plus and s[j] != "0"):
        return None
    total = 0
    while True:
        e = _digits_end(s, j)
        total += e - j
        if e + 1 < n and s[e] in PHONE_SEPS and is_d(s[e + 1]):
            j = e + 1
            continue
        break
    if total < 8 or (e < n and is_w(s[e])):
        return None
    return e


def _suffix(sp: Spec, s: str, i: int, int_s: str) -> tuple[int, str, object] | None:
    """(end, kind, value) of what follows the number ending at s[i] (after at most one space):
    ("w", words) for %, ‰ and a unit, ("m", Currency) for a currency (also 50:- and 50,-)."""
    n = len(s)
    j = _skip_space(s, i)
    if j < n and s[j] == "%":
        return j + 1, "w", sp.percent
    if j < n and s[j] == "\u2030":
        return j + 1, "w", sp.permille
    k = _match_key(s, j, sp.sorted_keys("units"))
    if k is not None:
        one, many = sp.units[k]
        return j + len(k), "w", one if int_s == "1" else many
    k = _match_key(s, j, sp.sorted_keys("currency"))
    if k is not None:
        e = j + len(k)
        if k[-1] == "." and _rest_blank(s, e):  # 99 kr. at the end: the dot ends the sentence
            e -= 1
        return _dash_end(s, e), "m", sp.currency[k]
    if i + 1 < n and s[i:i + 2] in sp.dash_money and not (i + 2 < n and is_w(s[i + 2])):  # 50:- / 50,-
        return i + 2, "m", sp.currency[sp.default_currency]
    return None


def _dash_end(s: str, e: int) -> int:
    """Past a ",-" ".-" or ":-" after an amount (5 kr.- / € 5,-) that no word character follows."""
    if e + 1 < len(s) and s[e] in ",.:" and s[e + 1] == "-" and not (e + 2 < len(s) and is_w(s[e + 2])):
        return e + 2
    return e


def money(sp: Spec, cur: Currency, int_s: str, frac: str | None) -> str:
    """An amount with its currency: 5 kronor; 5 kronor och 50 öre (two decimals); other decimals
    as a number before the plural."""
    if frac is None or frac == "00":
        return f"{read_int(sp, int_s)} {cur.one if int_s == '1' else cur.many}"
    if len(frac) == 2 and cur.sub_many:
        cents = int(frac)
        unit = cur.one if int_s == "1" else cur.many
        sub = cur.sub_one if cents == 1 else cur.sub_many
        if int_s == "0":
            return f"{sp.cardinal(cents)} {sub}"
        return f"{read_int(sp, int_s)} {unit} {sp.and_word} {sp.cardinal(cents)} {sub}"
    return f"{read_number(sp, int_s, frac, ',')} {cur.many}"


def _ordinal_suffix(sp: Spec, s: str, j: int) -> str | None:
    for k in sp.ordinal_suffixes:
        if _at(s, j, k) and not (j + len(k) < len(s) and is_w(s[j + len(k)])):
            return k
    return None


def _month_at(sp: Spec, s: str, j: int) -> bool:
    for m in sp.months[1:]:
        if j + len(m) <= len(s) and "".join(low(c) for c in s[j:j + len(m)]) == m \
                and not (j + len(m) < len(s) and is_w(s[j + len(m)])):
            return True
    return False


def _code(sp: Spec, run: str, o: _Out) -> None:
    """A run of letters and digits: letter runs by name when the run has a capital (or a letter
    run of one letter), else as a word; digit runs one by one when the run has a capital, else as
    a number."""
    caps = any(is_up(c) for c in run)
    k = 0
    while k < len(run):
        e = k
        if is_d(run[k]):
            while e < len(run) and is_d(run[e]):
                e += 1
            part = run[k:e]
            o.words(read_digits(sp, part) if caps else read_int(sp, part))
        else:
            while e < len(run) and not is_d(run[e]):
                e += 1
            part = run[k:e]
            if caps or len(part) == 1:
                _spell(sp, part, o)
            else:
                o.words("".join(low(c) for c in part))
        k = e


def _spell(sp: Spec, part: str, o: _Out) -> None:
    for c in part:
        name = sp.letters.get(low(c))
        if name:
            o.words(name)


def _word(sp: Spec, s: str, i: int, o: _Out) -> int:
    """The run of word characters (and apostrophes between letters) at s[i]; returns its end."""
    n = len(s)
    j = i
    while j < n and (is_w(s[j]) and s[j] != "_" or (s[j] == "'" and j > i and j + 1 < n and is_letter(s[j + 1])
                                                    and is_letter(s[j - 1]))):
        j += 1
    run = s[i:j]
    if any(is_d(c) for c in run):
        _code(sp, run, o)
        return j
    letters = [c for c in run if c != "'"]
    if 2 <= len(letters) <= 5 and all(is_up(c) for c in letters):
        low_run = "".join(low(c) for c in run)
        if low_run in sp.acronym_words:
            o.words(low_run)
        else:
            _spell(sp, run, o)
        return j
    o.words("".join(low(c) for c in run))
    return j


def _number_at(sp: Spec, s: str, i: int, o: _Out, neg: bool) -> int:
    """A digit at s[i] at a token start; returns the end of what was read."""
    n = len(s)
    if not neg:
        d = _date(s, i)
        if d is not None:
            e, day, month, year = d
            o.words(sp.date(day, month, year))
            return e
        t = _time(sp, s, i)
        if t is not None:
            o.words(t[1])
            return t[0]
        p = _phone(s, i)
        if p is not None:
            o.words(read_digits(sp, "".join(c for c in s[i:p] if is_d(c))))
            return p
    j = _digits_end(s, i)
    # attached letters: an ordinal suffix, a unit, else a code (4G, 3D)
    if j < n and is_letter(s[j]) or (j + 1 < n and s[j] == ":" and is_letter(s[j + 1])):
        k = _ordinal_suffix(sp, s, j)
        if k is not None and not neg:
            o.words(sp.ordinal(int(s[i:j])) if int(s[i:j]) > 0 and j - i <= 6 else read_int(sp, s[i:j]))
            return j + len(k)
        if is_letter(s[j]):
            u = _match_key(s, j, sp.sorted_keys("units"))
            if u is not None:
                o.words(read_int(sp, s[i:j]))
                one, many = sp.units[u]
                o.words(one if s[i:j] == "1" else many)
                return j + len(u)
            e = j
            while e < n and is_w(s[e]) and s[e] != "_":
                e += 1
            _code(sp, s[i:e], o)
            return e
    e, int_s, frac, mark = scan_number(s, i)
    # range a-b
    if frac is None and e + 1 < n and s[e] in "-–" and is_d(s[e + 1]):
        e2, int2, frac2, _ = scan_number(s, e + 1)
        if frac2 is None and not (e2 < n and (is_letter(s[e2]) or s[e2] in "-–")):
            o.words(read_int(sp, int_s) + f" {sp.range_word} " + read_int(sp, int2))
            suf = _suffix(sp, s, e2, int2)
            if suf is not None and suf[1] == "w":
                o.words(suf[2])
                return suf[0]
            if suf is not None:
                cur = suf[2]
                o.words(cur.one if int2 == "1" else cur.many)
                return suf[0]
            return e2
    if sp.ordinal_dot and frac is None and not neg and e - i <= 3 and e + 2 < n and s[e] == "." \
            and s[e + 1] == " " and is_letter(s[e + 2]) and not is_up(s[e + 2]) and int_s[0] != "0":
        o.words(sp.ordinal(int(int_s)))
        return e + 1
    if sp.month_ordinal and frac is None and not neg and e - i <= 2 and e + 1 < n and s[e] == " " \
            and int_s[0] != "0" and 1 <= int(int_s) <= 31 and _month_at(sp, s, e + 1):
        o.words(sp.ordinal(int(int_s)))
        return e
    sign = sp.minus + " " if neg else ""
    suf = _suffix(sp, s, e, int_s)
    if suf is None:
        o.words(sign + read_number(sp, int_s, frac, mark, year=not neg))
        return e
    end, kind, value = suf
    if kind == "m":
        o.words(sign + money(sp, value, int_s, frac))
    else:
        o.words(sign + read_number(sp, int_s, frac, mark))
        o.words(value)
    return end


def _money_before(sp: Spec, s: str, i: int, o: _Out) -> int | None:
    """A currency key before an amount (€ 5, € 5,50, kr 50,-) at s[i]; returns the end or None."""
    for k in sp.currency_before:
        if not _at(s, i, k) or (is_w(k[-1]) and i + len(k) < len(s) and is_w(s[i + len(k)])):
            continue
        j = _skip_space(s, i + len(k))
        if not (j < len(s) and is_d(s[j])):
            continue
        e, int_s, frac, _ = scan_number(s, j)
        e = _dash_end(s, e)
        if e < len(s) and is_w(s[e]):
            continue
        o.words(money(sp, sp.currency[k], int_s, frac))
        return e
    return None


def normalize(text: str, sp: Spec) -> str:
    s = text
    n = len(s)
    o = _Out()
    i = 0
    while i < n:
        c = s[i]
        start = i == 0 or not is_w(s[i - 1])
        if is_sp(c):
            i += 1
            continue
        if start:
            e = _money_before(sp, s, i, o)
            if e is not None:
                i = e
                continue
            k = _match_key(s, i, sp.sorted_keys("abbreviations"))
            if k is not None:
                o.words(sp.abbreviations[k])
                i += len(k)
                if k[-1] == "." and _rest_blank(s, i):
                    o.mark(".")
                continue
        if c in MINUS and i + 1 < n and is_d(s[i + 1]) and (i == 0 or is_sp(s[i - 1])):
            i = _number_at(sp, s, i + 1, o, neg=True)
            continue
        if c == "+" and start:
            p = _phone(s, i)
            if p is not None:
                o.words(sp.plus + " " + read_digits(sp, "".join(ch for ch in s[i:p] if is_d(ch))))
                i = p
                continue
        if is_d(c):
            if start:
                i = _number_at(sp, s, i, o, neg=False)
            else:
                i = _word(sp, s, i, o)
            continue
        if is_w(c) and c != "_" or (c == "'" and sp.leading_apostrophe and start and i + 1 < n
                                     and is_letter(s[i + 1])):
            if c == "'":
                i += 1
                j = i
                while j < n and is_letter(s[j]):
                    j += 1
                o.words("'" + "".join(low(ch) for ch in s[i:j]))
                i = j
                continue
            i = _word(sp, s, i, o)
            continue
        if c in MARKS:
            if c == "." and _at(s, i, "..."):
                o.mark(",")
                while i < n and s[i] == ".":
                    i += 1
                continue
            o.mark(c)
            i += 1
            continue
        if c == "…" or c in DASHES:
            o.mark(",")
            i += 1
            continue
        if c == "-":
            if (i == 0 or is_sp(s[i - 1])) and (i + 1 >= n or is_sp(s[i + 1])):
                o.mark(",")
            i += 1
            continue
        if c in sp.symbols:
            o.words(sp.symbols[c])
        i += 1
    return o.finish()


# ---------------- sentences ----------------

SENTENCE_MARKS = ".!?;"
CJK_ENDS = "。！？；।॥"
# Abbreviations that end a sentence when a capital letter follows (... enz. De ...).
FINAL_ABBREVIATIONS = ("enz.", "etc.", "osv.", "m.m.", "mv.", "e.d.", "e.a.", "o.l.")


def split_sentences(text: str, sp: Spec) -> list[str]:
    """Sentences of a text, like lang.SENTENCE_END (a cut after . ! ? ; and white space, or after
    。！？；।॥), except after a dot that ends an abbreviation of the table (o.a., bijv., t.ex.),
    a single letter (initials: J. S. Bach) or, with sp.ordinal_dot, a number of 1-3 digits before a
    lower-case letter (17. mai)."""
    s = text.strip()
    n = len(s)
    out: list[str] = []
    start = 0
    i = 0
    while i < n:
        c = s[i]
        cut = -1
        if c in CJK_ENDS:
            cut = i + 1
        elif c in SENTENCE_MARKS and i + 1 < n and is_sp(s[i + 1]) \
                and not (c == "." and i > 0 and "ก" <= s[i - 1] <= "๎"):
            cut = i + 1
            if c == "." and _keeps_dot(s, i, sp):
                cut = -1
        if cut < 0:
            i += 1
            continue
        e = cut
        while e < n and is_sp(s[e]):
            e += 1
        piece = s[start:cut]
        if piece.strip():
            out.append(piece)
        start = e
        i = e
    if s[start:].strip():
        out.append(s[start:])
    return out


def _keeps_dot(s: str, i: int, sp: Spec) -> bool:
    """The dot at s[i] (followed by white space) does not end the sentence."""
    a = i
    while a > 0 and not is_sp(s[a - 1]):
        a -= 1
    w = s[a:i]
    j = i + 1
    while j < len(s) and is_sp(s[j]):
        j += 1
    nxt = s[j] if j < len(s) else ""
    if not w:
        return False
    if w + "." in FINAL_ABBREVIATIONS and nxt and is_up(nxt):
        return False
    if w + "." in sp.abbreviations or (len(w) == 1 and is_letter(w)):
        return True
    return bool(sp.ordinal_dot and 1 <= len(w) <= 3 and all(is_d(c) for c in w) and nxt and is_letter(nxt)
                and not is_up(nxt))
