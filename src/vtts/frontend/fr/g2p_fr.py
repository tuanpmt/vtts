"""French word -> fr-en tokens (spelling rules, silent letters, nasal vowels, e muet).

A word (lower case, after normalize_fr, which already applied liaison) is read in four steps:

1. Table: lexicons/fr/overrides.tsv gives the reading of a whole word (or of the word without a
   plural s): a respelling read by the rules below (one token, e.g. femme -> fame), or phonemes
   separated by spaces (monsieur -> m @ s j eu). Function words with a fixed reading are there too.
2. Prefixes before an apostrophe: elision (l', d', qu', jusqu' ...) and the liaison consonant that
   normalize_fr attaches to the next word (les amis -> les z'amis) are read as consonants, then the
   rest of the word is read on its own.
3. The end of the word (_respell_end): plural -s/-x and final -z, -d, -t, -p, -g after n, -c after
   n are silent (bus, net, sud, cap, avec ... in lexicons/fr/final.txt keep theirs); -ent of a
   verb is silent (parlent) but read [an] in -ment words, -ents, one-syllable words and the nouns,
   adjectives and adverbs of lexicons/fr/ent.txt (client, souvent); -er is [e] (parler, premier)
   except one-syllable words and lexicons/fr/er.txt (mer, hiver); -ez, -ed -> [e], -et -> [E].
4. Letters, left to right (_scan): vowel digraphs (ai ei au eau ou oi eu œu), nasal vowels (a vowel
   before m/n that is not followed by a vowel or another m/n: an en am em on om in im ain ein un
   yn, ien -> j in), glides (i u ou before a vowel -> j H w, kept as vowels after a consonant +
   l/r: crier), ill (fille, travail, soleil; ville, mille, tranquille keep l), consonants (c ç g ge
   gu qu ch ph th gn s/ss/z between vowels, t of -tion, x as ks/gz, h silent), then:
   - e: é -> e, è ê ë -> E; e before a doubled consonant, a cluster that cannot start a syllable,
     x, or a pronounced final consonant -> E (belle, reste, examen, mer); e before one consonant
     (or consonant + l/r) and a vowel is a schwa (petit, secret); a final e is silent;
   - e muet: a schwa is dropped when exactly one consonant separates it from the vowel before
     it and a vowel follows (samedi -> s a m d i, maintenant, boulangerie); in the first
     syllable of a word it is kept (petit, semaine);
   - mid vowels by position: o is O in a closed syllable and before another syllable, o at the
     end of the word and before z (mot, rose); eu/œu is oe in a closed syllable (peur, neuf) and
     eu elsewhere (feu, heureux, Europe, heureuse).

valid_spelling() says whether a plain ASCII word could be French (latin.py uses it to tell French
from English words); unreadable_fr() lists letters the front-end cannot read.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from itertools import pairwise

from ..latin import clusters_fit, consonant_runs
from ..lexicons import load_table, load_words

LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzàâäæçéèêëîïôöœùûüÿ")
NASAL_E = "ã"  # internal: the -ent of a noun, adjective or adverb, read [an] (a front vowel for c/g)
VOWELS = frozenset("aeiouyàâäæéèêëîïôöœùûüÿ" + NASAL_E)
FOLD = {"ø": "eu", "ß": "ss", "ł": "l", "ñ": "gn", "å": "a", "ã": "an", "õ": "on"}
FRONT = frozenset("eiyéèêëîïæ" + NASAL_E)
# Consonant + l/r that start a syllable (the e before them stays open: secret, reprendre).
ONSET2 = frozenset(("pl", "pr", "bl", "br", "tr", "dr", "cl", "cr", "kl", "kr", "gl", "gr", "fl",
                    "fr", "vr", "phl", "phr", "chr", "thr"))
# Elision and liaison prefixes before an apostrophe, read as consonants.
PREFIX = {"l": ["l"], "d": ["d"], "j": ["zh"], "m": ["m"], "t": ["t"], "s": ["s"], "c": ["s"],
          "n": ["n"], "z": ["z"], "r": ["r"], "p": ["p"], "v": ["v"], "qu": ["k"]}
PHONEMES = frozenset(("i", "e", "E", "a", "O", "o", "u", "y", "eu", "oe", "@", "an", "on", "in",
                      "un", "j", "w", "H", "p", "b", "t", "d", "k", "g", "f", "v", "s", "z", "sh",
                      "zh", "m", "n", "gn", "ng", "l", "r"))
VOWEL_PHONEMES = frozenset(("i", "e", "E", "a", "O", "o", "u", "y", "eu", "oe", "@", "an", "on",
                            "in", "un"))
OBSTRUENTS = frozenset(("p", "b", "t", "d", "k", "g", "f", "v"))
MENT_VERBS = "ment_verbs"
# Word beginnings read unlike the letter rules: ch = k, gn = g n, ill = i l, x = z, x = s; the heads
# before ex + vowel read g z (inexact, hexagone).
CH_HARD = ("chor", "chœur", "orchestr", "psych", "écho", "archéo", "chaos", "chrono", "techn",
           "archa", "chiro")
GN_SPLIT = ("diagnos", "stagn", "agnosti", "gnom", "gnou", "cognitif", "cognitiv", "inexpugn",
            "magnum", "wagner")
ILL_L = ("mill", "tranquill", "lill", "distill", "oscill", "pupill", "bacill", "gill")
X_Z = ("deuxi", "sixi", "dixi")
X_S = ("soixant", "bruxell", "auxerr")
EX_GZ_HEADS = ("in", "h", "co", "ré", "pré")
# An e between a vowel and one consonant + vowel is silent (remerciement): the vowels of that rule.
SILENT_E_VOWELS = "aeiouyàâéèêëîïôûùü"
SILENT_E_AFTER = re.compile(rf"[^{SILENT_E_VOWELS}][{SILENT_E_VOWELS}{NASAL_E}]")


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("fr", "overrides")


@functools.cache
def _words(name: str) -> frozenset[str]:
    return load_words("fr", name)


def fold(word: str) -> str:
    """Lower case, French letters and the apostrophe kept, other accented letters reduced to their
    base letter (ñ -> gn, ø -> eu)."""
    out = []
    for ch in word.lower().replace("’", "'"):
        if ch in LETTERS or ch == "'":
            out.append(ch)
            continue
        base = FOLD.get(ch) or (unicodedata.normalize("NFKD", ch) or " ")[0]
        if all(b in LETTERS for b in base):
            out.append(base)
    return "".join(out)


def _vowel_groups(w: str) -> int:
    return len(re.findall(r"[aeiouyàâäæéèêëîïôöœùûüÿ]+", w))


# ---------------- the end of the word ----------------

def _ent_read(w: str) -> bool:
    """-ent read [an] (not a verb ending): -ment words except verbs (aiment), one-syllable words
    (dent, vent), the words of ent.txt."""
    if w in _words("ent"):
        return True
    if _vowel_groups(w[:-3]) == 0:
        return True
    return w.endswith("ment") and w not in _words(MENT_VERBS)


def _respell_end(w: str) -> str:
    """The word with its silent final letters removed and its ending respelled (see the module
    docstring, step 3)."""
    if w in _words("final"):
        return w
    plural = False
    if len(w) > 2 and w.endswith("s") and not w.endswith("ss"):
        w, plural = w[:-1], True
        if w in _words("final") or w + "s" in _words("final"):
            return w
    elif len(w) > 2 and w.endswith("x"):
        if w.endswith(("ex", "ax", "yx", "ox", "ynx")) and not w.endswith(("aux", "eaux")):
            return w  # index, thorax, box, lynx
        w = w[:-1]
    elif len(w) > 2 and w.endswith("z"):
        if w.endswith("ez"):
            return w[:-2] + "é"
        w = w[:-1]
    if w.endswith("em") and len(w) > 2:
        return w[:-2] + "èm"  # requiem, Jérusalem, tandem (not temps: tem after the p)
    if w.endswith("ent") and len(w) > 3:
        if plural or _ent_read(w):
            return w[:-6] + "am" + NASAL_E if w.endswith("emment") else w[:-3] + NASAL_E
        elif w.endswith("ient") and w[-5] in "vt":  # vient, tient: -ien + silent t
            pass
        else:
            return w[:-2]  # parlent -> parle
    if w.endswith("er") and len(w) > 2:
        if w in _words("er") or (plural and w + "s" in _words("er")) or _vowel_groups(w[:-2]) == 0:
            return w[:-2] + "èr"
        return w[:-2] + "é"
    if w.endswith("ed") and len(w) > 2:
        return w[:-2] + "é"
    if w.endswith("et") and len(w) > 2:
        return w[:-2] + "è"
    while len(w) > 1:
        last, prev = w[-1], w[-2]
        if last == "t":
            if w.endswith(("ct", "pt", "st")):
                break
            w = w[:-1]
        elif last in "dp":
            w = w[:-1]
        elif last == "g" and (prev not in VOWELS or prev == "i" and w[-3:-2] in VOWELS):
            w = w[:-1]  # sang, long, bourg; doigt
        elif last == "c" and (prev == "n" or w in _words("c_silent")):
            w = w[:-1]  # blanc, tabac
        elif last == "b" and prev == "m":
            w = w[:-1]  # plomb
        elif last == "l" and w in _words("l_silent"):
            w = w[:-1]  # gentil, outil
        elif last == "f" and w in _words("f_silent"):
            w = w[:-1]  # clef, nerf
        else:
            break
    return w


# ---------------- letters ----------------

def _nasal(w: str, k: int) -> bool:
    """w[k] (m or n) closes a nasal vowel: not followed by a vowel, h or another m/n."""
    if k >= len(w) or w[k] not in "mn":
        return False
    return k + 1 == len(w) or (w[k + 1] not in VOWELS and w[k + 1] not in "mnh")


def _cluster_before(w: str, i: int) -> bool:
    """A consonant + l/r right before position i (crier, cruel, trouer: the vowel stays)."""
    return i >= 2 and w[i - 1] in "lr" and w[i - 2] in "pbtdkgfvc"


def _silent_e(w: str, k: int) -> bool:
    """w[k] is an e after a vowel that is not read: one consonant then a vowel follows
    (remerciement, dévouement, ingénierie)."""
    return (w[k:k + 1] == "e" and k + 2 < len(w) and w[k + 1] not in VOWELS
            and w[k + 2] in VOWELS)


def _ti_is_s(w: str, i: int) -> bool:
    """t of -tion, -tiel, -tieux, -tience, -tiaire ... read [s] (not after s/x, not -tié -tier)."""
    if i == 0 or w[i - 1] in "sx":
        return False
    rest = w[i + 1:]
    if not rest.startswith("i") or len(rest) < 2:
        return False
    if rest == "ie":  # partie; démocratie, diplomatie
        return w.endswith("atie")
    if rest.startswith(("ié", "ier", "iè", "iez", "ien")):
        return rest.startswith("ience")
    return rest[1] in "aeouâ" + NASAL_E


def _scan(w: str) -> list[list[str]]:
    """Segments [kind, phoneme]: C consonant, G glide, V vowel, O/EU mid vowels decided later,
    S schwa candidate, F final e."""
    out: list[list[str]] = []
    n = len(w)
    i = 0

    def at(k: int) -> str:
        return w[k] if 0 <= k < n else "#"  # outside the word: no letter

    def isv(k: int) -> bool:
        return at(k) in VOWELS

    def add(kind: str, *phs: str) -> None:
        for ph in phs:
            out.append([kind, ph])

    while i < n:
        c, n1, n2, n3 = at(i), at(i + 1), at(i + 2), at(i + 3)
        step = 1
        # ---- vowels ----
        if c in "aàâä":
            if c == "a" and n1 in "iî":
                if n2 in "mn" and _nasal(w, i + 2):
                    add("V", "in")
                    step = 3
                elif n2 == "l" and (n3 == "l" or i + 3 == n):  # travail, paille
                    add("V", "a")
                    add("G", "j")
                    step = 4 if n3 == "l" else 3
                else:
                    add("V", "E")
                    step = 2
            elif c == "a" and n1 == "y":
                add("V", "E")
                if isv(i + 2):
                    add("G", "j")
                step = 2
            elif c == "a" and n1 == "u":
                add("V", "O" if n2 == "r" else "o")
                step = 2
            elif c == "a" and n1 in "mn" and _nasal(w, i + 1):
                add("V", "an")
                step = 2
            else:
                add("V", "a")
        elif c == "e":
            if n1 == "a" and n2 == "u":
                add("V", "o")
                step = 3
            elif n1 in "uû" or n1 == "œ":
                if n2 == "i" and n3 == "l" and (at(i + 4) == "l" or i + 4 == n):  # feuille, deuil
                    add("V", "oe")
                    add("G", "j")
                    step = 5 if at(i + 4) == "l" else 4
                else:
                    add("EU", "eu")
                    step = 2
            elif n1 in "iî":
                if n2 in "mn" and _nasal(w, i + 2):
                    add("V", "in")
                    step = 3
                elif n2 == "l" and (n3 == "l" or i + 3 == n):  # soleil, abeille
                    add("V", "E")
                    add("G", "j")
                    step = 4 if n3 == "l" else 3
                else:
                    add("V", "E")
                    step = 2
            elif n1 == "y":
                add("V", "E")
                if isv(i + 2):
                    add("G", "j")
                step = 2
            elif n1 in "mn" and _nasal(w, i + 1):
                # bien, moyen, européen, viendra (not -ience: science)
                ien = (at(i - 1) in "iyé" and n1 == "n" and not w.startswith("ce", i + 2)
                       and not (n2 == "t" and (w[i - 3:i - 1] == "sc" or isv(i + 3) and at(i - 2) not in "bvt")))
                # scientifique, patiente, orientale (not bientôt, viendra)
                add("V", "in" if ien else "an")
                step = 2
            elif n1 in "mn" and n2 == n1 and i == 0:  # ennui, emmener
                add("V", "an")
                add("C", n1)
                step = 3
            elif n1 == "m" and n2 == "m" and w[i + 3:i + 6] == "ent":
                add("V", "a")
            elif i == n - 1:
                add("F", "@")
            elif isv(i + 1):
                if at(i - 1) not in "g":  # mangeons, geôle: e silent
                    add("V", "E")
            elif (isv(i - 1) and at(i - 1) not in "éè" and not (at(i - 1) == "u" and at(i - 2) in "qg")
                  and re.match(SILENT_E_AFTER, w[i + 1:])):
                pass  # remerciement, gaieté, dévouement (not cruel, question, guerre, pierre)
            else:
                add(*_e_before_consonants(w, i))
        elif c == "é":
            add("V", "e")
        elif c in "èêë":
            add("V", "E")
        elif c in "iîï":
            if c == "i" and n1 in "mn" and _nasal(w, i + 1):
                add("V", "in")
                step = 2
            elif c == "i" and n1 == "l" and n2 == "l":
                if isv(i - 1) and not (at(i - 1) == "u" and at(i - 2) in "gq"):  # ouille
                    add("G", "j")
                elif i == 0 or w[i - 1:i + 3] == "vill" or w.startswith(ILL_L):
                    add("V", "i")
                    add("C", "l")
                else:  # fille, famille
                    add("V", "i")
                    add("G", "j")
                step = 3
            elif c == "i" and n1 == "l" and i + 2 == n and isv(i - 1):  # -ouil, œil
                add("G", "j")
                step = 2
            elif c in "iî" and isv(i + 1) and not (i + 2 == n and n1 == "e") \
                    and not _silent_e(w, i + 1):
                if _cluster_before(w, i):  # crier, oublier
                    add("V", "i")
                add("G", "j")
            else:
                add("V", "i")
        elif c in "oôö":
            if c == "o" and n1 in "iî":
                if n2 == "n" and _nasal(w, i + 2):
                    add("G", "w")
                    add("V", "in")
                    step = 3
                else:
                    add("G", "w")
                    add("V", "a")
                    step = 2
            elif c == "o" and n1 == "y":
                add("G", "w")
                add("V", "a")
                if isv(i + 2):
                    add("G", "j")
                step = 2
            elif c == "o" and n1 in "uùû":
                if n2 == "i" and n3 == "l" and (at(i + 4) == "l" or i + 4 == n):  # grenouille
                    add("V", "u")
                    add("G", "j")
                    step = 5 if at(i + 4) == "l" else 4
                elif isv(i + 2) and not (i + 3 == n and n2 == "e") and not _cluster_before(w, i) \
                        and not _silent_e(w, i + 2):
                    add("G", "w")
                    step = 2
                else:
                    add("V", "u")
                    step = 2
            elif c == "o" and n1 in "mn" and _nasal(w, i + 1):
                add("V", "on")
                step = 2
            elif c == "o" and n1 in "eê":  # poêle, moelle
                add("G", "w")
                add("V", "a")
                step = 2
            elif c == "ô":
                add("V", "o")
            else:
                add("O", "O")
        elif c == "œ":
            if n1 == "u":
                add("EU", "eu")
                step = 2
            elif n1 == "i" and n2 == "l":
                add("V", "oe")
                add("G", "j")
                step = 3
            else:
                add("V", "e")
        elif c == "æ":
            add("V", "e")
        elif c == NASAL_E:
            add("V", "an")
        elif c in "uùûü":
            if c == "u" and at(i - 1) in "cg" and w.startswith("eil", i + 1):  # accueil, orgueil
                add("V", "oe")
                add("G", "j")
                step = 5 if at(i + 4) == "l" else 4
            elif c == "u" and n1 in "mn" and _nasal(w, i + 1):
                if n1 == "m" and i + 2 == n and i > 0:  # album, maximum
                    add("V", "O")
                    add("C", "m")
                else:
                    add("V", "un")
                step = 2
            elif c in "uü" and isv(i + 1) and not (i + 2 == n and n1 == "e") \
                    and not _silent_e(w, i + 1):
                add("V", "y") if _cluster_before(w, i) else add("G", "H")
            else:
                add("V", "y")
        elif c in "yÿ":
            if n1 in "mn" and _nasal(w, i + 1):
                add("V", "in")
                step = 2
            elif isv(i + 1) and not (i + 2 == n and n1 == "e"):  # yeux, Libye
                add("G", "j")
            else:
                add("V", "i")
        # ---- consonants ----
        elif c == "c":
            if n1 == "h":
                hard = (n2 != "#" and n2 not in VOWELS) or w.startswith(CH_HARD)
                add("C", "k" if hard else "sh")
                step = 2
            elif n1 in FRONT:
                add("C", "s")
            elif n1 == "c" and n2 in FRONT:
                add("C", "k", "s")
                step = 2
            elif n1 in "cqk":
                add("C", "k")
                step = 3 if n1 == "q" and n2 == "u" else 2  # acquérir
            else:
                add("C", "k")
        elif c == "ç":
            add("C", "s")
        elif c == "g":
            if at(i - 1) == "n" and n1 not in VOWELS and n1 not in "rl#":
                pass  # longtemps, sangsue
            elif n1 == "n":
                if w.startswith(GN_SPLIT):
                    add("C", "g", "n")
                else:
                    add("C", "gn")
                step = 2
            elif n1 == "u" and n2 in FRONT:
                add("C", "g")
                step = 2
            elif n1 in FRONT:
                add("C", "zh")
                if n1 == "e" and n2 in "aoâô":
                    step = 2  # mangeait, geôle: e silent
            elif n1 == "g" and n2 in FRONT:
                add("C", "g", "zh")
                step = 2
            elif n1 == "g":
                add("C", "g")
                step = 2
            else:
                add("C", "g")
        elif c == "h":
            pass
        elif c == "j":
            add("C", "zh")
        elif c == "k":
            add("C", "k")
        elif c == "p":
            if n1 == "h":
                add("C", "f")
                step = 2
            elif n1 == "p":
                add("C", "p")
                step = 2
            elif at(i - 1) == "m" and n1 == "t":  # compter, dompter
                pass
            else:
                add("C", "p")
        elif c == "q":
            add("C", "k")
            if n1 == "u":
                step = 2
        elif c == "s":
            if n1 == "s" or n1 == "c" and n2 in FRONT:
                add("C", "s")
                step = 2
            elif n1 == "h":
                add("C", "sh")
                step = 2
            elif isv(i - 1) and isv(i + 1):
                add("C", "z")
            else:
                add("C", "s")
        elif c == "t":
            if n1 == "h" or n1 == "t":
                add("C", "t")
                step = 2
            elif _ti_is_s(w, i):
                add("C", "s")
            else:
                add("C", "t")
        elif c == "w":
            add("G", "w")
        elif c == "x":
            if i == 0:
                add("C", "g", "z") if w.startswith("xavier") else add("C", "k", "s")
            elif w.startswith(X_Z):
                add("C", "z")
            elif w.startswith(X_S):
                add("C", "s")
            elif at(i - 1) == "e" and isv(i + 1) and (i == 1 or w[:i - 1] in EX_GZ_HEADS):
                add("C", "g", "z")  # exemple, inexact, hexagone
            elif n1 == "c" and n2 in FRONT:  # excellent, exciter
                add("C", "k", "s")
                step = 2
            else:
                add("C", "k", "s")
        elif c in "bdfjlmnrvz":
            add("C", c)
            if n1 == c:
                step = 2
        i += step
    return out


def _e_before_consonants(w: str, i: int) -> tuple[str, str]:
    """A plain e followed by consonant letters: [kind, phoneme] (E closed, S schwa candidate)."""
    j = i + 1
    while j < len(w) and w[j] not in VOWELS:
        j += 1
    run = w[i + 1:j]
    if j == len(w):  # pronounced final consonants: sel, chef, mer, direct
        return "V", "E"
    if run[0] == "x":
        return "V", "E"
    if len(run) >= 2 and run[0] == run[1]:
        if run == "ss" and w.startswith(("ress", "dessus", "dessous")) and i <= 1:
            return "S", "@"
        return "V", "E"
    single = run if len(run) == 1 else run[:2] if run[:2] in ("ch", "ph", "th", "gn", "qu") else ""
    if run == single or run in ONSET2 or (run[:2] in ("ch", "ph", "th") and run[2:] in "lr"):
        return "S", "@"
    return "V", "E"


# ---------------- e muet and mid vowels ----------------

def _resolve(segs: list[list[str]]) -> list[str]:
    def is_vowel(s: list[str]) -> bool:
        return s[0] in ("V", "O", "EU") or (s[0] == "S" and s[1] == "@")

    n_vowels = sum(1 for s in segs if s[0] in ("V", "O", "EU", "S"))
    # final e: silent unless it is the only vowel (le, que)
    for s in segs:
        if s[0] == "F":
            s[0], s[1] = ("S", "@") if n_vowels == 0 else ("X", "")
    # schwa deletion (left to right): one consonant since the previous vowel, a vowel after
    for k, s in enumerate(segs):
        if s[0] != "S" or s[1] != "@":
            continue
        before = 0
        prev_vowel = False
        for t in reversed(segs[:k]):
            if t[0] == "X":
                continue
            if is_vowel(t):
                prev_vowel = True
                break
            before += 1
        after_vowel = any(is_vowel(t) for t in segs[k + 1:])
        if prev_vowel and before == 1 and after_vowel:
            s[0], s[1] = "X", ""
    out: list[str] = []
    live = [s for s in segs if s[0] != "X"]
    for k, s in enumerate(live):
        if s[0] not in ("O", "EU"):
            out.append(s[1])
            continue
        cons: list[str] = []
        nxt_vowel = False
        for t in live[k + 1:]:
            if is_vowel(t):
                nxt_vowel = True
                break
            cons.append(t[1])
        if nxt_vowel:  # a glide before the next vowel belongs to it (neuvième, voyelle)
            while cons and cons[-1] in ("j", "w", "H"):
                cons.pop()
        if s[0] == "O":
            if (not nxt_vowel and not cons) or cons[:1] == ["z"]:
                out.append("o")
            else:
                out.append("O")
            continue
        closed = (len(cons) >= 1 and not nxt_vowel and cons != ["z"]) or (
            len(cons) >= 2 and not (len(cons) == 2 and cons[0] in OBSTRUENTS and cons[1] in "lr"))
        out.append("oe" if closed else "eu")
    return out


# ---------------- words ----------------

def _read_table(reading: str) -> tuple[str, ...]:
    if " " in reading:
        return tuple(reading.split())
    return _rules(reading)


def _rules(w: str) -> tuple[str, ...]:
    return tuple(_resolve(_scan(_respell_end(w))))


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('enfants' -> an f an), without the FR: prefix."""
    raw = fold(word).lstrip("'")
    w = raw.rstrip("'")
    if not w:
        return ()
    if raw.endswith("'") and "'" not in w:  # an elided clitic before an English word: l'
        if w in PREFIX:
            return tuple(PREFIX[w])
        if w.endswith("qu"):
            return phonemes(w + "e")
    table = override_table()
    if w in table:
        return _read_table(table[w])
    if "'" in w:
        head, _, rest = w.partition("'")
        if head in PREFIX:
            return tuple(PREFIX[head]) + phonemes(rest)
        if head.endswith("qu"):  # jusqu', lorsqu', quelqu'
            return phonemes(head + "e") + phonemes(rest)
        return phonemes(head) + phonemes(rest)
    if w.endswith("s") and w[:-1] in table and w[:-1] not in _words("final"):
        return _read_table(table[w[:-1]])
    return _rules(w)


