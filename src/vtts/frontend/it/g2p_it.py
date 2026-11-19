"""Italian word -> it-en tokens (spelling rules, gemination, glides, stress, open e/o).

A word (lower case, after normalize_it) is first replaced by its entry in lexicons/it/overrides.tsv
(respellings in Italian orthography: an accent on any vowel marks the stress, è ò an open vowel,
é ó a closed one; telefono -> telèfono), then read letter by letter:

- c/g before e/i -> ch/dj, ch/gh -> k/g; ci/gi/sci + vowel: the i only marks the sound (ciao,
  giorno, scienza) unless it carries an accent (farmacìa); sc before e/i -> sh, sch -> s k;
  gli -> ly (gli + vowel: i silent), gn -> ny; qu -> k w; h silent; x -> k s; j y -> i sounds.
- s: voiced z between vowels and before b d g l m n r v (casa, sbaglio, smettere), else s.
  z: dz at the start of a word and in -izzare (zero, organizzare), else ts (azione, pizza).
- Gemination: a doubled letter is the consonant twice (fatto -> t t, acqua -> k k); ny, ly, sh,
  ts, dz are long between vowels (figlio -> ly ly, pesce -> sh sh, azione -> ts ts).
- Glides: an unaccented i/u next to another vowel is j/w (piano, buono, mai); in a word with one
  vowel group (mio, via, due) the i/u is the stressed nucleus.
- Stress: the vowel with a written accent; else antepenultimate for the suffixes -abile/-ibile,
  -evole, -imo (massimo, ventesimo), -ico/-ica, -ologo, -ografo, -fono, -metro, -olo/-ola after b c g p t v
  (titolo, piccola), -dine/-gine/-mine (ordine, immagine, termine), -ere (essere, prendere; not
  the -ére verbs of ERE_PENULT: avere, potere, ottenere), double consonant + -ero (vennero,
  ebbero), 3rd plural -ono and -avano -evano -ivano -erano -arono (all with 3+ syllables); else the last vowel of a word ending in a consonant (città is
  written with an accent), else the second-to-last. Function words (UNSTRESSED) have no stress.
- Stressed e/o are closed unless: written è ò, in ie/uo (piede, buono), antepenultimate stress
  (medico, popolo) or the suffixes -ente -enti (not -mente), -enza, -ello, -esimo (open E) and
  -orio -oria (open O). Other stressed e/o are closed (the quality is lexical; overrides.tsv lists frequent
  words).
- Elision: l'acqua, dell'anno, c'è: the part before the apostrophe is read without stress and
  joined to the word (c/g before e/i become ch/dj).

valid_spelling() says whether a plain ASCII word could be Italian (latin.py uses it to tell
Italian from English words).
"""

from __future__ import annotations

import functools
import re
import unicodedata
from itertools import pairwise

from ..latin import clusters_fit, consonant_runs
from ..lexicons import load_table

GRAVE = {"à": "a", "è": "e", "ì": "i", "ò": "o", "ù": "u", "î": "i"}
ACUTE = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
VOWEL_LETTERS = "aeiou" + "".join(GRAVE) + "".join(ACUTE)
LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz") | frozenset(GRAVE) | frozenset(ACUTE)
FOLD = {"ø": "o", "æ": "e", "œ": "e", "ß": "s", "ł": "l", "ñ": "n", "ç": "s"}
FRONT = "eièéìí"
VOICED = "bdglmnrv"
IZZARE = re.compile(r"izz(a[rtvz]|ando|er(?![iì]a))")
# Words elided before an apostrophe (l'acqua, dell'anno, un'altra), for latin.py.
ELIDED = frozenset(("l", "d", "c", "s", "m", "t", "v", "n", "dell", "nell", "all", "dall", "sull",
                    "coll", "un", "quest", "quell", "sant", "tutt", "bell", "buon", "po", "dev",
                    "dov", "com", "cos", "anch", "senz", "nessun", "qualcun", "ciascun"))
ELISION = "\u02bc"  # ʼ: normalize_it writes a word-final apostrophe as this letter-like mark
LONG_BETWEEN_VOWELS = ("ny", "ly", "sh", "ts", "dz")

UNSTRESSED = frozenset((
    "il", "lo", "la", "i", "gli", "le", "un", "una", "di", "a", "da", "in", "con", "su", "per",
    "tra", "fra", "del", "dello", "della", "dei", "degli", "delle", "al", "allo", "alla", "ai", "agli",
    "alle", "dal", "dallo", "dalla", "dai", "dagli", "dalle", "nel", "nello", "nella", "nei", "negli",
    "nelle", "sul", "sullo", "sulla", "sui", "sugli", "sulle", "col", "coi", "e", "ed", "o", "od",
    "ma", "che", "se", "mi", "ti", "si", "ci", "vi", "ne", "non", "lo", "li", "gli", "ad",
))

