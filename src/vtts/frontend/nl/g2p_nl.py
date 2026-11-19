"""Dutch word -> nl-en tokens (spelling rules, vowel length, schwa, stress).

A word (lower case, after normalize_nl) is first looked up in lexicons/nl/overrides.tsv (phonemes
written out, "1" on the stressed vowel). A word made only of number morphs (eenentwintig,
tweeduizendzesentwintig) is read morph by morph with the stress on the first. Otherwise an
unstressed prefix (be- ge- ver- ont- her- er-, not before the stems of NOT_PREFIX) is read as such
and the rest by the rules:

- Graphemes, longest first: ieuw eeuw aai ooi oei (vowel + w/j), eau, auw ouw au ou (Au), aa ee oo
  uu ie oe eu ui ei ij, the single vowels (y is a vowel, j before a vowel at the start); sch ch ng nk
  sj th ph qu ck dt c x and single consonants; doubled consonants are one sound.
- Vowel length of a single vowel letter: long in an open syllable (at the end of the word, before
  one consonant and a vowel, or before an obstruent + l/r and a vowel), short in a closed one;
  ch, sch, ng, nk, x, ck and qu close the syllable. Long: a: e: o: y (u) i (i); short: A E O Y I.
- Schwa: an unstressed e after the stress, a final e, the e of a prefix, an unstressed open e
  right before the stress (telefoon), -ig, -lijk (the n of -en is kept).
- Consonants: g and ch are x (sch = s x, final -sch = s), ng N, nk N k, sj S, th t, ph f, qu k w,
  c is s before e i y and k elsewhere, x k s, final -tie after a vowel t s i (else s i), final
  devoicing (b d -> p t at the end and before a voiceless consonant), -age a: Z @.
- Stress: an accented vowel (één, café); a stressed ending (STRESSED_ENDINGS: -teit -eur -ier -aal
  -eel -ant -ent -ist -iek -ief -ine -ade -age -aat -iet -ijn -ij -uur -oen -oon -ees -aan -erij
  -ie after r g f k m d p b, -eren after a vowel and one consonant, each also before -e -en -s); the
  syllable before -tie -sie -isch -isme; else the first syllable after an unstressed prefix.
  Function words (FUNCTION_WORDS) and one-syllable words have no stress mark.

Tokens: NL:<phoneme>, with "1" on the stressed vowel (NL:a:1).
"""

from __future__ import annotations

import functools
import unicodedata

from ..lexicons import load_table, load_words

LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzáéíóúàèëïöüêç")
FOLD = {"ø": "o", "æ": "e", "œ": "e", "ß": "s", "ł": "l", "đ": "d", "þ": "t", "å": "a",
        "ä": "a", "â": "a", "î": "i", "ô": "o", "û": "u", "ì": "i", "ò": "o", "ù": "u"}

VOWEL_GRAPHEMES = (
    # spelling, vowel (None: a single-letter vowel, decided by the rules), glide after it
    ("ieuw", "i", "w"), ("eeuw", "e:", "w"), ("aai", "a:", "j"), ("ooi", "o:", "j"),
    ("oei", "u", "j"), ("eau", "o:", ""), ("auw", "Au", ""), ("ouw", "Au", ""),
    ("aa", "a:", ""), ("ee", "e:", ""), ("oo", "o:", ""), ("uu", "y", ""), ("ie", "i", ""),
    ("oe", "u", ""), ("eu", "2:", ""), ("ui", "9y", ""), ("ei", "Ei", ""), ("ij", "Ei", ""),
    ("au", "Au", ""), ("ou", "Au", ""),
)
SINGLE_VOWELS = "aeiouyáéíóúàèëïöüê"
ACCENTED = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "à": "a", "è": "e", "ê": "e"}
DIAERESIS = {"ë": "e", "ï": "i", "ö": "o", "ü": "u"}
CONSONANT_GRAPHEMES = (
    ("sch", ("s", "x")), ("ch", ("x",)), ("ng", ("N",)), ("nk", ("N", "k")), ("sj", ("S",)),
    ("th", ("t",)), ("ph", ("f",)), ("qu", ("k", "w")), ("ck", ("k",)), ("dt", ("t",)),
    ("x", ("k", "s")),
)
# Graphemes that close the syllable before them.
CLOSING = frozenset(("sch", "ch", "ng", "nk", "qu", "ck", "x", "dt"))
OBSTRUENTS = frozenset("pbtdkgfvc")
LIQUIDS = frozenset("lr")
FRONT = frozenset("eiyéèëïê")
SINGLE = {"g": "x", "j": "j", "v": "v", "w": "w", "z": "z", "h": "h", "q": "k", "ç": "s",
          "b": "b", "d": "d", "f": "f", "k": "k", "l": "l", "m": "m", "n": "n", "p": "p",
          "r": "r", "s": "s", "t": "t"}