def word_tokens_fr(word: str) -> list[str]:
    """fr-en tokens of one word; a word without a vowel (km, ss) is spelled letter by letter."""
    w = fold(word).lstrip("'")
    if w and "'" not in w and not any(ch in VOWELS for ch in w) and w not in override_table():
        from .normalize_fr import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for n in NAMES[ch].split() for t in word_tokens_fr(n)]
    return [f"FR:{p}" for p in phonemes(word)]


# ---------------- spelling check (French or English?) ----------------

ONSETS = frozenset(["pl", "pr", "bl", "br", "tr", "dr", "cl", "cr", "gl", "gr", "fl", "fr", "vr",
                    "ps", "pn", "sc", "sp", "st", "sk", "str", "spr", "scr", "spl", "sph", "squ",
                    "ch", "ph", "th", "gn", "rh", "chr", "chl", "phr", "phl", "thr", "qu", "gu"])
CODAS = frozenset("lrsmnxcpbdgtfz") | {"ct", "rs", "ns", "bs", "ls", "rt", "rd", "rc", "rm", "rn",
                                      "rl", "rb", "rg", "rp", "rv", "lc", "lp", "lt", "mp", "nc",
                                      "nd", "nt", "ng", "st", "sc", "mb", "nq", "rch", "x", "ch",
                                      "ph", "th", "gn"}