# Antepenultimate stress (regex on the word, minimum number of vowel nuclei).
ANTEPENULT = (
    (re.compile(r"(abil|ibil|evol)[eiae]$"), 3),
    (re.compile(r"im[oaie]$"), 3),
    (re.compile(r"(ic[oa]|ici|iche)$"), 3),
    (re.compile(r"olog[oai]$|ologhe$"), 3),
    (re.compile(r"ograf[oaie]$"), 3),
    (re.compile(r"fon[oi]$"), 3),
    (re.compile(r"metr[oi]$"), 3),
    (re.compile(r"[bcgptv]ol[oaie]$"), 3),
    (re.compile(r"[dgm]in[ei]$"), 3),
    (re.compile(r"[^i]ere$"), 3),
    (re.compile(r"([bcdfglmnprstvz])\1ero$"), 3),
    (re.compile(r"[^aeiou]ono$"), 3),
    (re.compile(r"([aei]van|eran|aron|eron|iron)o$"), 3),
)
OPEN_E = re.compile(r"(?<!m)(ente|enti)$|(enz[ae]|ell[oaie]|esim[oaie])$")
# -ia/-ie with a stressed i (galleria, geometria, compagnie): the i gets an accent before reading.
IA_STEMS = ("metri", "logi", "grafi", "sofi", "pati", "crazi", "nomi", "foni", "scopi", "terapi", "gni",
            "archi", "fobi", "fili", "tomi", "cardi")
IA_ERIA_AFTER = ("ll", "tt", "zz", "rr", "br", "cc", "nn", "ss", "nt")  # pizzeria, libreria, segreteria
IA_STRESS = re.compile(r"((?<=" + "|".join(IA_ERIA_AFTER) + r")eri(?=a$)|" + "|".join(IA_STEMS)
                       + r"|mani(?=e$))([ae])$")
# Tens + sei/sette (ventisei, trentasette): a voiceless s, and sei keeps its stress.
TEN_WORDS = ("venti", "trenta", "quaranta", "cinquanta", "sessanta", "settanta", "ottanta", "novanta")
NUMBER_SEI = re.compile(r"(" + "|".join(TEN_WORDS) + r")s(ei|ette)?$")
# -ere infinitives stressed on the e (avere, potere, ottenere) and other -ere words of that kind.
ERE_STEMS = ("av", "dov", "pot", "vol", "sap", "ved", "piac", "ten", "par", "cad", "god", "riman", "sed",
             "val", "tac", "giac", "dol", "persuad", "mest", "carab", "sfer", "atmosf", "primav", "cr")
ERE_PENULT = re.compile(r"(" + "|".join(ERE_STEMS) + r")ere$")
OPEN_O = re.compile(r"(ori[oa]|orie)$")


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("it", "overrides")


def fold(word: str) -> str:
    """Lower case, Italian letters kept, other accented letters reduced to their base letter."""
    out = []
    for ch in word.lower():
        if ch in LETTERS:
            out.append(ch)
            continue
        base = FOLD.get(ch) or (unicodedata.normalize("NFKD", ch) or " ")[0]
        if base in LETTERS:
            out.append(base)
    return "".join(out)


def _vowel(ch: str) -> list:
    if ch in GRAVE:
        return ["V", GRAVE[ch], "grave"]
    if ch in ACUTE:
        return ["V", ACUTE[ch], "acute"]
    return ["V", ch, None]