VOICELESS = frozenset(("p", "t", "k", "f", "s", "x", "S"))
DEVOICE = {"b": "p", "d": "t", "v": "f", "z": "s"}
LONG = {"a": "a:", "e": "e:", "i": "i", "o": "o:", "u": "y", "y": "i"}
SHORT = {"a": "A", "e": "E", "i": "I", "o": "O", "u": "Y", "y": "I"}

PREFIXES = (("ver", ("v", "@", "r")), ("ont", ("O", "n", "t")), ("her", ("h", "E", "r")),
            ("be", ("b", "@")), ("ge", ("x", "@")), ("er", ("E", "r")))
# Words starting like a prefix that is not one (beter, geven, verder, herfst ...).
NOT_PREFIX = (
    "beter", "beven", "bezem", "beker", "bezig", "bende", "bedden", "bed", "berg", "beek",
    "been", "beer", "beest", "bel", "best", "betje", "beurs", "beu", "bever", "bes", "ben",
    "geven", "gever", "gevel", "gele", "geel", "geld", "gelden", "geest", "geit", "gek", "gem",
    "gen", "genre", "gerst", "gesp", "gerrit", "geur", "gewest",
    "ver", "verder", "verte", "vers", "verf", "verre", "verven", "veren", "verzen", "verwen",
    "verbum", "vertex", "vervel",
    "her", "herder", "herfst", "hertog", "herberg", "hert", "herman", "hernia", "heros",
    "ont", "onto",
    "erg", "erger", "ergens", "erf", "erwt", "ernst", "erts", "erik", "eros", "ere", "eren",
    "erna", "erop", "eruit", "erin", "eraan", "erbij", "erdoor", "ermee", "erom", "erover",
    "ervan", "ervoor", "erachter", "eronder", "ertegen", "ertoe", "erheen",
)
# Stressed endings: (ending, letter offset of the stressed vowel in it), longest first.
STRESSED_ENDINGS = (("iteit", 3), ("teit", 1), ("erij", 2), ("arij", 2), ("euse", 0), ("eur", 0),
                    ("ier", 0), ("aal", 0), ("ieel", 1), ("reel", 1), ("ueel", 1), ("ëel", 1), ("ant", 0), ("ent", 0), ("ist", 0),
                    ("iek", 0), ("ief", 0), ("ine", 0), ("ade", 0), ("age", 0), ("aat", 0),
                    ("iet", 0), ("ijn", 0), ("uur", 0), ("oen", 0), ("oon", 0), ("ees", 0),
                    ("aan", 0), ("ette", 0), ("ale", 0), ("rele", 1), ("uele", 1), ("ee", 0), ("ij", 0))