FINALS = frozenset("srlzxtdcfnmpgq") | {"nt", "nd", "ng", "rd", "rt", "rs", "ct", "pt", "st", "mp",
                                        "mps", "rc", "rf", "rg", "gt", "ls", "ts", "ds", "ps",
                                        "rps", "nts", "nds", "rts", "cts", "rds", "ngs",
                                        "rcs", "cs", "ss", "ns", "ms", "ch", "rch", "ff", "ll",
                                        "nc", "ncs", "mb", "rm", "rn", "lt", "ngt", "ngts"}
DOUBLES = frozenset(["ll", "ss", "tt", "nn", "mm", "rr", "ff", "pp", "cc", "ee"])
FOREIGN = ("sh", "ck", "gh", "wh", "ea", "oo", "ow", "aw", "ew", "w", "k", "tch", "tz", "sz")
DIGRAPHS = (("eau", "o"), ("ch", "C"), ("ph", "F"), ("th", "T"), ("gn", "N"), ("qu", "K"),
            ("gu", "G"))


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits French spelling: no w, k or English letter groups
    (sh ck gh ea oo ow), no doubled letters other than ll ss tt nn mm rr ff pp cc ee, onsets of
    one consonant or the French clusters, codas inside a word of one consonant or the usual
    pairs, a vowel or one of the French final letters and clusters at the end, and no y after a
    consonant at the end (weekend, chat, happy, update are not French; chateau, parle, temps
    are)."""
    if not w or not w.isascii() or not w.isalpha():
        return False
    if any(f in re.sub(r"eau|(?<=[gj])ea", "o", w) for f in FOREIGN):  # beau, Jean, mangea
        return False
    if any(a == b and a + b not in DOUBLES for a, b in pairwise(w)):
        return False
    if w.endswith("ing") or (w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou"):
        return False
    for d, r in DIGRAPHS:
        w = w.replace(d, r)
    runs = consonant_runs(w, y_vowel=True)
    if runs is None:
        return False
    runs = [(r.replace("C", "ch").replace("F", "ph").replace("T", "th").replace("N", "gn")
             .replace("K", "q").replace("G", "g"), s, e) for r, s, e in runs]
    return clusters_fit(runs, ONSETS, CODAS, FINALS)


def unreadable_fr(text: str) -> list[str]:
    """Letters the French front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded to a base letter and are readable."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
