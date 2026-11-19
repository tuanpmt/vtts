"""Greek text normalization for one Greek run.

Output follows the other modules' convention: words and the punctuation tokens , . ? ! ; :
separated by single spaces. Greek words are lower case with their accents (g2p_el.lower: the
final sigma written ς); Latin parts go through the English normalizer and are read by the English
module. A word may hold combining marks U+0300-U+036F (decomposed accents); text is not
NFC-normalized here, abbreviations and acronyms match precomposed letters only.

Rules, in order: the Greek question mark ";" (and U+037E) -> "?", the ano teleia · -> ";",
abbreviations (π.χ., κ.λπ., δηλ., μ.Χ., τηλ.), quotes and brackets dropped, dates (3/5/2026,
3.5.2026, 2026-05-03 -> τρεις Μαΐου ...; the 1st is πρώτη), times (14:30 -> δεκατέσσερις και
τριάντα; στις 9.15), phone numbers (digit by digit), money (5 €, 12,50 € -> δώδεκα ευρώ και
πενήντα λεπτά, $5), percentages (τοις εκατό), units after a number (5 km, 25 °C, 3 χλμ.),
ordinals with a Greek ending (1ος, 2η, 3ο, 20ός -> πρώτος, δεύτερη, τρίτο, εικοστός), ranges
(10-20 -> δέκα έως είκοσι), pause marks, product codes (ESP32: Latin letters by their Greek names,
digits one by one), numbers (1.000 thousands, 3,5 -> τρία κόμμα πέντε, -5 -> μείον πέντε),
Greek acronyms (ΟΤΕ, ΔΕΗ as words; others of 2-5 capitals spelled by letter names, unless most
words of the text are in capitals), symbols.

Numbers agree in gender with the word after them, guessed from its ending (default neuter):
-ες -εις (and a month in the genitive, ώρα, μέρα, φορά ...) feminine, -οι -ους -ος -ης -ας
masculine. Gender changes 1 (ένα, ένας, μία), 3 and 4 (τρία / τρεις, τέσσερα / τέσσερις, also in
13, 14, 23 ...), the hundreds (διακόσια / διακόσιοι / διακόσιες) and 1000 (χίλια / χίλιοι /
χίλιες); thousands are counted in the feminine (τρεις χιλιάδες).
"""

from __future__ import annotations

import re
import unicodedata

from ..latin_norm import DROP, PAUSE, PRODUCT_CODE, parse_number, phone_digits
from .g2p_el import decompose, lower

ONES = {
    "n": ("μηδέν", "ένα", "δύο", "τρία", "τέσσερα", "πέντε", "έξι", "επτά", "οκτώ", "εννέα"),
    "m": ("μηδέν", "ένας", "δύο", "τρεις", "τέσσερις", "πέντε", "έξι", "επτά", "οκτώ", "εννέα"),
    "f": ("μηδέν", "μία", "δύο", "τρεις", "τέσσερις", "πέντε", "έξι", "επτά", "οκτώ", "εννέα"),
}
TEENS = {
    "n": ("δέκα", "έντεκα", "δώδεκα", "δεκατρία", "δεκατέσσερα", "δεκαπέντε", "δεκαέξι",
          "δεκαεπτά", "δεκαοκτώ", "δεκαεννέα"),
    "m": ("δέκα", "έντεκα", "δώδεκα", "δεκατρείς", "δεκατέσσερις", "δεκαπέντε", "δεκαέξι",
          "δεκαεπτά", "δεκαοκτώ", "δεκαεννέα"),
}
TEENS["f"] = TEENS["m"]
TENS = ("", "", "είκοσι", "τριάντα", "σαράντα", "πενήντα", "εξήντα", "εβδομήντα", "ογδόντα",
        "ενενήντα")
HUNDRED_STEMS = ("", "", "διακόσι", "τριακόσι", "τετρακόσι", "πεντακόσι", "εξακόσι", "επτακόσι",
                 "οκτακόσι", "εννιακόσι")