# Verb forms of -eren with ee (studeert, publiceerde): the ee is stressed.
EER_FORMS = ("eert", "eerd", "eerde", "eerden", "eer")
UNSTRESSED_ENT = ("kent", "pent", "bent", "gent", "lent", "dent")
INFLECTIONS = ("en", "e", "s", "es", "n")
PRESTRESS_ENDINGS = ("tie", "ties", "sie", "sies", "isch", "ische", "isme", "ismen")
FUNCTION_WORDS = frozenset((
    "de", "het", "een", "en", "of", "maar", "als", "dan", "dat", "die", "dit", "deze", "wat",
    "wie", "in", "op", "te", "tot", "van", "met", "voor", "naar", "bij", "aan", "om", "uit",
    "door", "ik", "je", "jij", "u", "hij", "zij", "ze", "we", "wij", "mij", "me", "hem", "haar",
    "ons", "zich", "is", "was", "er", "zo", "al", "ook", "nog", "wel", "want", "dus", "hun",
    "mijn", "m'n", "z'n", "'s", "'t", "'n", "zijn", "had", "heeft", "per",
))
NUMBER_MORPHS = ("nul", "een", "één", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht",
                 "negen", "tien", "elf", "twaalf", "dertien", "veertien", "vijftien", "zestien",
                 "zeventien", "achttien", "negentien", "twintig", "dertig", "veertig", "vijftig",
                 "zestig", "zeventig", "tachtig", "negentig", "honderd", "duizend", "en", "ën",
                 "eerste", "tweede", "derde", "achtste", "ste", "de")


@functools.cache
def override_table() -> dict[str, tuple[str, ...]]:
    return {k: tuple(v.split()) for k, v in load_table("nl", "overrides").items()}


def fold(word: str) -> str:
    """Lower case, Dutch letters kept, other accented letters reduced to their base letter."""
    out = []
    for ch in word.lower():
        if ch in LETTERS:
            out.append(ch)
            continue
        base = FOLD.get(ch) or (unicodedata.normalize("NFKD", ch) or " ")[0]
        if base in LETTERS:
            out.append(base)
    return "".join(out)


def _segments(w: str) -> list[list]:
    """["V", vowel or None, letter, glide, accented, grapheme] or ["C", phonemes, grapheme] per
    grapheme; doubled consonant letters become one ["C"] with grapheme of two letters."""
    out: list[list] = []
    i, n = 0, len(w)
    plain = "".join(ACCENTED.get(c, c) for c in w)  # éé, èè ... are read as ee
    while i < n:
        for g, v, glide in VOWEL_GRAPHEMES:
            if plain.startswith(g, i):
                accented = any(c in ACCENTED for c in w[i:i + len(g)])
                out.append(["V", v, g[0], glide, accented, g])
                i += len(g)
                break
        else:
            c = w[i]
            if c in SINGLE_VOWELS:
                if c == "y" and i + 1 < n and w[i + 1] in "aeiou" and i == 0:
                    out.append(["C", ("j",), "y"])
                elif c in ACCENTED:
                    out.append(["V", None, ACCENTED[c], "", True, c])
                elif c in DIAERESIS:
                    out.append(["V", None, DIAERESIS[c], "", False, c])
                else:
                    out.append(["V", None, c, "", False, c])
                i += 1
                continue
            if c == "t" and w.startswith("tio", i) and i > 0:  # -tion, -tioneel: S
                out.append(["C", ("S",), "ti"])
                i += 2
                continue
            if c == "n" and w.startswith("nge", i) and (w.startswith(("aange", "onge", "inge")) and i in (1, 2, 3)
                                                       and w[:i + 1] in ("aan", "on", "in")):
                out.append(["C", ("n",), "n"])  # aan|ge, on|ge, in|ge
                i += 1
                continue
            for g, ph in CONSONANT_GRAPHEMES:
                if w.startswith(g, i):
                    out.append(["C", ph, g])
                    i += len(g)
                    break
            else:
                if c == "c":
                    if i + 1 < n and w[i + 1] == "c":  # cc: k s before e i y, else k
                        front = i + 2 < n and w[i + 2] in FRONT
                        out.append(["C", ("k", "s") if front else ("k",), "cc"])
                        i += 2
                        continue
                    out.append(["C", ("s",) if i + 1 < n and w[i + 1] in FRONT else ("k",), "c"])
                    i += 1
                    continue
                if c not in SINGLE:  # an apostrophe or a stray letter
                    i += 1
                    continue
                if i + 1 < n and w[i + 1] == c:
                    out.append(["C", (SINGLE[c],), c + c])
                    i += 2
                    continue
                out.append(["C", (SINGLE[c],), c])
                i += 1
    return out


