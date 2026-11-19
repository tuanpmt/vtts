"""French text normalization for one French run, with liaison.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces. Accents and apostrophes are kept (l'école, aujourd'hui).

Rules, in order: typographic apostrophe, abbreviations (M., Mme, Dr, etc., J.-C., qqn, svp),
quotes and brackets dropped, ordinals (1er, 1re, 2e, 2nd, XIXe; Louis XIV and François Ier read as
a cardinal / premier), dates (14/07/1789, 2026-11-19; day 1 is "premier"), times (14 h 30, 14h30,
14:30, 8 h -> huit heures), phone numbers (06 12 34 56 78 and +33 6 ... read in pairs: zéro six,
douze ...), numbers grouped with spaces (10 000), money (12,50 € -> douze euros cinquante, 1 000
000 € -> un million d'euros, $, £, CHF), percentages, units after a number (5 km, 25 °C, 8 Go),
ranges (10-20 -> dix à vingt), product codes (ESP32: letters by French name, digits one by one),
numbers (soixante-dix, quatre-vingts, vingt et un, une before a feminine noun), symbols, inverted
verbs (a-t-il, dit-il, allez-y), hyphens, acronyms (spelled: SNCF -> èss èn cé èf; a few read as
words: ONU, OTAN, UNESCO).

Liaison (_sandhi, after the words are split): a word that links (les, des, un, mon, on, nous, ils,
deux, trois, six, dix, vingt, cent, petit, grand, en, dans, chez, sans, très, quand, tout, est,
sont ...) before a word starting with a vowel or a silent h gives its consonant to that word,
written before an apostrophe (les amis -> les z'amis, un ami -> un n'ami, petit enfant -> petit
t'enfant), which g2p_fr reads as a consonant. h aspiré words (haricot, héros, hasard, hors ...),
onze, oui, huit, yaourt block it. bon, ancien, certain, plein, prochain, moyen are denasalized
(bon ami -> bonne ami). Numbers: six, dix (sis) lose their s before a consonant (six mois) and
link with z (six ans, dix-huit, dix-neuf); huit loses its t before a consonant; vingt keeps its t
in 21-29 (vingt-deux) but not in quatre-vingt-deux; neuf links with v before ans and heures.
tous at the end of a phrase is read with s.
"""

from __future__ import annotations

import re

from ..latin_norm import DROP, PAUSE, PRODUCT_CODE, digits, parse_number, read_number, spell

ONES = ("zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
        "onze", "douze", "treize", "quatorze", "quinze", "seize")
TENS = ("", "dix", "vingt", "trente", "quarante", "cinquante", "soixante", "soixante",
        "quatre-vingt", "quatre-vingt")
