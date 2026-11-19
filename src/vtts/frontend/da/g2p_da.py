"""Danish word -> da-en tokens: lexicon, compounds, spelling rules (stress, vowel length, stød).

Danish spelling is far from the pronunciation (soft d, vocalized r, v and g, silent letters, schwa
assimilation, stød), so a word is read in this order:

1. lexicons/da/lexicon.tsv: the frequent words of Danish Wikipedia whose rule reading (step 3)
   differs from the NST pronunciation lexicon for Danish (Nordic Language Technology, CC0, see
   scripts/frontend/build_da_lexicon.py), converted to da-en tokens. lexicons/da/words.txt lists
   the other frequent words (read correctly by the rules); both are the known words.
2. Compounds: a word that is not known is split into two or three known words (each at least three
   letters; a linking s or e may follow a part: arbejd-s-plads), the split with the fewest parts and
   then the longest first part. The parts are read as words (step 1 or 3); the first part keeps the
   primary stress, the later parts' primary stress becomes secondary.
3. Rules (rules()): letters to sound units, stress (first syllable; prefixes be- ge- for-;
   stressed foreign endings -ere -eri -tion -isme -ist -tet -ør -ur ...; a written é), vowel
   quality and length from stress and the following letters, consonants by position (p t k
   unaspirated b d g after s and after a vowel, soft d, silent d in ld nd rd, vocalized r v g),
   unstressed e = schwa merged with r into the r-schwa, and stød on a stressed syllable with a long
   vowel or a short vowel + voiced consonant that ends the word or comes before an ending
   -en -et -er -ene -erne ... .

Function words (UNSTRESSED) lose their stress mark. Tokens (phoneme_set.DA_*): 15 short vowels
(NST SAMPA: i e E a A y 2 9 u o O Q @, V = the open o of "op", 6 = the r-schwa of "-er"), 12 long
vowels (i: ... Q:), the glides j~ w 6~ (vocalized j, v/g, r), 18 consonants (p t k = aspirated,
b d g = unaspirated, D = soft d, R = the onset r, N = ng, s' = sj), "?" = stød after the vowel or
the voiced consonant that carries it, '"' and "%" = primary and secondary stress after the stressed
vowel.
"""

from __future__ import annotations

import functools
import unicodedata

from ..lexicons import load_table, load_words

VOWEL_LETTERS = "aeiouyæøåé"
SHORT = ("i", "e", "E", "a", "A", "y", "2", "9", "u", "o", "O", "Q", "@", "V", "6")
LONG = ("i:", "e:", "E:", "a:", "A:", "y:", "2:", "9:", "u:", "o:", "O:", "Q:")
GLIDES = ("j~", "w", "6~")
CONSONANTS = ("p", "t", "k", "b", "d", "g", "f", "v", "s", "s'", "h", "m", "n", "N", "l", "R", "j",
              "D")
STOD, PRIMARY, SECONDARY = "?", '"', "%"
VOWELS = frozenset(SHORT + LONG)
VOICED_CODA = frozenset(("m", "n", "N", "l", "D", "j~", "w", "6~"))

UNSTRESSED = frozenset((
    "af", "at", "da", "de", "dem", "den", "der", "det", "du", "efter", "eller", "en", "er", "et",
    "for", "fra", "han", "har", "hun", "hvis", "i", "jeg", "kan", "man", "med", "men", "mig", "og",
    "om", "os", "på", "sig", "sin", "sit", "sine", "skal", "som", "til", "ved", "var", "vi", "vil",
    "blev", "bliver", "bliver", "hans", "hendes", "deres", "dens", "dets", "min", "mit", "mine",
    "din", "dit", "dine", "vores", "jer", "ham", "hende", "også", "end", "når", "hvor", "fordi",
    "nogle", "noget", "nogen", "under", "over", "mod", "hos", "uden", "mellem", "blandt", "gennem",
    "ad", "op", "ud", "ind", "ned", "så", "ikke", "dog", "jo", "nu", "her", "havde", "være", "været",
    "kunne", "skulle", "ville", "må", "kun", "et", "ens",
))