def _segments(w: str) -> list[list]:
    """["V", vowel, accent] or ["C", phoneme] per sound."""
    out: list[list] = []
    n = len(w)

    def at(k: int) -> str:
        return w[k] if 0 <= k < n else ""

    def is_v(k: int) -> bool:
        return at(k) != "" and at(k) in VOWEL_LETTERS

    def silent_i(k: int) -> bool:
        """An unaccented i after c/g/sc that only marks the sound before another vowel."""
        return at(k) == "i" and is_v(k + 1)

    i = 0
    while i < n:
        c, nxt, nxt2 = w[i], at(i + 1), at(i + 2)
        if c in VOWEL_LETTERS:
            out.append(_vowel(c))
            i += 1
            continue
        if c in "jy":
            out.append(["V", "i", None])
            i += 1
            continue
        double = nxt == c and c not in "h"
        if c == "c" and nxt == "q":
            double, nxt, nxt2 = True, "q", at(i + 2)
        if double:  # read the second letter in its context, then the consonant twice
            i += 1
            c, nxt, nxt2 = w[i], at(i + 1), at(i + 2)
        before = len(out)
        step = 1
        if c == "c":
            if nxt == "h":
                out.append(["C", "k"])
                step = 2
            elif nxt in FRONT:
                out.append(["C", "ch"])
                if silent_i(i + 1):
                    step = 2
            else:
                out.append(["C", "k"])
        elif c == "g":
            if nxt == "h":
                out.append(["C", "g"])
                step = 2
            elif nxt in FRONT:
                out.append(["C", "dj"])
                if silent_i(i + 1):
                    step = 2
            elif nxt == "l" and nxt2 in ("i", "ì"):
                out.append(["C", "ly"])
                step = 3 if silent_i(i + 2) else 2
            elif nxt == "n":
                out.append(["C", "ny"])
                step = 2
            else:
                out.append(["C", "g"])
        elif c == "s":
            if nxt == "c" and nxt2 in FRONT:
                out.append(["C", "sh"])
                step = 3 if silent_i(i + 2) else 2
            elif nxt == "c" and nxt2 == "h":
                out += [["C", "s"], ["C", "k"]]
                step = 3
            elif (nxt and nxt in VOICED) or (is_v(i - 1) and is_v(i + 1) and not double
                                              and not NUMBER_SEI.search(w[:i + 1])):
                out.append(["C", "z"])
            else:
                out.append(["C", "s"])
        elif c == "z":
            voiced = (i == 0 and not double) or (double and IZZARE.search(w) is not None)
            out.append(["C", "dz" if voiced else "ts"])
        elif c == "q":
            out.append(["C", "k"])
            if nxt == "u":
                out.append(["G", "w"])
                step = 2
        elif c == "h":
            pass
        elif c == "x":
            out += [["C", "k"], ["C", "s"]]
        elif c == "w":
            out.append(["C", "v"])
        elif c == "k":
            out.append(["C", "k"])
        else:
            out.append(["C", c])
        if double and len(out) > before:
            out.insert(before, list(out[before]))
        i += step
    # intrinsically long consonants between vowels
    res: list[list] = []
    for k, s in enumerate(out):
        res.append(s)
        if (s[0] == "C" and s[1] in LONG_BETWEEN_VOWELS and 0 < k < len(out) - 1
                and out[k - 1][0] == "V" and out[k + 1][0] in "VG" and out[k - 1] != s):
            res.insert(len(res) - 1, list(s))
    return res


def _nuclei(segs: list[list]) -> list[int]:
    """Indices of syllable nuclei; unaccented i/u next to another vowel become glides."""
    runs: list[list[int]] = []
    k = 0
    while k < len(segs):
        if segs[k][0] != "V":
            k += 1
            continue
        j = k
        while j < len(segs) and segs[j][0] == "V":
            j += 1
        runs.append(list(range(k, j)))
        k = j
    nuclei: list[int] = []
    for run in runs:
        if len(run) == 1:
            nuclei += run
            continue
        weak = [k for k in run if segs[k][1] in "iu" and segs[k][2] is None]
        strong = [k for k in run if k not in weak]
        if (len(runs) == 1 and len(run) == 2 and weak == [run[0]] and strong
                and segs[run[1]][2] is None):
            nuclei += run  # mio, via, due: two syllables, stress on the i/u
            segs[run[0]][2] = "stress"
            continue
        # weak vowels not next to a strong one: one of them is a nucleus (fiume, guida, aiuto:
        # the last; lui, cui at the end of a word: the first)
        lone = [k for k in weak if k - 1 not in strong and k + 1 not in strong]
        if lone:
            strong.append(lone[0] if lone[-1] == len(segs) - 1 else lone[-1])
        for k in run:
            if k not in strong:
                segs[k] = ["G", "j" if segs[k][1] == "i" else "w"]
        nuclei += sorted(strong)
    return nuclei


def _stress(w: str, segs: list[list], nuclei: list[int]) -> int | None:
    if not nuclei or w in UNSTRESSED:
        return None
    marked = [k for k in nuclei if segs[k][2] is not None]
    if marked:
        return marked[-1]
    if len(nuclei) == 1:
        return nuclei[0]
    for pattern, minimum in ANTEPENULT:
        if len(nuclei) >= minimum and pattern.search(w) and not ERE_PENULT.search(w):
            return nuclei[-3]
    if w[-1] not in VOWEL_LETTERS and w[-1] not in "jy":
        return nuclei[-1]
    return nuclei[-2]


def _quality(w: str, segs: list[list], k: int, nuclei: list[int]) -> str:
    """Stressed vowel: E/O (open) or e/o (closed)."""
    v, accent = segs[k][1], segs[k][2]
    if v not in "eo":
        return v
    if accent == "grave":
        return v.upper()
    if accent == "acute":
        return v
    prev = segs[k - 1] if k else None
    if prev is not None and prev[0] == "G" and prev[1] == ("j" if v == "e" else "w"):
        return v.upper()
    if len(nuclei) >= 3 and k == nuclei[-3]:
        return v.upper()
    if v == "e" and OPEN_E.search(w) and k == nuclei[-2]:
        return "E"
    if v == "o" and OPEN_O.search(w) and k == nuclei[-2]:
        return "O"
    return v