GENDER_END = {"n": "α", "m": "οι", "f": "ες"}
THOUSAND = {"n": "χίλια", "m": "χίλιοι", "f": "χίλιες"}
SCALES = ((10 ** 9, "ένα δισεκατομμύριο", "δισεκατομμύρια"),
          (10 ** 6, "ένα εκατομμύριο", "εκατομμύρια"))
DIGITS = ONES["n"]
MONTHS = ("", "ιανουαρίου", "φεβρουαρίου", "μαρτίου", "απριλίου", "μαΐου", "ιουνίου", "ιουλίου",
          "αυγούστου", "σεπτεμβρίου", "οκτωβρίου", "νοεμβρίου", "δεκεμβρίου")
FEMININE_WORDS = frozenset(("ώρα", "μέρα", "ημέρα", "φορά", "εβδομάδα", "χιλιάδα", "λίρα",
                            "μονάδα", "θέση", "λέξη", "γυναίκα", "κόρη", "αδελφή", "αδερφή",
                            "πόλη", "χώρα", "οικογένεια", "μοίρα", "σελίδα", "γραμμή", "ομάδα",
                            "φωτογραφία", "εταιρεία", "ταινία", "κιλοβατώρα", *MONTHS[1:]))
# Ordinal stems: (stem, the ending carries the stress).
ORD_ONES = ("", ("πρώτ", False), ("δεύτερ", False), ("τρίτ", False), ("τέταρτ", False),
            ("πέμπτ", False), ("έκτ", False), ("έβδομ", False), ("όγδο", False), ("ένατ", False))
ORD_TEENS = {10: ("δέκατ", False), 11: ("ενδέκατ", False), 12: ("δωδέκατ", False)}
ORD_TENS = ("", "", "εικοστ", "τριακοστ", "τεσσαρακοστ", "πεντηκοστ", "εξηκοστ", "εβδομηκοστ",
            "ογδοηκοστ", "ενενηκοστ")
ORD_HUNDREDS = ("", "εκατοστ", "διακοσιοστ", "τριακοσιοστ", "τετρακοσιοστ", "πεντακοσιοστ",
                "εξακοσιοστ", "επτακοσιοστ", "οκτακοσιοστ", "εννιακοσιοστ")
ORD_ENDINGS = ("ος", "ου", "ο", "ον", "οι", "ων", "ους", "η", "ης", "ες", "α")
ACCENTED = {"ος": "ός", "ου": "ού", "ο": "ό", "ον": "όν", "οι": "οί", "ων": "ών", "ους": "ούς",
            "η": "ή", "ης": "ής", "ες": "ές", "α": "ά"}
GREEK_LETTERS = {"α": "άλφα", "β": "βήτα", "γ": "γάμα", "δ": "δέλτα", "ε": "έψιλον", "ζ": "ζήτα",
                 "η": "ήτα", "θ": "θήτα", "ι": "γιώτα", "κ": "κάπα", "λ": "λάμδα", "μ": "μι",
                 "ν": "νι", "ξ": "ξι", "ο": "όμικρον", "π": "πι", "ρ": "ρο", "σ": "σίγμα",
                 "ς": "σίγμα", "τ": "ταυ", "υ": "ύψιλον", "φ": "φι", "χ": "χι", "ψ": "ψι",
                 "ω": "ωμέγα"}
LATIN_LETTERS = {"a": "έι", "b": "μπι", "c": "σι", "d": "ντι", "e": "ι", "f": "εφ", "g": "τζι",
                 "h": "έιτς", "i": "άι", "j": "τζέι", "k": "κέι", "l": "ελ", "m": "εμ", "n": "εν",
                 "o": "όου", "p": "πι", "q": "κιου", "r": "αρ", "s": "ες", "t": "τι", "u": "γιου",
                 "v": "βι", "w": "ντάμπλιου", "x": "εξ", "y": "ουάι", "z": "ζεντ"}