def _open(segs: list[list], k: int) -> bool:
    """The single vowel at segs[k] ends an open syllable."""
    j = k + 1
    if j >= len(segs):
        return True
    if segs[j][0] == "V":
        return True
    c1 = segs[j]
    if j + 1 >= len(segs):
        return False
    if segs[j + 1][0] == "V":
        return len(c1[2]) == 1 and c1[2] not in CLOSING or c1[2] in ("th", "ph", "ti")
    c2 = segs[j + 1]
    return (len(c1[2]) == 1 and c1[2] in OBSTRUENTS and c2[2] in LIQUIDS
            and j + 2 < len(segs) and segs[j + 2][0] == "V")


def _ends(w: str, endings: tuple[str, ...]) -> str | None:
    """The first of endings that w ends with (w longer than it)."""
    for e in endings:
        if w.endswith(e) and len(w) > len(e):
            return e
    return None


def _stress(w: str, segs: list[list], nuclei: list[int]) -> int | None:
    """Index into segs of the stressed vowel (endings are matched without diaeresis)."""
    w = "".join(DIAERESIS.get(c, c) for c in w)
    if not nuclei:
        return None
    marked = [k for k in nuclei if segs[k][4]]
    if marked:
        return marked[0]
    if len(nuclei) == 1:
        return nuclei[0]
    for infl in ("",) + INFLECTIONS:
        if infl and not w.endswith(infl):
            continue
        stem = w[:len(w) - len(infl)] if infl else w
        for e, off in STRESSED_ENDINGS:
            if not stem.endswith(e) or len(stem) <= len(e):
                continue
            if e == "ent" and stem.endswith(UNSTRESSED_ENT) and not stem.endswith(("dent", "gent")):
                continue
            pos = _nucleus_starting(segs, nuclei, len(stem) - len(e) + off)
            if pos is not None:
                return pos
    if w.endswith("ie") and len(w) > 3 and w[-3] in "rgfkmdpb" and segs[nuclei[-1]][-1] == "ie":
        return nuclei[-1]
    for e in EER_FORMS:
        if w.endswith(e) and len(w) > len(e) + 1:
            pos = _nucleus_starting(segs, nuclei, len(w) - len(e))
            if pos is not None:
                return pos
    if w.endswith("eren") and len(nuclei) >= 3:
        k = len(w) - 4
        if k >= 2 and w[k - 1] not in "aeiouy" and w[k - 2] in "aeiouy":
            pos = _nucleus_starting(segs, nuclei, k)
            if pos is not None:
                return pos
    e = _ends(w, PRESTRESS_ENDINGS)
    if e is not None:
        before = [k for k in nuclei if _seg_start(segs, k) < len(w) - len(e)]
        if before:
            return before[-1]
    return nuclei[0]


def _seg_start(segs: list[list], k: int) -> int:
    return sum(len(s[-1]) if s[0] == "V" else len(s[2]) for s in segs[:k])


def _nucleus_starting(segs: list[list], nuclei: list[int], pos: int) -> int | None:
    """The nucleus starting exactly at letter position pos."""
    for k in nuclei:
        if _seg_start(segs, k) == pos:
            return k
    return None