# Endings read with the stress on them (with inflections); the number is the vowel of the ending
# that carries the stress (0: its first vowel letter). Longest match on the folded word wins.
STRESSED_ENDINGS: dict[str, int] = {}
for _stem, _ends in (
    ("ere", ("", "r", "de", "t", "nde", "s")), ("ering", ("", "en", "er", "erne", "ens", "s")),
    ("eri", ("", "et", "er", "erne", "ets")), ("tion", ("", "en", "er", "erne", "ens", "al", "ale",
                                                       "el", "elle", "s")),
    ("sion", ("", "en", "er", "erne", "s")), ("isme", ("", "n", "r", "rne")),
    ("ist", ("", "en", "er", "erne", "isk", "iske")), ("tet", ("", "et", "er", "erne", "ets")),
    ("ør", ("", "en", "er", "erne", "s")), ("ur", ("", "en", "er", "erne", "s")),
    ("ent", ("", "en", "er", "erne", "s")), ("ant", ("", "en", "er", "erne", "s")),
    ("ance", ("", "n", "r")), ("ence", ("", "n", "r")), ("logi", ("", "en", "er", "sk", "ske")),
    ("grafi", ("", "en", "er", "sk", "ske")), ("sofi", ("", "en", "er", "sk", "ske")),
    ("nomi", ("", "en", "sk", "ske")), ("tek", ("", "et", "er", "erne")),
    ("øs", ("", "e")), ("ese", ("", "n", "r")), ("age", ("", "n", "r")), ("ade", ("", "n", "r")),
    ("at", ("en", "er", "erne", "et")), ("al", ("e", "en", "er", "erne", "t")),
    ("ik", ("en", "er", "erne", "ens")), ("on", ("en", "er", "erne", "ens")),
    ("ission", ("", "en", "er", "erne")), ("ssion", ("", "en", "er")), ("ik", ("",)),
):
    for _e in _ends:
        STRESSED_ENDINGS[_stem + _e] = 0
# Endings that put the stress on the vowel before them (politisk, logiske).
PRE_STRESSED_ENDINGS = ("isk", "iske", "isks")
UNSTRESSED_PREFIXES = ("be", "ge", "for")
# Endings after which a stressed final stem syllable keeps its stød (huset, dagen, hunden).
STOD_ENDINGS = ("en", "et", "ens", "ets", "er", "ers", "erne", "ernes", "ene", "enes", "s")
LONG_FINAL = frozenset("slrgbvf")  # a stressed vowel before one final consonant: long (hus, bil)

FOLD = {"à": "a", "á": "a", "â": "a", "ä": "æ", "ã": "a", "è": "e", "ê": "e", "ë": "e", "ì": "i",
        "í": "i", "î": "i", "ï": "i", "ò": "o", "ó": "o", "ô": "o", "ö": "ø", "õ": "o", "ù": "u",
        "ú": "u", "û": "u", "ü": "y", "ý": "y", "ÿ": "y", "ç": "s", "ñ": "n", "ß": "s", "œ": "ø",
        "ð": "d", "þ": "t"}


def fold(word: str) -> str:
    """Lower case; letters outside a-z æ ø å é folded to them (ä -> æ, ö -> ø, ü -> y), others
    dropped."""
    out = []
    for ch in unicodedata.normalize("NFC", word.lower()):
        if "a" <= ch <= "z" or ch in "æøåé":
            out.append(ch)
        elif ch in FOLD:
            out.append(FOLD[ch])
    return "".join(out)


# ---------------- spelling -> units ----------------
# A unit is (code, position in the folded word): a vowel letter, or a consonant: a letter, a doubled
# letter ("tt": one sound, the vowel before it is short), "S" (sj, sch, ch, -tion), "N" (ng, nk).