DIGITS = ONES[:10]
MONTHS = ("", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre")
LETTERS = {"a": "a", "b": "bé", "c": "cé", "d": "dé", "e": "eu", "f": "èf", "g": "gé",
           "h": "hache", "i": "i", "j": "ji", "k": "ka", "l": "èl", "m": "èm", "n": "èn", "o": "o",
           "p": "pé", "q": "ku", "r": "èr", "s": "èss", "t": "té", "u": "u", "v": "vé",
           "w": "double vé", "x": "ixe", "y": "i grec", "z": "zède"}
ACRONYM_WORDS = frozenset(("onu", "otan", "unesco", "nasa", "fifa", "uefa", "sida", "ovni",
                           "insee", "ena", "cac", "ram", "rom", "led", "pin", "cnil", "inserm",
                           "cnrs", "isf", "smic", "pacs", "ong", "covid"))
ACRONYM_WORDS = ACRONYM_WORDS - {"cnrs", "isf", "ong"}  # spelled
ABBREVIATIONS = {
    "M.": "monsieur", "MM.": "messieurs", "Mme": "madame", "Mmes": "mesdames",
    "Mlle": "mademoiselle", "Mlles": "mesdemoiselles", "Dr": "docteur", "Dr.": "docteur",
    "Pr": "professeur", "Pr.": "professeur", "St": "saint", "Ste": "sainte",
    "etc.": "et cetera", "cf.": "confer", "av. J.-C.": "avant jésus-christ",
    "apr. J.-C.": "après jésus-christ", "ap. J.-C.": "après jésus-christ", "J.-C.": "jésus-christ",
    "n°": "numéro", "N°": "numéro", "nº": "numéro", "tél.": "téléphone", "env.": "environ",
    "av.": "avenue", "bd": "boulevard", "Bd": "boulevard", "c.-à-d.": "c'est-à-dire",
    "càd": "c'est-à-dire", "p. ex.": "par exemple", "ex.": "exemple", "Cie": "compagnie",
    "qqn": "quelqu'un", "qqch": "quelque chose", "svp": "s'il vous plaît",
    "SVP": "s'il vous plaît", "stp": "s'il te plaît", "vs": "contre",
}
# Units after a number: (singular, plural, feminine).
UNITS = {"km/h": ("kilomètre heure", "kilomètres heure", False),
         "km": ("kilomètre", "kilomètres", False), "m": ("mètre", "mètres", False),
         "cm": ("centimètre", "centimètres", False), "mm": ("millimètre", "millimètres", False),
         "m²": ("mètre carré", "mètres carrés", False), "m³": ("mètre cube", "mètres cubes", False),
         "km²": ("kilomètre carré", "kilomètres carrés", False),
         "ha": ("hectare", "hectares", False),
         "kg": ("kilo", "kilos", False), "g": ("gramme", "grammes", False),
         "mg": ("milligramme", "milligrammes", False), "t": ("tonne", "tonnes", True),
         "l": ("litre", "litres", False), "L": ("litre", "litres", False),
         "ml": ("millilitre", "millilitres", False), "cl": ("centilitre", "centilitres", False),
         "min": ("minute", "minutes", True), "s": ("seconde", "secondes", True),
         "ms": ("milliseconde", "millisecondes", True),
         "Go": ("gigaoctet", "gigaoctets", False), "Mo": ("mégaoctet", "mégaoctets", False),
         "GB": ("gigaoctet", "gigaoctets", False), "MB": ("mégaoctet", "mégaoctets", False),
         "kWh": ("kilowattheure", "kilowattheures", False),
         "kW": ("kilowatt", "kilowatts", False), "W": ("watt", "watts", False),
         "V": ("volt", "volts", False), "mAh": ("milliampère heure", "milliampères heure", False),
         "GHz": ("gigahertz", "gigahertz", False), "MHz": ("mégahertz", "mégahertz", False),
         "°C": ("degré", "degrés", False), "℃": ("degré", "degrés", False),
         "°": ("degré", "degrés", False)}
CURRENCY = {"€": ("euro", "euros", "centime", "centimes"),
            "EUR": ("euro", "euros", "centime", "centimes"),
            "$": ("dollar", "dollars", "cent", "cents"), "US$": ("dollar", "dollars", "cent", "cents"),
            "£": ("livre", "livres", "penny", "pence"),
            "CHF": ("franc suisse", "francs suisses", "centime", "centimes"),
            "¥": ("yen", "yens", "", "")}
SYMBOLS = {"&": " et ", "+": " plus ", "=": " égale ", "@": " arobase ", "#": " dièse ",
           "×": " fois ", "/": " sur ", "%": " pour cent ", "§": " paragraphe "}
MARK_WORDS = {",": "virgule", ".": "point"}
# Feminine nouns counted after a number: 1, 21, 31 ... read une (une heure, vingt et une pages).
FEMININE = frozenset((
    "heure", "heures", "minute", "minutes", "seconde", "secondes", "fois", "personne", "personnes",
    "semaine", "semaines", "année", "années", "journée", "journées", "nuit", "nuits", "page",
    "pages", "voiture", "voitures", "chose", "choses", "femme", "femmes", "fille", "filles",
    "étoile", "étoiles", "tonne", "tonnes", "ville", "villes", "place", "places", "chambre",
    "chambres", "pièce", "pièces", "partie", "parties", "photo", "photos", "image", "images",
    "question", "questions", "réponse", "réponses", "étape", "étapes", "saison", "saisons",
    "édition", "éditions", "équipe", "équipes", "victoire", "victoires", "langue", "langues",
    "classe", "classes", "fois", "livre", "livres", "voix", "lettre", "lettres", "ligne", "lignes",
    "rue", "rues", "porte", "portes", "table", "tables", "maison", "maisons", "entreprise",
    "entreprises", "espèce", "espèces", "région", "régions", "commune", "communes", "chanson",
    "chansons", "minute", "élève", "élèves", "version", "versions", "tasse", "tasses",
    "bouteille", "bouteilles", "mille", "centaine", "dizaine",
))
FEMININE = FEMININE - {"mille", "livre", "livres"}

_A = r"(?<![\w.,])"
_SP = "[   ]"
NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
GROUPED = re.compile(rf"(?<![\d.,])\d{{1,3}}(?:{_SP}\d{{3}})+(?![\d])")
DATE_DMY = re.compile(r"(?<![\d/.])(\d{1,2})[/.](\d{1,2})[/.](\d{4}|\d{2})(?![\d/])")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
TIME = re.compile(r"(?<![\d:,.])([01]?\d|2[0-4])\s?(?:h|:)\s?([0-5]\d)(?::([0-5]\d))?"
                  r"(?:\s?min(?![\w]))?(?![\d:])"
                  r"|(?<![\w:.,])([01]?\d|2[0-4])\s?h(?![\w])")
PHONE = re.compile(r"(?<![\d+])(?:\+33\s?(?:\(0\)\s?)?|0033\s?|0)[1-9](?:[\s.-]?\d{2}){4}(?![\d])")
# Other international numbers: + country code, then at least six digits (single separators).
PHONE_OTHER = re.compile(r"(?<![\d])\+\d{1,3}(?:[\s.-]?\d){6,}(?![\d])")
# Scale words after an amount, in the order the alternations try them.
SCALES_BEFORE = ("millions", "million", "milliards", "milliard")
SCALES_AFTER = (*SCALES_BEFORE, "mille")
MONEY_AFTER_KEYS = ("€", "EUR", "CHF", "£", "¥", "$")
MONEY_BEFORE = re.compile(r"(" + _CUR_KEYS + r")\s?(" + NUM + r")(\s?(?:" + "|".join(SCALES_BEFORE)
                          + r")(?![\w]))?")
MONEY_AFTER = re.compile(_A + r"(" + NUM + r")(\s?(?:" + "|".join(SCALES_AFTER) + r")(?![\w]))?\s?("
                         + "|".join(re.escape(k) for k in MONEY_AFTER_KEYS) + r")(?![\w])")
PERCENT = re.compile(_A + r"(-?)(" + NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w²³])")
ORDINAL = re.compile(_A + r"(\d+)(er|re|ère|ers|res|ères|e|es|ème|èmes|nd|nde|nds|ndes|d|de)(?![\w])")
ROMAN_ORDINAL = re.compile(r"(?<![\w])([IVXLC]+)(er|re|e|ème)(?![\w])")
# A Roman numeral after a capitalized word (Louis XIV, Henri IV, Chapitre V): a cardinal.
ROMAN_NAME = re.compile(r"(?<![\w'])([A-ZÉ][a-zàâçéèêëîïôûùüÿ]+) ([IVX]{2,5}|V|X)(?![\w'])")
RANGE = re.compile(_A + r"(\d+)\s?[-–]\s?(\d+)(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + NUM + r")(?![\d])(?:\s+([^\W\d_]+))?")
ACRONYM = re.compile(r"(?<![\w'])[A-Z]{2,5}(?![\w'])")
INVERSION_T = re.compile(r"-t-(?=(?:il|elle|on|ils|elles)(?![\w]))", re.IGNORECASE)
INVERSION = re.compile(r"(?<=[tdTD])-(?=(?:il|elle|on|ils|elles)(?![\w]))", re.IGNORECASE)
IMPERATIVE = re.compile(r"(?<=[sz])-(?=(?:y|en)(?![\w]))", re.IGNORECASE)
WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*'?|[,.?!;:]")
MARKS = ",.?!;:"