def _rules(w: str, stressed: bool = True, prefix_before: bool = False) -> list[str]:
    """Phonemes of a word without prefix (stressed: mark the stressed vowel with 1)."""
    segs = _segments(w)
    nuclei = [k for k, s in enumerate(segs) if s[0] == "V"]
    stress = _stress(w, segs, nuclei) if stressed else None
    if stressed and len(nuclei) == 1 and w in FUNCTION_WORDS:
        stress = None
    out: list[str] = []
    for k, s in enumerate(segs):
        if s[0] == "C":
            ph = s[1]
            g = s[2]
            if g == "sch" and (k == len(segs) - 1 or (k == len(segs) - 2 and segs[-1][2] == "e"
                                                     and segs[-1][0] == "V")):
                ph = ("s",)
            if g == "ch" and k == 0 and w in CH_S:
                ph = ("S",)
            if g == "g" and w.endswith(("gie", "gieën", "gies")) and k == _last_consonant(segs) \
                    and not w.endswith(("logie", "logieën", "logies")):
                ph = ("Z",)
            if g == "n" and k + 1 < len(segs) and segs[k + 1][0] == "C" and segs[k + 1][1][0] == "k":
                ph = ("N",)
            out.extend(ph)
            continue
        v, letter, glide = s[1], s[2], s[3]
        is_stressed = k == stress
        if v is None:
            v = _single_vowel(w, segs, nuclei, k, letter, stress, prefix_before)
        out.append(v + ("1" if is_stressed and v != "@" else ""))
        if glide:
            out.append(glide)
    return _finish(w, out)


CH_S = frozenset(("chef", "chefs", "chique", "chic", "chocolade", "chauffeur", "chauffeurs",
                  "champagne", "china", "chinees", "chinese", "chirurg", "charme", "charmant",
                  "chalet", "chantage", "chaperon", "check", "checken", "chips", "chat", "chatten"))


def _last_consonant(segs: list[list]) -> int:
    k = len(segs) - 1
    while k >= 0 and segs[k][0] != "C":
        k -= 1
    return k


def _single_vowel(w: str, segs: list[list], nuclei: list[int], k: int, letter: str,
                  stress: int | None, prefix_before: bool) -> str:
    is_open = _open(segs, k) and not (k == 0 and w.startswith(("opl", "opr")))
    if letter == "e" and segs[k][-1] in ("ë",) and not is_open and stress != k:
        return "@"
    if stress == k or (stress is None and len(nuclei) == 1 and letter != "e"):
        return LONG[letter] if is_open else SHORT[letter]
    if letter == "e":
        if k == len(segs) - 1:
            return "@"
        if stress is None:
            return "@" if len(nuclei) == 1 and is_open else ("E" if len(nuclei) == 1 else "@")
        if k > stress:
            return "@" if _schwa_coda(segs, k) else "E"
        if is_open:
            nxt = nuclei[nuclei.index(k) + 1]
            return "@" if nxt == stress else "e:"
        return "E"
    if letter == "i" and k > (stress or 0) and _ig_at(segs, k):
        return "@"
    if letter == "i" and k + 1 < len(segs) and segs[k + 1][2] == "sch" and (
            k + 2 == len(segs) or (k + 3 == len(segs) and segs[k + 2][-1] == "e")):
        return "i"  # -isch, -ische
    return LONG[letter] if is_open else SHORT[letter]


SCHWA_CODAS = frozenset(("", "n", "r", "l", "m", "s", "nd", "nt", "rd", "rt", "ns", "rs", "ls", "ms",
                         "nds", "nts", "rds", "rts", "ts", "st", "nst", "rst", "ld"))


def _schwa_coda(segs: list[list], k: int) -> bool:
    """An unstressed e after the stress is a schwa: in the last syllable before one of SCHWA_CODAS;
    inside the word when no consonant closes its syllable, or only n r l m (honderden, wetenschap,
    overzicht: the -en -er -el of a first compound part); not before a doubled consonant (stellen)."""
    j = k + 1
    gs: list[str] = []
    while j < len(segs) and segs[j][0] == "C":
        g = segs[j][2]
        if len(g) == 2 and g[0] == g[1]:
            return False
        gs.append(g)
        j += 1
    if j == len(segs):
        return "".join(gs) in SCHWA_CODAS
    if len(gs) <= 1:
        return True
    onset = 1
    for m in (3, 2):
        if len(gs) >= m and "".join(gs[-m:]) in ONSETS:
            onset = m
            break
    coda = gs[:-onset]
    return not coda or (len(coda) == 1 and coda[0] in ("n", "r", "l", "m"))