def _read(w: str, stressed: bool = True) -> list[str]:
    segs = _segments(w)
    nuclei = _nuclei(segs)
    stress = _stress(w, segs, nuclei) if stressed else None
    out = []
    for k, s in enumerate(segs):
        if s[0] != "V":
            out.append(s[1])
        elif k == stress:
            out.append(_quality(w, segs, k, nuclei) + "1")
        else:
            out.append(s[1])
    return out


def _mark_ia(w: str) -> str:
    """galleria -> gallerìa (IA_STRESS), ventisei -> ventisèi, when the word has no written
    accent."""
    if any(ch in GRAVE or ch in ACUTE for ch in w):
        return w
    if NUMBER_SEI.search(w) and w.endswith("sei"):
        return w[:-2] + "èi"
    return IA_STRESS.sub(lambda m: m.group(1)[:-1] + "ì" + m.group(2), w)


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('città' -> ch i t t a1), without the IT: prefix."""
    raw = word.replace("’", "'")
    whole = fold(raw)
    if whole in override_table():
        parts = [override_table()[whole]]
    else:
        parts = [p for p in (fold(p) for p in raw.split("'")) if p]
    if not parts:
        return ()
    out: list[str] = []
    for k, p in enumerate(parts):
        last = k == len(parts) - 1
        if not last:  # elided word: c'è, l'acqua
            nxt = parts[k + 1][0]
            if p[-1] in "cg" and nxt in FRONT:
                p = p + "i"  # c' + e -> ch (ci with the i silent before the vowel)
                out += _read(p + nxt, stressed=False)[:-1]
                continue
            out += _read(p, stressed=False)
        else:
            out += _read(_mark_ia(override_table().get(p, p)))
    return tuple(out)


def word_tokens_it(word: str) -> list[str]:
    """it-en tokens of one word; a word without a vowel (km, pst) is spelled letter by letter."""
    if word.endswith(ELISION):  # sullʼ (before an English word, see normalize_it), poʼ
        w = fold(word)
        return [f"IT:{p}" for p in _read(w, stressed=w == "po")]
    w = fold(word.replace("'", ""))
    if w and not any(ch in VOWEL_LETTERS or ch in "jy" for ch in w):
        from .normalize_it import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for n in NAMES[ch].split() for t in word_tokens_it(n)]
    return [f"IT:{p}" for p in phonemes(word)]


# ---------------- spelling check (Italian or English?) ----------------

ONSETS = frozenset(["pr", "br", "tr", "dr", "cr", "gr", "fr", "vr", "pl", "bl", "cl", "gl", "fl",
                    "ps", "pn", "gn", "sp", "st", "sc", "sb", "sd", "sf", "sg", "sl", "sm", "sn", "sv",
                    "spr", "str", "scr", "spl", "sbr", "sfr", "sgr", "sC", "sQ", "C", "G", "Q", "S",
                    "L", "N", "sN"])
CODAS = frozenset("lrnmsbcdgptvfz") | {"ns", "rs"}
FINALS = frozenset("lrnmd") | {"C"}
DOUBLES = frozenset(["bb", "cc", "dd", "ff", "gg", "ll", "mm", "nn", "pp", "rr", "ss", "tt", "vv", "zz",
                     "ii", "ee", "oo"])
FOREIGN = ("sh", "th", "ph", "ck", "wh", "w", "k", "y", "j", "x", "ght", "ou", "ay",
           "ey")
DIGRAPHS = (("ch", "C"), ("gh", "G"), ("qu", "Q"), ("sce", "Se"), ("sci", "Si"), ("gli", "Li"),
            ("gn", "N"))


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Italian spelling: no j k w x y or foreign letter
    groups (sh th ph ck ou), no doubled letters other than consonants and ii ee oo, onsets of
    one consonant, obstruent + l/r or s + consonant, codas of one consonant inside a word (or n/r +
    s), and a vowel or one of l r n m d at the end (weekend, smart, update are not Italian)."""
    if not w or not w.isascii() or not w.isalpha():
        return False
    if any(f in w for f in FOREIGN):
        return False
    if any(a == b and a + b not in DOUBLES for a, b in pairwise(w)):
        return False
    w = re.sub(r"([bcdfglmnprstvz])\1", r"\1", w)
    for d, r in DIGRAPHS:
        w = w.replace(d, r)
    runs = consonant_runs(w, y_vowel=False)
    return runs is not None and clusters_fit(runs, ONSETS, CODAS, FINALS)


def unreadable_it(text: str) -> list[str]:
    """Letters the Italian front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded to a base letter and are readable."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