# ---------------- numbers ----------------

def _below_100(n: int) -> str:
    if n <= 16:
        return ONES[n]
    if n < 20:
        return "dix-" + ONES[n - 10]
    t, u = divmod(n, 10)
    if t in (7, 9):
        rest = n - (t - 1) * 10
        return TENS[t] + (" et onze" if rest == 11 and t == 7 else "-" + _below_100(rest))
    if t == 8:
        return "quatre-vingts" if u == 0 else "quatre-vingt-" + ONES[u]
    if u == 0:
        return TENS[t]
    if u == 1:
        return TENS[t] + " et un"
    return TENS[t] + "-" + ONES[u]


def _below_1000(n: int, last: bool = True) -> str:
    """0 < n < 1000; last: nothing follows but a noun (quatre-vingts, deux cents get their s)."""
    h, r = divmod(n, 100)
    if h == 0:
        out = _below_100(r)
    else:
        out = "cent" if h == 1 else f"{ONES[h]} cent"
        if r:
            out += " " + _below_100(r)
        elif h > 1 and last:
            out += "s"
    if not last and out.endswith("quatre-vingts"):
        out = out[:-1]
    return out


def cardinal(n: int) -> str:
    """French cardinal (masculine): 21 -> vingt et un, 71 -> soixante et onze, 80 ->
    quatre-vingts, 81 -> quatre-vingt-un, 200 -> deux cents, 201 -> deux cent un, 1000 -> mille,
    80 000 -> quatre-vingt mille, 2 000 000 -> deux millions."""
    if n < 0:
        return "moins " + cardinal(-n)
    if n == 0:
        return "zéro"
    if n >= 10 ** 15:
        return digits(str(n), DIGITS)
    words: list[str] = []
    for scale, name in ((10 ** 12, "billion"), (10 ** 9, "milliard"), (10 ** 6, "million")):
        q, n = divmod(n, scale)
        if q:
            words.append(f"{_below_1000(q)} {name}{'s' if q > 1 else ''}")
    q, n = divmod(n, 1000)
    if q:
        words.append("mille" if q == 1 else f"{_below_1000(q, last=False)} mille")
    if n:
        words.append(_below_1000(n))
    return " ".join(words)