def _ig_at(segs: list[list], k: int) -> bool:
    """-ig / -ige / -igs / -igheid: the i of an unstressed -ig."""
    rest = "".join(s[-1] if s[0] == "V" else s[2] for s in segs[k + 1:])
    return rest in ("g", "ge", "gs", "gen", "gheid", "gheden", "ger", "gst", "gste") and segs[k][-1] == "i"


def _finish(w: str, out: list[str]) -> list[str]:
    # -lijk: l @ k
    for end in ("lijk", "lijke", "lijks", "lijker", "lijkheid", "lijkheden"):
        if w.endswith(end) and len(w) > len(end):
            idx = _find_lijk(out)
            if idx is not None:
                out[idx] = "@"
            break
    # final -tie / -ties: t s i after a vowel, else s i
    for end in ("tie", "ties"):
        if w.endswith(end) and len(w) > len(end) + 1:
            j = len(out) - (2 if end == "tie" else 3)
            if j >= 0 and out[j] == "t" and out[j + 1].rstrip("1") == "i":
                if w[-len(end) - 1] in "aeiouy":
                    out.insert(j + 1, "s")
                else:
                    out[j] = "s"
            break
    # -age: a: Z @
    if w.endswith("age") and len(out) >= 3 and out[-2] == "x" and len(w) > 4:
        out[-2] = "Z"
    # final devoicing and devoicing before a voiceless consonant
    for j, p in enumerate(out):
        if p in DEVOICE and (j == len(out) - 1 or out[j + 1] in VOICELESS):
            out[j] = DEVOICE[p]
    # doubled sounds from compounds of graphemes (t t) are one
    res: list[str] = []
    for p in out:
        if res and p == res[-1] and p not in VOWELS and p.rstrip("1") not in VOWELS:
            continue
        res.append(p)
    return res


def _find_lijk(out: list[str]) -> int | None:
    for j in range(len(out) - 3, -1, -1):
        if out[j] == "l" and out[j + 1].rstrip("1") == "Ei" and out[j + 2] == "k":
            return j + 1
    return None


VOWELS = frozenset(("A", "E", "I", "O", "Y", "a:", "e:", "i", "o:", "u", "y", "2:", "Ei", "9y",
                    "Au", "@"))


def _number_split(w: str) -> list[str] | None:
    """The number morphs of w (two or more), or None."""
    n = len(w)
    best: list[list[str] | None] = [None] * (n + 1)
    best[0] = []
    for i in range(n):
        if best[i] is None:
            continue
        for m in NUMBER_MORPHS:
            if w.startswith(m, i) and best[i + len(m)] is None:
                best[i + len(m)] = best[i] + [m]
    parts = best[n]
    if parts is None or len(parts) < 2 or parts[0] in ("en", "ën", "ste", "de"):
        return None
    return parts