# Greek acronyms read as words (lower case, with the stress they are said with).
ACRONYM_WORDS = {"οτε": "οτέ", "δεη": "δεή", "ερτ": "ερτ", "πασοκ": "πασόκ", "ασεπ": "ασέπ",
                 "οπαπ": "οπάπ", "νατο": "νάτο", "οηε": "οηέ", "εφκα": "εφκά", "κκε": "κουκουέ",
                 "ουεφα": "ουέφα", "φιφα": "φίφα", "αεκ": "αεκ", "παοκ": "παόκ", "εοκ": "εοκ",
                 "ναυτεμπορικη": "ναυτεμπορική", "οσε": "οσέ", "ικα": "ικά", "εμπ": "εμπ"}
ABBREVIATIONS = {
    "π.χ.": "παραδείγματος χάρη", "κ.λπ.": "και λοιπά", "κλπ.": "και λοιπά", "κ.λ.π.": "και λοιπά",
    "κτλ.": "και τα λοιπά", "κ.ά.": "και άλλα", "δηλ.": "δηλαδή", "π.Χ.": "προ Χριστού",
    "μ.Χ.": "μετά Χριστόν", "π.μ.": "προ μεσημβρίας", "μ.μ.": "μετά μεσημβρίαν",
    "αι.": "αιώνας", "τηλ.": "τηλέφωνο", "Τηλ.": "τηλέφωνο", "σελ.": "σελίδα", "βλ.": "βλέπε",
    "Βλ.": "βλέπε", "οδ.": "οδός", "Οδ.": "οδός", "αρ.": "αριθμός", "Αρ.": "αριθμός",
    "εκατ.": "εκατομμύρια", "δισ.": "δισεκατομμύρια", "χιλ.": "χιλιάδες", "κ.": "κύριος",
    "Κ.": "κύριος", "κα": "κυρία", "Δρ": "δόκτωρ", "Α.Ε.": "ανώνυμη εταιρεία",
    "ΗΠΑ": "ηνωμένες πολιτείες", "Η.Π.Α.": "ηνωμένες πολιτείες", "ΕΕ": "ευρωπαϊκή ένωση",
    "Ε.Ε.": "ευρωπαϊκή ένωση", "λεωφ.": "λεωφόρος", "Λεωφ.": "λεωφόρος",
}
# Units after a number: (singular, plural, gender).
UNITS = {"km/h": ("χιλιόμετρο την ώρα", "χιλιόμετρα την ώρα", "n"),
         "km": ("χιλιόμετρο", "χιλιόμετρα", "n"), "χλμ.": ("χιλιόμετρο", "χιλιόμετρα", "n"),
         "χλμ": ("χιλιόμετρο", "χιλιόμετρα", "n"), "m": ("μέτρο", "μέτρα", "n"),
         "μ.": ("μέτρο", "μέτρα", "n"), "cm": ("εκατοστό", "εκατοστά", "n"),
         "εκ.": ("εκατοστό", "εκατοστά", "n"), "mm": ("χιλιοστό", "χιλιοστά", "n"),
         "τ.μ.": ("τετραγωνικό μέτρο", "τετραγωνικά μέτρα", "n"),
         "kg": ("κιλό", "κιλά", "n"), "κιλ.": ("κιλό", "κιλά", "n"),
         "g": ("γραμμάριο", "γραμμάρια", "n"), "γρ.": ("γραμμάριο", "γραμμάρια", "n"),
         "mg": ("χιλιοστόγραμμο", "χιλιοστόγραμμα", "n"), "l": ("λίτρο", "λίτρα", "n"),
         "L": ("λίτρο", "λίτρα", "n"), "ml": ("χιλιοστόλιτρο", "χιλιοστόλιτρα", "n"),
         "h": ("ώρα", "ώρες", "f"), "min": ("λεπτό", "λεπτά", "n"),
         "s": ("δευτερόλεπτο", "δευτερόλεπτα", "n"), "GB": ("γκιγκαμπάιτ", "γκιγκαμπάιτ", "n"),
         "MB": ("μεγκαμπάιτ", "μεγκαμπάιτ", "n"), "TB": ("τεραμπάιτ", "τεραμπάιτ", "n"),
         "kWh": ("κιλοβατώρα", "κιλοβατώρες", "f"), "kW": ("κιλοβάτ", "κιλοβάτ", "n"),
         "W": ("βατ", "βατ", "n"), "V": ("βολτ", "βολτ", "n"),
         "mAh": ("μιλιαμπερώριο", "μιλιαμπερώρια", "n"), "GHz": ("γιγαχέρτζ", "γιγαχέρτζ", "n"),
         "MHz": ("μεγαχέρτζ", "μεγαχέρτζ", "n"), "°C": ("βαθμός Κελσίου", "βαθμοί Κελσίου", "m"),
         "℃": ("βαθμός Κελσίου", "βαθμοί Κελσίου", "m"), "°": ("βαθμός", "βαθμοί", "m")}