def feminine(words: str) -> str:
    """un -> une at the end (vingt et une, quatre-vingt-une)."""
    return re.sub(r"\bun$", "une", words)


def ordinal(n: int, fem: bool = False) -> str:
    """1 -> premier / première, 2 -> deuxième, 21 -> vingt et unième, 80 -> quatre-vingtième."""
    if n == 1:
        return "première" if fem else "premier"
    words = cardinal(n)
    head, sep, last = words.rpartition(" ")
    pre, dash, last = last.rpartition("-")
    if last == "cinq":
        last = "cinquième"
    elif last == "neuf":
        last = "neuvième"
    elif last in ("cents", "vingts") or last.endswith("e"):
        last = last[:-1] + "ième"
    else:
        last += "ième"
    return head + sep + pre + dash + last


def number(s: str) -> str:
    """A written number (decimal comma or point)."""
    return ("moins " if s.startswith("-") else "") + read_number(s.lstrip("-"), cardinal,
                                                                  MARK_WORDS, DIGITS)


def _count(s: str) -> tuple[str, bool]:
    n, frac, _ = parse_number(s)
    return number(s), n <= 1 and frac is None


def _number_noun(m: re.Match) -> str:
    sign, num, noun = m.groups()
    words = number(sign + num)
    _, frac, _ = parse_number(num)
    if noun and frac is None and noun.lower() in FEMININE:
        words = feminine(words)
    return f" {words} {noun or ''} "