NUMBER_READINGS = {"en": ("@", "n"), "ën": ("@", "n"), "een": ("e:", "n"), "één": ("e:", "n"),
                   "ste": ("s", "t", "@"), "de": ("d", "@")}


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('lopen' -> l o:1 p @), without the NL: prefix."""
    w = fold(word)
    if not w:
        return ()
    table = override_table()
    if word.lower() in table:
        return table[word.lower()]
    if w in table:
        return table[w]
    parts = _number_split(w)
    if parts is not None:
        out: list[str] = []
        for k, m in enumerate(parts):
            ph = list(NUMBER_READINGS.get(m) or _rules(m))
            if k == 0 and not any(p.endswith("1") for p in ph):
                ph = _mark_first(ph)
            elif k > 0:
                ph = [p.removesuffix("1") for p in ph]
            out += ph
        return tuple(_merge(out))
    for p, ph in PREFIXES:
        rest = w[len(p):]
        if w.startswith(p) and len(rest) >= 3 and _onset_ok(rest, p) and not _not_prefix(w):
            body = list(_rules(rest))
            if not any(x.endswith("1") for x in body):
                body = _mark_first(body)
            return tuple(_merge(list(ph) + body))
    return tuple(_rules(w))


ONSETS = frozenset(("bl", "br", "dr", "dw", "fl", "fr", "gl", "gr", "kl", "kn", "kr", "kw", "pl",
                    "pr", "sl", "sm", "sn", "sp", "st", "sw", "sch", "schr", "str", "spr", "spl",
                    "tr", "tw", "zw", "wr", "vl", "vr", "ch", "chr", "th", "ph", "sj", "tj"))
NOT_PREFIX_ENDINGS = ("", "e", "en", "s", "es", "n", "er", "ere", "eren", "st", "ste", "je", "jes",
                      "tje", "tjes")


def _onset_ok(rest: str, p: str) -> bool:
    """The rest after a prefix starts with a vowel (not after be- ge- er-) or a Dutch onset, and
    has a vowel."""
    k = 0
    while k < len(rest) and rest[k] not in SINGLE_VOWELS:
        k += 1
    if k == len(rest):
        return False
    if k == 0:
        return p in ("ver", "ont", "her") or rest[0] in DIAERESIS
    return k == 1 or rest[:k] in ONSETS


def _not_prefix(w: str) -> bool:
    return any(w.startswith(x) and w[len(x):] in NOT_PREFIX_ENDINGS for x in NOT_PREFIX)


def _mark_first(ph: list[str]) -> list[str]:
    out = list(ph)
    for j, p in enumerate(out):
        if p in VOWELS and p != "@":
            out[j] = p + "1"
            break
    return out


def _merge(out: list[str]) -> list[str]:
    res: list[str] = []
    for p in out:
        if res and p == res[-1] and p.rstrip("1") not in VOWELS:
            continue
        res.append(p)
    return res


def word_tokens_nl(word: str) -> list[str]:
    """nl-en tokens of one word; a word without a vowel (km, s) is spelled letter by letter,
    except 's (s)."""
    w = fold(word)
    if w and not any(ch in SINGLE_VOWELS for ch in w):
        from .normalize_nl import LETTERS as NAMES

        if word.startswith("'") or w in override_table():
            return [f"NL:{p}" for p in phonemes(word)]
        return [t for ch in w if ch in NAMES for t in word_tokens_nl(NAMES[ch])]
    return [f"NL:{p}" for p in phonemes(word)]


# ---------------- spelling check (Dutch or English?) ----------------

FOREIGN = ("ck", "wh", "tch", "ay", "oy", "ght", "ii", "ight", "dget")
FOREIGN_START = ("sh", "ph")
FOREIGN_END = ("sh", "ph", "igh", "dge")


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Dutch spelling: none of the English letter groups of
    FOREIGN (ck wh tch ay oy ght ii ight dget), no sh / ph at the start or sh ph igh dge at the end
    (inside a word they are a morph boundary: staatshoofd, opheffing, vaardigheid, grondgebied),
    ph inside only in oph- (op + h), a final w only after u (uw, ouw, ieuw), and not in
    lexicons/nl/english.txt (English words that fit Dutch spelling: software, reminder)."""
    if not w or not w.isascii() or not w.isalpha() or w in load_words("nl", "english"):
        return False
    if any(f in w for f in FOREIGN) or w.startswith(FOREIGN_START) or w.endswith(FOREIGN_END):
        return False
    if "ph" in w and not w.startswith("oph"):
        return False
    return not (w.endswith("w") and not w.endswith("uw"))


def unreadable_nl(text: str) -> list[str]:
    """Letters the Dutch front-end cannot read (other scripts), to filter training sentences."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