CURRENCY = {"€": ("ευρώ", "ευρώ", "n"), "EUR": ("ευρώ", "ευρώ", "n"),
            "US$": ("δολάριο", "δολάρια", "n"), "$": ("δολάριο", "δολάρια", "n"),
            "£": ("λίρα", "λίρες", "f"), "¥": ("γιεν", "γιεν", "n")}
# Plain Latin words of the tables: lang.py tags them Greek in mode "el" (5 km, 10 GB), so they are
# read here with their number; single letters stay English.
LATIN_WORDS = frozenset(k for k in (*UNITS, *CURRENCY)
                        if len(k) > 1 and k.isascii() and k.isalpha())
SYMBOLS = {"&": " και ", "+": " συν ", "=": " ίσον ", "@": " παπάκι ", "#": " δίεση ",
           "×": " επί ", "%": " τοις εκατό ", "°": " βαθμοί ", "/": " "}
MARK_WORDS = {",": "κόμμα", ".": "τελεία"}

NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?"
_A = r"(?<![\w.,])"
_NEXT = r"(?:\s*(?=([^\W\d_]+)))?"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
DATE_DMY = re.compile(r"(?<![\d/.-])(\d{1,2})([/.-])(\d{1,2})\2(\d{4}|\d{2})(?![\d/-]|[.,]\d)")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:])"
                  r"|(?<=στις )([01]?\d|2[0-4])\.([0-5]\d)(?![\d]|[.,]\d)")
PHONE = re.compile(r"(?<![\d.,])(?:\+\d{1,3}[\s-]?)?(?:\d{3,5}(?:[\s-]\d{2,7}){1,3}|(?:2|69)\d{8,9}"
                   r"|0\d{9,11})(?![\d.,])")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")")
MONEY_AFTER = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _CUR_KEYS + r")(?![\w])")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(r"(?<![\w.,])(\d+)(?:-?)(" + "|".join(sorted({*ORD_ENDINGS, *ACCENTED.values()},
                                                                 key=len, reverse=True))
                     + r")(?![\w])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])" + _NEXT)
LATIN = re.compile(r"[A-Za-zÀ-ɏ](?:[A-Za-zÀ-ɏ'-]*[A-Za-zÀ-ɏ])?")
GREEK_CAPS = re.compile(r"(?<![\w])[Α-ΩΆΈΉΊΌΎΏΪΫ]{2,5}(?![\w])")
WORD = re.compile(r"[^\W\d_](?:[^\W\d_]|[\u0300-\u036f])*(?:'[^\W\d_]+)*|[,.?!;:]")
MARKS = ",.?!;:"


def _plain(w: str) -> str:
    """Base letters without accents (NFD of each character, combining marks dropped)."""
    return "".join(decompose(c)[0] for c in w if not "\u0300" <= c <= "\u036f")


def gender_of(word: str | None) -> str:
    """Guessed gender of the noun after a number: "n", "m" or "f"."""
    if not word:
        return "n"
    w = lower(word)
    plain = _plain(w)
    if w in FEMININE_WORDS or plain.endswith(("ες", "εις")):
        return "f"
    if plain.endswith(("οι", "ους", "ος", "ης", "ας")):
        return "m"
    return "n"