def _roman(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for k, ch in enumerate(s):
        v = vals[ch]
        total += -v if k + 1 < len(s) and vals[s[k + 1]] > v else v
    return total


def _date(d: int, m: int, y: str | None) -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    out = f"{'premier' if d == 1 else cardinal(d)} {MONTHS[m]}"
    if y is not None:
        out += f" {cardinal(int(y) + (2000 if len(y) == 2 else 0))}"
    return f" {out} "


def _time(m: re.Match) -> str:
    if m.group(4) is not None:
        h, mi, sec = int(m.group(4)), 0, 0
    else:
        h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    out = f"{feminine(cardinal(h))} {'heure' if h <= 1 else 'heures'}"
    if mi:
        out += f" {feminine(cardinal(mi))}"
    if sec:
        out += f" et {feminine(cardinal(sec))} {'seconde' if sec == 1 else 'secondes'}"
    return f" {out} "


def _phone(m: re.Match) -> str:
    """French numbers in pairs (06 12 34 56 78 -> zéro six douze trente-quatre ...)."""
    s = m.group(0)
    ds = "".join(c for c in s if c.isdigit())
    out = []
    if s.startswith(("+33", "0033")):
        out.append("plus trente-trois")
        ds = ds[2:] if s.startswith("+") else ds[4:]
        ds = ds.removeprefix("0")
        out.append(ONES[int(ds[0])])
        ds = ds[1:]
    for k in range(0, len(ds), 2):
        pair = ds[k:k + 2]
        out.append(f"zéro {ONES[int(pair[1])]}" if pair[0] == "0" and len(pair) == 2
                   else cardinal(int(pair)))
    return " " + " ".join(out) + " "


def _phone_other(m: re.Match) -> str:
    s = m.group(0)
    return f" plus {digits(s, DIGITS)} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    words, one = _count(num)
    sing, plural, fem = UNITS[unit]
    if fem and one:
        words = feminine(words)
    return f" {'moins ' if sign else ''}{words} {sing if one else plural} "


def _money(num: str, cur: str, scale: str | None = None) -> str:
    """12,50 € -> douze euros cinquante; 1,5 million € -> un virgule cinq million d'euros."""
    sing, plural, cent1, cents = CURRENCY[cur]
    words, one = _count(num)
    if scale:
        scale = scale.strip()
        if scale == "mille":
            return f" {words} mille {plural} "
        return f" {words} {scale} {_de(plural)} "
    n, frac, _ = parse_number(num)
    if frac is not None and len(frac) == 2 and cent1:
        c = int(frac)
        if n == 0:
            return f" {cardinal(c)} {cent1 if c == 1 else cents} "
        out = f"{cardinal(n)} {sing if n == 1 else plural}"
        if c:
            out += f" {cardinal(c)}"
        return f" {out} "
    if frac is None and n >= 10 ** 6 and n % 10 ** 6 == 0:  # un million d'euros
        return f" {words} {_de(plural)} "
    return f" {words} {sing if one else plural} "


def _de(noun: str) -> str:
    """de + noun with elision (d'euros, de dollars)."""
    return f"d'{noun}" if noun[0] in "aeiouyé" else f"de {noun}"


def _ordinal(m: re.Match) -> str:
    n, suffix = int(m.group(1)), m.group(2)
    if suffix.startswith("n") or suffix in ("d", "de", "ds", "des"):
        if n == 2:
            return " seconde " if "e" in suffix else " second "
        return f" {ordinal(n)} "
    return f" {ordinal(n, fem=suffix.startswith(('r', 'è')))} "


def _roman_ordinal(m: re.Match) -> str:
    if m.group(1) in ("L", "C", "LI", "CI", "VI", "MI") and m.group(2) == "e":
        return m.group(0)  # Le, Ce, Vie ... are words
    n, suffix = _roman(m.group(1)), m.group(2)
    return f" {ordinal(n, fem=suffix == 're')} "


def _roman_name(m: re.Match) -> str:
    return f"{m.group(1)} {cardinal(_roman(m.group(2)))} "


def _apply_abbreviations(text: str) -> str:
    for key in sorted(ABBREVIATIONS, key=len, reverse=True):
        tail = "" if key.endswith(".") else r"(?![\w])"
        reading = ABBREVIATIONS[key]

        def sub(m: re.Match, reading=reading, key=key) -> str:
            end = key.endswith(".") and not m.string[m.end():].strip()
            return f" {reading} {'.' if end else ''}"

        lead = r"(?<![\w'])" if key[0].isalnum() else ""
        text = re.sub(lead + re.escape(key) + tail, sub, text)
    return text


def _acronyms(text: str) -> str:
    def sub(m: re.Match) -> str:
        w = m.group(0)
        return w.lower() if w.lower() in ACRONYM_WORDS else " " + spell(w, LETTERS, ()) + " "
    return ACRONYM.sub(sub, text)


# ---------------- liaison ----------------

LIAISON = {
    **dict.fromkeys(("les", "des", "ces", "mes", "tes", "ses", "nos", "vos", "leurs", "aux",
                     "quels", "quelles", "lesquels", "lesquelles", "desquels", "desquelles",
                     "auxquels", "auxquelles", "plusieurs", "quelques", "certains", "certaines",
                     "divers", "diverses", "différents", "différentes", "nous", "vous", "ils",
                     "elles", "deux", "trois", "six", "dix", "vingts", "cents", "mauvais", "gros",
                     "grands", "grandes", "petits", "petites", "beaux", "belles", "nouveaux",
                     "nouvelles", "vieux", "vieilles", "anciens", "anciennes", "autres", "bons",
                     "bonnes", "premiers", "premières", "derniers", "dernières", "jeunes", "dans",
                     "chez", "sans", "sous", "très", "plus", "moins", "aucuns", "mêmes", "toutes",
                     "tous", "hauts", "longs", "faux", "doux"), "z"),
    **dict.fromkeys(("un", "aucun", "mon", "ton", "son", "en", "on", "bien"), "n"),
    **dict.fromkeys(("petit", "grand", "tout", "quand", "vingt", "cent", "est", "sont"), "t"),
    **dict.fromkeys(("trop", "beaucoup"), "p"),
    **dict.fromkeys(("premier", "dernier", "léger", "entier"), "r"),
}
# Before a vowel these adjectives are read like their feminine (bon ami -> bonne ami).
DENASAL = {"bon": "bonne", "ancien": "ancienne", "moyen": "moyenne", "certain": "certaine",
           "plein": "pleine", "prochain": "prochaine", "vilain": "vilaine", "divin": "divine"}
# Words starting with a vowel sound that block liaison; words with an h aspiré.
NO_LIAISON = frozenset(("onze", "onzième", "oui", "ouistiti", "ouate", "yaourt", "yaourts",
                        "yacht", "yachts", "yoga", "yeti", "york", "uhlan", "huit", "huitième",
                        "huitièmes", "et"))
H_ASPIRE = frozenset(["hache", "haie", "haine", "haïr", "hall", "halte", "hamac", "hameau", "hamburger", "hanche", "handicap", "handball", "hangar", "hanter", "happer", "harceler", "hardi", "hareng", "haricot", "harpe", "hasard", "hâte", "hausse", "haut", "haute", "hauteur", "hautbois", "havre", "hennir", "hérisson", "hernie", "héron", "héros", "hêtre", "heurt", "heurter", "hibou", "hideux", "hiérarchie", "hippie", "hisser", "hobby", "hockey", "hollande", "hollandais", "homard", "hongrie", "hongrois", "honte", "honteux", "hoquet", "horde", "hors", "hotte", "houblon", "houle", "housse", "houx", "hublot", "huer", "huée", "hurler", "hussard", "hutte", "hamster", "hall", "halle", "hamsters", "harpon", "hausser", "hachis", "haricots", "héros", "hiboux", "homards", "hors-la-loi"])
NUMBER_WORDS = frozenset(ONES[1:] + ("vingt", "vingts", "trente", "quarante", "cinquante",
                                     "soixante", "cent", "cents", "mille", "et"))
UNIT_WORDS = frozenset(("un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf"))
PREPOSITIONS = frozenset(("avec", "pour", "chez", "sans", "de", "à", "par", "entre", "contre",
                          "sur", "sous", "vers", "après", "avant", "comme", "derrière", "devant",
                          "selon", "malgré", "parmi", "envers"))
VOWEL_START = re.compile(r"^[aeiouyàâæéèêëîïôœùûüÿ]|^h[aeiouyàâæéèêëîïôœùûü]")


def _vowel_start(word: str) -> bool:
    """The word starts with a vowel sound that allows liaison (elided words never: l'ami)."""
    if "'" in word.rstrip("'"):
        return word.startswith("aujourd'")
    stem = word.rstrip("s")
    if word in NO_LIAISON or word in H_ASPIRE or stem in H_ASPIRE:
        return False
    if word.startswith("y") and word not in ("y", "yeux", "ypérite"):
        return False
    return bool(VOWEL_START.match(word))


def _sandhi(words: list[str]) -> list[str]:
    out = list(words)
    n = len(out)
    for k in range(n):
        w = out[k]
        nxt = out[k + 1] if k + 1 < n else ""
        prev = out[k - 1] if k > 0 else ""
        if nxt in MARKS:
            nxt = ""
        base = w.split("'")[-1]
        # numbers
        if base in ("six", "dix"):
            if base == "dix" and nxt in ("huit", "neuf", "huitième", "neuvième"):
                out[k] = w[:-1]  # dix-huit, dix-neuf: di z'huit
                out[k + 1] = "z'" + nxt
                continue
            if nxt in ("sept", "septième", "à", "et", "ou", "au", "aux") or not nxt:
                continue  # dix-sept, six à huit: sis, dis
            out[k] = w[:-1]  # six mois, dix jours; six ans -> si z'ans
            if _vowel_start(nxt):
                out[k + 1] = "z'" + nxt
            continue
        if base == "huit" and nxt and not _vowel_start(nxt) and nxt != "et":
            out[k] = w[:-1]  # huit jours
            continue
        if base == "vingt" and nxt in UNIT_WORDS | {"et"} and prev != "quatre":
            out[k + 1] = "t'" + nxt  # vingt-deux, vingt et un
            continue
        if base == "neuf" and nxt in ("ans", "heures", "hommes"):
            out[k + 1] = "v'" + nxt
            continue
        if base == "tous" and not nxt:
            out[k] = w[:-1] + "sse"  # ils sont tous.
            continue
        if base == "est" and prev in ("l'", "nord", "sud", "à") or w == "l'est":
            out[k] = w[:-3] + "èst"  # l'est, nord-est: the cardinal point
            continue
        if not nxt or "'" in nxt.rstrip("'") and nxt.split("'")[0] in ("z", "t", "n", "v", "r"):
            continue
        if not _vowel_start(nxt):
            continue
        if base in NUMBER_WORDS and nxt in ("un", "une", "onze"):
            continue
        if base in DENASAL:
            out[k] = w[:-len(base)] + DENASAL[base]
            continue
        if base in ("nous", "vous") and prev in PREPOSITIONS:
            continue  # avec nous au cinéma: an object of a preposition does not link
        if w in ("quelqu'un", "chacun"):
            continue
        cons = LIAISON.get(base)
        if cons:
            out[k + 1] = f"{cons}'{nxt}"
    return out


# ---------------- the whole run ----------------

def finish_fr(text: str) -> list[str]:
    """Lower-case words (apostrophes kept) and marks; a mark right after another is dropped."""
    out: list[str] = []
    for w in WORD.findall(text.lower()):
        if w in MARKS and out and out[-1] in MARKS:
            continue
        out.append(w)
    return out


def normalize_fr(text: str) -> str:
    t = text.replace("’", "'").replace("ʼ", "'").replace(" ", " ").replace(" ", " ")
    t = t.replace("ᵉʳ", "er").replace("ʳᵉ", "re").replace("ᵉ", "e").replace("ᵈ", "d")
    t = _apply_abbreviations(t)
    t = t.translate({ord(c): " " for c in DROP.replace("(", "").replace(")", "")})
    t = ROMAN_ORDINAL.sub(_roman_ordinal, t)
    t = ROMAN_NAME.sub(_roman_name, t)
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(2)), m.group(3)) or m.group(0), t)
    t = PHONE.sub(_phone, t)
    t = PHONE_OTHER.sub(_phone_other, t)
    t = TIME.sub(_time, t)
    t = GROUPED.sub(lambda m: re.sub(_SP, "", m.group(0)), t)
    t = t.replace("(", " ").replace(")", " ")
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1), m.group(3)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(3), m.group(2)), t)
    t = PERCENT.sub(lambda m: f" {number(m.group(1) + m.group(2))} pour cent ", t)
    t = UNIT.sub(_unit, t)
    t = ORDINAL.sub(_ordinal, t)
    t = RANGE.sub(lambda m: f" {cardinal(int(m.group(1)))} à {cardinal(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {spell(m.group(0), LETTERS, DIGITS)} ", t)
    t = NUMBER.sub(_number_noun, t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = INVERSION_T.sub(" t'", t)
    t = INVERSION.sub(" t'", t)
    t = IMPERATIVE.sub(" z'", t)
    t = t.replace("-", " ")
    t = _acronyms(t)
    return " ".join(_sandhi(finish_fr(t)))