ONSETS = frozenset((
    "pl", "pr", "pj", "bl", "br", "bj", "tr", "tv", "tj", "dr", "dv", "dj", "kl", "kr", "kv", "kn",
    "kj", "gl", "gr", "gn", "gj", "fl", "fr", "fj", "vr", "vl", "sp", "st", "sk", "sl", "sm", "sn",
    "sv", "spl", "spr", "str", "skr", "skj", "spj", "skv",
))
PAIR_NUCLEI = frozenset(("au", "eu", "ou", "aa", "oo", "ee", "uu", "ii", "ei", "ai", "øi"))


def units(w: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    i, n = 0, len(w)
    while i < n:
        c = w[i]
        if i > 0 and w.startswith(("tion", "sion"), i):
            out.append(("S", i))
            i += 2
        elif w.startswith("sch", i):
            out.append(("S", i))
            i += 3
        elif w.startswith(("sj", "ch"), i) or (i == 0 and w.startswith("sh")):
            out.append(("S", i))
            i += 2
        elif w.startswith(("ph", "th"), i):
            out.append(("f" if c == "p" else "t", i))
            i += 2
        elif w.startswith("ck", i):
            out.append(("kk", i))
            i += 2
        elif w.startswith("ng", i):
            out.append(("N", i))
            i += 2
        elif w.startswith("nk", i):
            out += [("N", i), ("k", i + 1)]
            i += 2
        elif i == 0 and w.startswith(("hv", "hj")):
            out.append((w[1], 0))
            i += 2
        elif c == "x":
            out += [("k", i), ("s", i)]
            i += 1
        elif w.startswith("qu", i):
            out += [("k", i), ("v", i + 1)]
            i += 2
        elif c in "ptkbdgfslmnrv" and i + 1 < n and w[i + 1] == c:
            out.append((c + c, i))
            i += 2
        else:
            if c == "c":
                c = "s" if i + 1 < n and w[i + 1] in "eiyæø" else "k"
            out.append(({"z": "s", "w": "v", "q": "k"}.get(c, c), i))
            i += 1
    return out


def _vowel(u: str) -> bool:
    return u in VOWEL_LETTERS


def nuclei(us: list[tuple[str, int]]) -> list[tuple[int, int]]:
    """(first, last) unit index of each syllable nucleus (au eu ou ei ai: a vowel + glide; aa ee
    oo uu ii: one long vowel)."""
    out: list[tuple[int, int]] = []
    for k, (u, _) in enumerate(us):
        if not _vowel(u):
            continue
        if out and out[-1] == (k - 1, k - 1) and us[k - 1][0] + u in PAIR_NUCLEI:
            out[-1] = (k - 1, k)
            continue
        out.append((k, k))
    return out


def stressed_syllable(w: str, us: list[tuple[str, int]],
                      nuc: list[tuple[int, int]]) -> tuple[int, bool]:
    """(index of the stressed nucleus, True when a foreign ending or é decides it)."""
    for k, (a, _) in enumerate(nuc):
        if us[a][0] == "é":
            return k, True
    if len(nuc) >= 2:
        for e in PRE_STRESSED_ENDINGS:
            if w.endswith(e) and len(nuc) >= 3:
                return len(nuc) - 2, False
        for L in range(min(len(w) - 1, 9), 1, -1):
            if w[-L:] in STRESSED_ENDINGS:
                start = len(w) - L
                k = next((k for k, (a, _) in enumerate(nuc) if us[a][1] >= start), len(nuc))
                if 0 < k < len(nuc):
                    return k, True
                break
        for p in UNSTRESSED_PREFIXES:
            if (w.startswith(p) and len(w) > len(p) + 2 and not _vowel(w[len(p)])
                    and us[nuc[1][0]][1] >= len(p)
                    and (len(nuc) >= 3 or us[nuc[1][0]][0] != "e")):
                return 1, False
    return 0, False


def _base(u: str) -> str:
    return u[0] if len(u) == 2 and u[0] == u[1] else u


def _split(us: list[tuple[str, int]], nuc: list[tuple[int, int]]) -> list[tuple[str, int]]:
    """Role of each unit: ("v", k) nucleus k, ("o", k) onset of nucleus k, ("c", k) coda of k."""
    role: list[tuple[str, int]] = [("o", 0)] * len(us)
    for k, (a, b) in enumerate(nuc):
        for i in range(a, b + 1):
            role[i] = ("v", k)
        end = nuc[k + 1][0] if k + 1 < len(nuc) else len(us)
        cons = list(range(b + 1, end))
        if k + 1 == len(nuc):
            for i in cons:
                role[i] = ("c", k)
            continue
        # a j or g right after the vowel stays with it (glide or silent g)
        first = 0
        while first < len(cons) and first == 0 and us[cons[0]][0] in ("j", "g") and len(cons) >= 1:
            first = 1
        rest = cons[first:]
        take = 0
        for L in range(min(3, len(rest)), 0, -1):
            if L == 1 and us[rest[-1]][0] != "N":
                take = 1
                break
            seq = "".join(_base(us[i][0]) for i in rest[-L:])
            if L > 1 and seq in ONSETS and not any(len(us[i][0]) == 2 for i in rest[-L:]):
                take = L
                break
        for i in cons[:len(cons) - take]:
            role[i] = ("c", k)
        for i in cons[len(cons) - take:]:
            role[i] = ("o", k + 1)
    return role


SHORT_OF = {"a": "a", "e": "E", "i": "i", "o": "V", "u": "u", "y": "y", "æ": "E", "ø": "2", "å": "O",
            "é": "e"}
LONG_OF = {"a": "a:", "e": "e:", "i": "i:", "o": "o:", "u": "u:", "y": "y:", "æ": "E:", "ø": "2:",
           "å": "O:", "é": "e:"}
UNSTRESSED_OF = {"a": "a", "e": "@", "i": "i", "o": "o", "u": "u", "y": "y", "æ": "E", "ø": "2",
                 "å": "O", "é": "e"}
PAIR_OF = {"au": ("A", "w"), "ou": ("O", "w"), "eu": ("E", "w"), "ei": ("A", "j~"),
           "ai": ("A", "j~"), "øi": ("O", "j~"), "aa": ("O:",), "ee": ("e:",), "oo": ("o:",),
           "uu": ("u:",), "ii": ("i:",)}


def rules(word: str) -> list[str]:
    """da-en token names (without the "DA:" prefix) of one word by the spelling rules."""
    w = fold(word)
    us = units(w)
    nuc = nuclei(us)
    if not nuc:
        return [_onset_sound(us, i, True) for i in range(len(us)) if _onset_sound(us, i, True)]
    s, foreign = stressed_syllable(w, us, nuc)
    role = _split(us, nuc)
    n = len(us)
    out: list[list[str]] = [[] for _ in range(n)]  # sounds per unit
    skip: set[int] = set()
    long_syl = [False] * len(nuc)
    for k, (a, b) in enumerate(nuc):
        code = "".join(us[i][0] for i in range(a, b + 1))
        coda = [i for i in range(b + 1, n) if role[i] == ("c", k)]
        onset_next = [i for i in range(b + 1, n) if role[i] == ("o", k + 1)]
        nxt = coda[0] if coda else (onset_next[0] if onset_next else -1)
        c1 = us[nxt][0] if nxt >= 0 else ""
        prev = us[a - 1][0] if a > 0 and role[a - 1] == ("o", k) else ""
        last = k + 1 == len(nuc)
        stressed = k == s
        if a != b:
            out[a] = list(PAIR_OF[code])
            long_syl[k] = out[a][0].endswith(":")
            continue
        v = code
        if not stressed:
            if v == "e" and (prev == "r" and a > 0 or (coda and us[coda[0]][0] == "r")):
                out[a] = ["6"]
                if coda and us[coda[0]][0] == "r":
                    skip.add(coda[0])
                if prev == "r" and a >= 2 and _vowel(us[a - 2][0]):
                    skip.add(a - 1)
            elif v == "e" and us[a][1] == 0:
                out[a] = ["E"]
            elif k == 0 and s == 1 and w.startswith(("be", "ge")) and v == "e":
                out[a] = ["e"]
            elif k == 0 and s == 1 and w.startswith("for") and v == "o":
                out[a] = ["Q"]
                skip.add(a + 1)
            else:
                out[a] = [UNSTRESSED_OF[v]]
            if v == "i" and coda and us[coda[0]][0] == "g":
                skip.add(coda[0])
            continue
        # stressed: length
        if last:
            long = not coda or (len(coda) == 1 and us[coda[0]][0] in LONG_FINAL)
        else:
            long = not coda and len(onset_next) <= 1 and not (
                onset_next and len(us[onset_next[0]][0]) == 2)
        if foreign and last and len(coda) == 1 and us[coda[0]][0] not in ("k", "kk", "N"):
            long = True
        if foreign and v == "o" and prev == "S":
            long = True
        q = LONG_OF[v] if long else SHORT_OF[v]
        if c1 == "r" and coda and coda[0] == nxt:
            after_r = us[nxt + 1][0] if nxt + 1 < n else ""
            if v in "aå" or (v == "o" and after_r and after_r not in ("d", "dd")):
                q = "A:" if v == "a" else "Q:"
                skip.add(nxt)
            else:
                q = {"e": "E", "æ": "E", "ø": "9"}.get(v, SHORT_OF[v] if v != "o" else "o")
        elif c1 == "N":
            q = {"a": "A", "i": "e", "y": "2", "u": "O", "o": "O", "e": "E"}.get(v, SHORT_OF[v])
        elif c1 == "j" and coda:
            q = {"e": "A", "æ": "A", "ø": "O", "a": "A"}.get(v, SHORT_OF[v])
        elif c1 == "g" and coda and coda[0] == nxt:
            if v in "aiuy":
                q = LONG_OF[v]
                skip.add(nxt)
            else:
                q = {"o": "O", "å": "O", "e": "A", "æ": "A", "ø": "O", "é": "A"}[v]
        elif c1 == "v" and coda and coda[0] == nxt:
            q = {"a": "A", "o": "O", "e": "E", "ø": "2", "å": "O"}.get(v, SHORT_OF[v])
        elif not long:
            nxt2 = us[nxt + 1][0] if 0 <= nxt < n - 1 else ""
            if v == "i" and (c1 in ("k", "kk", "nn", "mm") or (c1 == "n" and nxt2 == "d")):
                q = "e"
            elif v == "u" and c1 in ("m", "mm", "nn", "n"):
                q = "O"
            elif v == "y" and (c1 == "nn" or (c1 == "n" and nxt2 == "d")):
                q = "2"
            elif v == "a" and c1 in ("m", "mm"):
                q = "A"
        if v == "a" and prev in ("r", "rr") and q in ("a", "a:"):
            q = "A" if q == "a" else "A:"
        out[a] = [q]
        long_syl[k] = q.endswith(":")
    for i, (u, _) in enumerate(us):
        if i in skip or role[i][0] == "v":
            continue
        out[i] = _consonant(us, nuc, role, i, s)
    # stress and stød
    a, b = nuc[s]
    out[a] = out[a][:1] + [PRIMARY] + out[a][1:]
    tail = w[us[nuc[s + 1][0]][1]:] if s + 1 < len(nuc) else ""
    if not tail or foreign or tail in STOD_ENDINGS:
        if long_syl[s]:
            out[a].insert(out[a].index(PRIMARY) + 1, STOD)
        else:
            after = out[a][out[a].index(PRIMARY) + 1:]
            if after and after[0] in VOICED_CODA:
                out[a].append(STOD)
            else:
                for i in range(b + 1, n):
                    if role[i] != ("c", s):
                        break
                    if out[i]:
                        if out[i][0] in VOICED_CODA:
                            out[i] = out[i][:1] + [STOD] + out[i][1:]
                        break
    return [t for seg in out for t in seg]


def _onset_sound(us: list[tuple[str, int]], i: int, strong: bool) -> str:
    u = _base(us[i][0])
    if u == "S":
        return "s'"
    if u in "ptk" and not strong:
        return {"p": "b", "t": "d", "k": "g"}[u]
    if u == "r":
        return "R"
    if u in ("c",):
        return "k"
    return u if u in CONSONANTS else ""


def _consonant(us: list[tuple[str, int]], nuc: list[tuple[int, int]],
               role: list[tuple[str, int]], i: int, s: int) -> list[str]:
    u = us[i][0]
    c = _base(u)
    kind, k = role[i]
    prev = us[i - 1][0] if i > 0 else ""
    nxt = us[i + 1][0] if i + 1 < len(us) else ""
    double = len(u) == 2 and u[0] == u[1]
    if c == "S":
        return ["s'"]
    if c == "N":
        return ["N"]
    if kind == "o":
        if c in "ptk":
            strong = (i == 0 or (k == s and not double)) and _base(prev) != "s" or (
                i == 0)
            if prev == "s" and role[i - 1][0] == "o":
                strong = False
            return [_onset_sound(us, i, strong)]
        if c == "d":
            if double or (i > 0 and _vowel(prev) and k != s):
                return ["D"]
            if _base(prev) in ("n", "l", "r") and role[i - 1][0] == "c" and k != s:
                return []
            return ["d"]
        if c == "g" and i > 0 and _vowel(prev) and not double:
            return []
        if c == "h" or c in "bfvslmnj":
            return [c]
        if c == "r":
            return ["R"]
        return [_onset_sound(us, i, False)] if _onset_sound(us, i, False) else []
    # coda
    if c in "ptk":
        if c == "t" and prev == "e" and i == len(us) - 1 and k != s:  # -et: huset
            return ["D"]
        if c == "t" and prev == "d" and role[i - 1] == ("c", k):
            return ["d"]
        return [{"p": "b", "t": "d", "k": "g"}[c]]
    if c == "d":
        if _base(prev) in ("n", "l", "r") or nxt in ("t", "s", "tt", "ss"):
            return []
        return ["D"] if _vowel(prev) or double else ["d"]
    if c == "g":
        if _vowel(prev):
            v = prev
            if v in "oå":
                return ["w"]
            if v in "eæøé":
                return ["j~"]
            return []
        if _base(prev) == "r":
            return ["w"]
        return ["g"]
    if c == "v":
        if _vowel(prev):
            return ["w"]
        if _base(prev) == "l":
            return []
        if _base(prev) == "r":
            return ["w"]
        return ["v"]
    if c == "j":
        return ["j~"] if _vowel(prev) else ["j"]
    if c == "r":
        return ["6~"] if _vowel(prev) else ["R"]
    if c == "h":
        return []
    if c in "bfslmn":
        return [c]
    return []


# ---------------- lexicon, compounds, words ----------------

MIN_PART = 3
LINKS = ("s", "e")
# Letter names, used for a word without a vowel (a spelled consonant cluster: "hm", "pst").
LETTER_NAMES = {"a": "a", "b": "be", "c": "se", "d": "de", "e": "e", "f": "ef", "g": "ge", "h": "hå",
                "i": "i", "j": "jod", "k": "kå", "l": "el", "m": "em", "n": "en", "o": "o", "p": "pe",
                "q": "ku", "r": "ær", "s": "es", "t": "te", "u": "u", "v": "ve", "w": "dobbeltve",
                "x": "eks", "y": "y", "z": "set", "æ": "æ", "ø": "ø", "å": "å", "é": "e"}


@functools.cache
def lexicon() -> dict[str, tuple[str, ...]]:
    return {k: tuple(v.split()) for k, v in load_table("da", "lexicon").items()}


@functools.cache
def known_words() -> frozenset[str]:
    """Words read from the lexicon or (correctly) by the rules: the parts of compounds."""
    return frozenset(lexicon()) | load_words("da", "words")


def simple_word(w: str) -> list[str]:
    """A folded word without compound splitting: lexicon, else rules."""
    lex = lexicon()
    return list(lex[w]) if w in lex else rules(w)


def split_compound(w: str) -> list[tuple[str, str]] | None:
    """[(part, linking letter or "")] of an unknown word made of 2-3 known words (each at least
    MIN_PART letters; a linking s or e may follow a part but the last), or None. Fewest parts,
    then fewest linking letters, then the longest first part."""
    known = known_words()
    n = len(w)
    best: tuple[tuple[int, int, int], list[tuple[str, str]]] | None = None

    def search(i: int, parts: list[tuple[str, str]]) -> None:
        nonlocal best
        if len(parts) > 3:
            return
        for j in range(n, i + MIN_PART - 1, -1):
            part = w[i:j]
            if part not in known:
                continue
            if j == n:
                if parts:
                    cand = parts + [(part, "")]
                    key = (len(cand), sum(1 for _, s in cand if s), -len(cand[0][0]))
                    if best is None or key < best[0]:
                        best = (key, cand)
                continue
            if n - j >= MIN_PART:
                search(j, parts + [(part, "")])
            if j < n and w[j] in LINKS and n - j - 1 >= MIN_PART:
                search(j + 1, parts + [(part, w[j])])

    search(0, [])
    return best[1] if best else None


def compound_tokens(parts: list[tuple[str, str]]) -> list[str]:
    """Parts read as words: the first keeps the primary stress, later ones get a secondary
    stress; stød is dropped from all parts but the last."""
    out: list[str] = []
    for k, (part, link) in enumerate(parts):
        toks = simple_word(part)
        if k > 0:
            toks = [SECONDARY if t == PRIMARY else t for t in toks]
        if k + 1 < len(parts):
            toks = [t for t in toks if t != STOD]
        out += toks
        if link:
            out.append("s" if link == "s" else "@")
    return out


def word_tokens_names(word: str) -> list[str]:
    """da-en token names (without the prefix) of one normalized word."""
    w = fold(word)
    if not w:
        return []
    if not any(_vowel(c) for c in w) and w not in lexicon():
        return [t for c in w for t in word_tokens_names(LETTER_NAMES[c])] if len(w) <= 6 else rules(w)
    if w in lexicon():
        toks = list(lexicon()[w])
    else:
        parts = split_compound(w) if w not in known_words() else None
        toks = compound_tokens(parts) if parts else rules(w)
    if w in UNSTRESSED:
        toks = [t for t in toks if t not in (PRIMARY, SECONDARY)]
    return toks


def word_tokens_da(word: str) -> list[str]:
    """da-en tokens of one normalized Danish word ([] when it has nothing to read)."""
    return [f"DA:{t}" for t in word_tokens_names(word)]


# ---------------- tagging and corpus helpers ----------------

DANISH_ONLY = "æøåé"


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word could be Danish: a known Danish word, or no letters and
    letter groups that Danish words do not have (w q x z c outside ck/ch, th ph sh ea oa ee oo
    ou ay ey oy aw ow) and it does not end in a vowel other than e (English final y, a, o ...)."""
    if not w or not w.isascii() or not w.isalpha():
        return False
    if w in known_words() or split_compound(w):
        return True
    if any(c in w for c in "wqxz") or "c" in w.replace("ck", "").replace("ch", ""):
        return False
    if any(g in w for g in ("th", "ph", "sh", "ea", "oa", "ee", "oo", "ou", "ay", "ey", "oy", "aw",
                            "ow", "gh", "wh", "tch", "dge")):
        return False
    return w[-1] not in "aiouy" or len(w) <= 3


def unreadable_da(text: str) -> list[str]:
    """Letters the Danish front-end cannot read (other scripts than Latin), to filter training
    sentences."""
    out = []
    for ch in text:
        if not ch.isalpha() or ch.isascii() or ch in DANISH_ONLY or ch.lower() in DANISH_ONLY:
            continue
        if ch.lower() not in FOLD and ch.lower() not in "æøåé":
            out.append(ch)
    return out