def _below_100(n: int, g: str) -> str:
    if n < 10:
        return ONES[g][n]
    if n < 20:
        return TEENS[g][n - 10]
    t, u = divmod(n, 10)
    return TENS[t] + (f" {ONES[g][u]}" if u else "")


def _below_1000(n: int, g: str) -> str:
    h, r = divmod(n, 100)
    parts = []
    if h == 1:
        parts.append("εκατόν" if r else "εκατό")
    elif h:
        parts.append(HUNDRED_STEMS[h] + GENDER_END[g])
    if r or not h:
        parts.append(_below_100(r, g))
    return " ".join(parts)


def _below_million(n: int, g: str) -> str:
    th, r = divmod(n, 1000)
    parts = []
    if th == 1:
        parts.append(THOUSAND[g])
    elif th:
        parts.append(_below_1000(th, "f") + " χιλιάδες")
    if r or not th:
        parts.append(_below_1000(r, g))
    return " ".join(parts)


def cardinal(n: int, g: str = "n") -> str:
    """Greek cardinal in gender g (n, m, f): 3 -> τρία / τρεις, 21 -> είκοσι ένα, 100 -> εκατό,
    101 -> εκατόν ένα, 2000 -> δύο χιλιάδες, 3000 -> τρεις χιλιάδες, 2_000_000 -> δύο
    εκατομμύρια."""
    if n < 0:
        return "μείον " + cardinal(-n, g)
    if n >= 10 ** 15:
        return " ".join(DIGITS[int(c)] for c in str(n))
    parts = []
    for scale, one, many in SCALES:
        q, n = divmod(n, scale)
        if q == 1:
            parts.append(one)
        elif q:
            parts.append(f"{cardinal(q)} {many}")
    if n or not parts:
        parts.append(_below_million(n, g))
    return " ".join(parts)


def _ord_word(stem_acc: tuple[str, bool], ending: str) -> str:
    stem, oxytone = stem_acc
    return stem + (ACCENTED[ending] if oxytone else ending)


def ordinal(n: int, ending: str = "ος") -> str:
    """Greek ordinal with an ending of ος (masculine), η (feminine), ο (neuter) or another case
    ending: 1 -> πρώτος, 3 + η -> τρίτη, 20 -> εικοστός, 21 -> εικοστός πρώτος; from 1000 the
    cardinal."""
    plain = {v: k for k, v in ACCENTED.items()}.get(ending, ending)
    if not 1 <= n <= 999:
        return cardinal(n)
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts.append(_ord_word((ORD_HUNDREDS[h], True), plain))
    if r in ORD_TEENS:
        parts.append(_ord_word(ORD_TEENS[r], plain))
    else:
        t, u = divmod(r, 10)
        if t == 1:
            parts.append(_ord_word(ORD_TEENS[10], plain))
        elif t:
            parts.append(_ord_word((ORD_TENS[t], True), plain))
        if u:
            parts.append(_ord_word(ORD_ONES[u], plain))
    return " ".join(parts)


def number(s: str, g: str = "n") -> str:
    """A written number: the dot groups thousands, the comma is the decimal mark (κόμμα); decimals
    of one or two digits without a leading zero are read as a number, else digit by digit."""
    neg = s.startswith("-")
    n, frac, _ = parse_number(s.lstrip("-"))
    out = cardinal(n, g if frac is None else "n")
    if frac is not None:
        if len(frac) <= 2 and not frac.startswith("0"):
            out += f" κόμμα {cardinal(int(frac))}"
        else:
            out += " κόμμα " + " ".join(DIGITS[int(c)] for c in frac)
    return ("μείον " if neg else "") + out


def _is_one(s: str) -> bool:
    n, frac, _ = parse_number(s.lstrip("-"))
    return n == 1 and frac is None


def _day(d: int) -> str:
    return "πρώτη" if d == 1 else cardinal(d, "f")


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{_day(d)} {MONTHS[m]}"
    if y is not None:
        out += f" {cardinal(int(y) + (2000 if len(y) == 2 else 0))}"
    return f" {out} "


def _time(m: re.Match) -> str:
    h = m.group(1) or m.group(4)
    mi = m.group(2) or m.group(5)
    sec = m.group(3)
    out = cardinal(int(h), "f")
    if int(mi):
        out += f" και {cardinal(int(mi))}"
    if sec and int(sec):
        out += f" και {cardinal(int(sec))} δευτερόλεπτα"
    return f" {out} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    one, many, g = UNITS[unit]
    return f" {number(sign + num, g)} {one if _is_one(num) else many} "


def _money(num: str, cur: str, sign: str = "") -> str:
    one, many, g = CURRENCY[cur]
    n, frac, _ = parse_number(num)
    if frac is not None and len(frac) == 2 and cur in ("€", "EUR"):
        out = f"{cardinal(n)} ευρώ"
        if int(frac):
            out += f" και {cardinal(int(frac))} {'λεπτό' if int(frac) == 1 else 'λεπτά'}"
        return f" {'μείον ' if sign else ''}{out} "
    return f" {number(sign + num, g)} {one if _is_one(num) else many} "


def _number(m: re.Match) -> str:
    sign, num, nxt = m.groups()
    g = gender_of(nxt)
    if nxt and lower(nxt) in MONTHS and parse_number(num)[0] == 1:
        return " πρώτη "
    return f" {number(sign + num, g)} "


def _spell(code: str) -> str:
    out = []
    for ch in code:
        if ch.isdigit():
            out.append(DIGITS[int(ch)])
        elif ch.lower() in LATIN_LETTERS:
            out.append(LATIN_LETTERS[ch.lower()])
        elif lower(ch) in GREEK_LETTERS:
            out.append(GREEK_LETTERS[lower(ch)])
    return " ".join(out)


def _greek_caps(m: re.Match) -> str:
    w = m.group(0)
    plain = _plain(lower(w))
    if plain in ACRONYM_WORDS:
        return ACRONYM_WORDS[plain]
    return " ".join(GREEK_LETTERS[c] for c in plain if c in GREEK_LETTERS)


def _latin(m: re.Match) -> str:
    from ..en.normalize_en import normalize_en

    folded = "".join(c for c in unicodedata.normalize("NFKD", m.group(0)) if c.isascii())
    return f" {normalize_en(folded)} "


def _abbreviations(t: str) -> str:
    for key in sorted(ABBREVIATIONS, key=len, reverse=True):
        tail = "" if key.endswith(".") else r"(?![\w])"
        t = re.sub(r"(?<![\w.])" + re.escape(key) + tail, f" {ABBREVIATIONS[key]} ", t)
    return t


def normalize_el(text: str) -> str:
    t = text.replace(";", "?").replace(";", "?").replace("·", ";").replace("·", ";")
    t = UNIT.sub(_unit, t)
    t = _abbreviations(t)
    t = t.translate({ord(c): " " for c in DROP})
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(3)), m.group(4)) or m.group(0), t)
    t = TIME.sub(_time, t)
    t = PHONE.sub(lambda m: phone_digits(m.group(0), DIGITS, "συν"), t)
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(2), m.group(3), m.group(1)), t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} τοις εκατό ", t)
    t = ORDINAL.sub(lambda m: f" {ordinal(int(m.group(1)), m.group(2))} ", t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} έως {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {_spell(m.group(0))} ", t)
    t = NUMBER.sub(_number, t)
    words = [w for w in re.findall(r"[^\W\d_]{2,}", t)]
    # not a text in capitals (a word is in capitals when every letter has a lower-case form)
    if sum(all(c.lower() != c for c in w) for w in words) * 2 <= len(words):
        t = GREEK_CAPS.sub(lambda m: f" {_greek_caps(m)} ", t)
    t = LATIN.sub(_latin, t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ").replace("–", " ")
    out: list[str] = []
    for w in WORD.findall(lower(t)):
        if w in MARKS and out and out[-1] in MARKS:
            continue
        out.append(w)
    return " ".join(out)
