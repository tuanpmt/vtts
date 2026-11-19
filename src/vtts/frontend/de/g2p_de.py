"""German word -> de-en tokens (morphs, spelling rules, vowel length, stress).

A word (lower case, after normalize_de) is first looked up in lexicons/de/overrides.tsv (phonemes
for function words and words the rules read wrongly). Otherwise it is read in four steps:

1. Morphs. A number word (zweitausendsechsundzwanzig) is cut into number morphs. Any other word is
   cut by a lowest-cost split into prefixes (be- ge- ver- ... unstressed, ab- an- auf- ... with
   their own stress), stems of lexicons/de/stems.txt, suffixes (-ung -heit -lich -chen, endings
   -e -en -er -t -st ...) and linking elements (-s- -es- -n- -en- -e- -er-) between the parts of a
   compound; text not covered by the stem list is an "unknown" stem read by the rules. The split
   has the fewest unknown pieces, then covers the most letters with known pieces, then has the
   fewest pieces. Restrictions keep the split honest: a prefix before an unknown stem needs a full
   vowel in the rest of the word and a German onset; an unknown stem inside a word starts with a
   consonant and has at least four letters; endings like -t -st -te only follow a known stem; no
   cut inside a double consonant after an unknown stem.
2. Graphemes per morph group (a stem with its suffixes): sch, tsch, ch, chs, ck, ph, th, qu, ng,
   tz, dt, doubled consonants, ß; aa ee oo ie ei ey ai ay au eu äu. A vowel-initial suffix is read
   together with its stem (Ta-ge), a consonant-initial one after a boundary (Tag+s).
3. Stress. The first stressed prefix (an-, auf-, un- ...) or else the first stem carries the
   primary stress; each stem has its own (secondary, unmarked) stress. Inside a stem: a stress
   mark of the stem list, else a stressed foreign ending (-ion -ität -ieren -ie -ur -ent -ant
   -enz -al -ell -ett -iv -ös -eur -är -at -on -ee -ei -ismus -ist ...), the syllable before
   -ik -isch -iker -ika -ium -ien (Politik, Technik, politisch, Gymnasium), else the first
   syllable. über- unter- hinter- wider- are unstressed before a verb ending or -ung
   (übersetzen, Unterstützung).
4. Sounds. Vowels: long before h, ß, a single consonant and a vowel (Na-me), at the end of a
   stressed stem closed by one consonant (Tag, Weg, sagt = sag+t) and in doubled vowels and ie;
   short before two or more consonants, doubled consonants, ck, tz, sch, ch, x, ng. An unstressed
   e after the stress or in an ending is the schwa @ (e + r at the end of a syllable is 6: Lehrer
   -> l e:1 R 6). Final devoicing of b d g s v (Tag -> t a:1 k, Haus); -ig -> I C (König), -ig +
   -lich -> I k; ch after a o u au -> x, else C, initial ch -> C before front vowels, k (Chor) or S
   (Chef); s before a vowel -> z, sp st at the start of a stem -> S p, S t; v -> f in native
   words; r after a vowel at the end of a syllable -> 6; unstressed i before the last vowel -> j
   (Radio, Million); a glottal stop ? before a vowel at the start of a word, prefix or stem.

valid_spelling() says whether a plain ASCII word could be German (latin.py uses it to tell German
from English words); lexicons/de/english.txt lists English words that German text borrows.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from dataclasses import dataclass

from ..lexicons import load_table, load_words

VOWELS = "aeiouyäöü"
LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzäöüß")
# Letters of other languages: French é is a stressed long e (Café -> kafee), others a base letter.
FOLD = {"é": "ee", "è": "ä", "ê": "ä", "æ": "ä", "œ": "ö", "ø": "ö", "ç": "s", "ł": "l", "đ": "d",
        "þ": "th", "ð": "d", "ẞ": "ß"}
LONG = {"a": "a:", "e": "e:", "i": "i:", "o": "o:", "u": "u:", "ä": "E:", "ö": "2:", "ü": "y:",
        "y": "y:"}
SHORT = {"a": "a", "e": "E", "i": "I", "o": "O", "u": "U", "ä": "E", "ö": "9", "ü": "Y", "y": "Y"}
DIGRAPHS = {"äu": "OY", "aa": "a:", "ee": "e:", "oo": "o:", "ie": "i:", "ei": "aI", "ey": "aI",
            "ai": "aI", "ay": "aI", "au": "aU", "eu": "OY"}
CONS_GRAPHEMES = ("tsch", "sch", "chs", "ch", "ck", "ph", "th", "qu", "ng", "tz", "dt")
VOWEL_PHONES = frozenset(LONG.values()) | frozenset(SHORT.values()) | {"aI", "aU", "OY", "@", "6"}
FRONT = "eiäöüy"
BACK = ("a", "o", "u", "au", "aa", "oo")

# ---------------- morph tables ----------------

# Prefixes: phonemes; "1" marks the stressed vowel of a stressed prefix (else its first vowel).
UNSTRESSED_PREFIXES = {
    "be": "b @", "ge": "g @", "ver": "f E 6", "zer": "t s E 6", "er": "E 6", "ent": "E n t",
    "emp": "E m p",
}
STRESSED_PREFIXES = {
    "ab": "a p", "an": "a n", "auf": "aU f", "aus": "aU s", "bei": "b aI", "ein": "aI n",
    "mit": "m I t", "nach": "n a: x", "vor": "f o: 6", "weg": "v E k", "zu": "t s u:",
    "zurück": "t s u: R Y1 k", "un": "U n", "ur": "u: 6", "über": "y: b 6", "unter": "U n t 6",
    "hinter": "h I n t 6", "durch": "d U 6 C", "um": "U m", "hin": "h I n", "her": "h e: 6",
    "fort": "f O 6 t", "los": "l o: s", "wieder": "v i: d 6", "wider": "v i: d 6",
    "gegen": "g e: g @ n", "voll": "f O l", "heim": "h aI m", "dar": "d a: 6", "miss": "m I s",
    "zusammen": "t s u: z a1 m @ n", "voran": "f o: R a1 n", "voraus": "f o: R aU1 s",
    "vorbei": "f o: 6 b aI1", "herein": "h E R aI1 n", "heraus": "h E R aU1 s",
    "herum": "h E R U1 m", "hinein": "h I n aI1 n", "hinaus": "h I n aU1 s",
    "herab": "h E R a1 p", "hinab": "h I n a1 p", "herbei": "h e: 6 b aI1", "empor": "E m p o:1 6",
    "entgegen": "E n t g e:1 g @ n", "nieder": "n i: d 6",
}
# über- unter- hinter- wider- are unstressed before a verb form or -ung (übersetzen, Unterstützung).
INSEPARABLE_TOO = frozenset(("über", "unter", "hinter", "wider"))
VERB_ENDINGS = frozenset(("en", "ens", "t", "te", "ten", "tet", "st", "e", "et", "est", "end", "ung"))
PREFIXES = {**{k: ("up", v) for k, v in UNSTRESSED_PREFIXES.items()},
            **{k: ("sp", v) for k, v in STRESSED_PREFIXES.items()}}
# Suffixes: vowel-initial ones are read with the stem (Ta-ge); consonant-initial ones after a
# boundary; INFLECTION only after a known stem (sag+t, but Kunst is not kun+st).
VOWEL_SUFFIXES = frozenset(("e", "en", "er", "ern", "es", "em", "el", "eln", "ens", "est", "et",
                            "end", "ung", "ig", "isch", "in", "innen", "erin", "erinnen"))
DERIVATION = frozenset(("heit", "keit", "schaft", "lich", "bar", "sam", "los", "haft", "nis",
                        "nisse", "nissen", "tum", "tümer", "chen", "lein", "ling"))
INFLECTION = frozenset(("t", "st", "te", "ten", "tet", "test", "s", "n"))
LINKERS = frozenset(("s", "es", "n", "en", "e", "er", "ens"))
ALL_SUFFIXES = tuple(sorted(VOWEL_SUFFIXES | DERIVATION | INFLECTION))  # a fixed order for the split
# Annotated readings of suffixes (":" long, "." short).
SUFFIX_READING = {"bar": "ba:r", "sam": "sa:m", "los": "lo:s", "tum": "tu:m", "tümer": "tü:mer"}
NUMBER_MORPHS = ("eins", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sech", "sieben", "sieb",
                 "acht", "neun", "zehn", "elf", "zwölf", "zwanzig", "dreißig", "vierzig", "fünfzig",
                 "sechzig", "siebzig", "achtzig", "neunzig", "hundert", "tausend", "und",
                 "millionen", "million", "milliarden", "milliarde")
NUMBER_TAILS = ("ste", "ster", "sten", "stes", "stem", "te", "ter", "ten", "tes", "tem")
ONSETS = frozenset(("bl", "br", "ch", "chr", "dr", "fl", "fr", "gl", "gn", "gr", "kl", "kn", "kr",
                    "pf", "pfl", "pfr", "ph", "pl", "pr", "qu", "sch", "schl", "schm", "schn", "schr",
                    "schw", "sk", "sp", "spr", "st", "str", "th", "tr", "wr", "zw", "ps"))
INITIAL_CH_S = ("chef", "chanc", "champ", "chans", "chauff", "chaise", "charm", "chalet", "chiff",
                "chic", "chips", "chill", "chat", "check", "chor")

# ---------------- stress rules for a stem group (stem + suffixes) ----------------

_VOWEL_SET = ("a", "e", "i", "o", "u", "ä", "ö", "ü")
_T_ENT = ("e", "en", "in", "innen", "s", "es", "")
# Stressed foreign endings, checked in this order on the letters of a stem group: (befores, groups,
# after, tails, not_after). A rule matches where the letters end with before + group + after + tail
# (the leftmost such start, as a regex search would find it) and no string of not_after ends right
# before the group; the group's vowel is stressed.
STRESSED_ENDINGS = (
    (("i",), ("o",), "n", ("en", "s", ""), ()),
    (("t",), ("ä",), "t", ("en", "s", ""), ()),
    (("",), ("ie",), "r", ("e", "en", "t", "te", "ten", "tet", "test", "tes", "ter", "tem", "ung", "ungen",
                          "bar", "st", "est", "et", ""), ()),
    (("",), ("i",), "smus", ("",), ()),
    (("",), ("i",), "st", ("en", "in", "innen", "isch", "ische", "ischen", "ischer", "isches", "ik", ""), ()),
    (("",), ("u",), "r", ("en", ""), ()),
    (("",), ("e",), "nt", _T_ENT, ()),
    (("",), ("a",), "nt", _T_ENT, ()),
    (("",), ("a", "e"), "nz", ("en", ""), ()),
    (("",), ("i",), "nz", ("en", ""), ()),
    (("",), ("a",), "r", ("e", "en", "s", "es", "in", "innen", ""), _VOWEL_SET),
    (("",), ("i",), "l", ("e", "en", "s", "es", "er", "em", ""), _VOWEL_SET),
    (("",), ("o",), "l", ("e", "en", "s", "es", ""), _VOWEL_SET),
    (("",), ("a",), "l", ("e", "en", "es", "er", "em", "s", "ität", "itäten", ""), ()),
    (("",), ("e",), "ll", ("e", "en", "es", "er", "em", "s", ""), ()),
    (("",), ("a",), "ll", ("e", "en", "s", "es", ""), ()),
    (("",), ("e",), "tt", ("e", "en", "s", ""), ()),
    (("",), ("o",), "tt", ("e", "en", "s", ""), ()),
    (("",), ("i",), "v", ("e", "en", "er", "es", "em", "s", ""), ()),
    (("",), ("ö",), "s", ("e", "en", "er", "es", "em", ""), ()),
    (("",), ("eu",), "r", ("e", "en", "in", "innen", "s", ""), ()),
    (("",), ("eu",), "s", ("e", "en"), ()),
    (("",), ("ä",), "r", ("e", "en", "in", "innen", "s", ""), ()),
    (("",), ("a",), "t", ("e", "en", "es", "s", "in", "innen", ""), ()),
    (("",), ("o",), "n", ("e", "en", "s", ""), ()),
    (("",), ("ee",), "", ("n", "s", ""), ()),
    (("",), ("ie",), "", ("n", "s", ""), ()),
    (("",), ("ei",), "", ("en", "s", ""), ("erl",)),
    (("",), ("e",), "kt", ("e", "en", "s", "es", ""), ()),
    (("",), ("a",), "kt", ("e", "en", "s", "es", ""), ()),
    (("",), ("i",), "kt", ("e", "en", "s", "es", ""), ()),
    (("",), ("u",), "kt", ("e", "en", "s", "es", ""), ()),
    (("",), ("e",), "pt", ("e", "en", "s", "es", ""), ()),
    (("",), ("e",), "ss", ("e", "en", "es", "in", "innen", ""), ()),
    (("",), ("a",), "mm", ("e", "en", "s", ""), ()),
    (("bl", "st"), ("e",), "m", ("e", "en", "s", ""), ()),
    (("",), ("ü",), "r", ("e", "en"), ()),
    (("",), ("a",), "n", ("er", "erin", "erinnen", "ern", "s", ""), ()),
)
# Excluded from the stressed endings: words ending in one of NOT_STRESSED_ENDS (+ s, e, en), in
# -erlei (not after i), and the words of NOT_STRESSED_WORDS (native words, -sal, -stan ...).
NOT_STRESSED_ENDS = ("sal", "sale", "salen", "stan", "mals", "monat", "monate", "monaten", "heimat",
                     "heirat", "leumund")
NOT_STRESSED_TAILS = ("s", "e", "en", "")
NOT_STRESSED_WORDS = frozenset((
    "kanon", "lexikon", "marathon", "bison", "python", "natron", "bariton", "ypsilon", "satan", "sultan",
    "japan", "harem", "totem", "atem", "karneval", "kaffee", "abend", "jugend", "tugend", "januar",
    "februar", "april", "nachbar", "zucker", "london", "christian", "sebastian"))
# The syllable before these endings is stressed (Politik is in STRESSED_IK); the longest ending that
# the letters end with counts.
BEFORE_ENDINGS = ("ik", "iker", "ikerin", "ikerinnen", "ikern", "ika", "ikum", "ium", "ius", "ien", "ie",
                  "isch", "ische", "ischen", "ischer", "isches", "ischem", "tor", "tore", "toren", "sor")
STRESSED_IK = frozenset(("musik", "politik", "physik", "kritik", "fabrik", "republik", "mathematik",
                         "mosaik", "rubrik", "katholik", "replik", "informatik"))
OREN_TAILS = ("en", "in", "innen")  # -oren -orin -orinnen: o stressed (Professoren)
# Words in -ie / -ien whose ending is unstressed ([i̯ə]): Familie, Ferien, Italien.
UNSTRESSED_IE = (
    "familie", "linie", "serie", "studie", "folie", "lilie", "arie", "komödie", "tragödie", "prämie",
    "materie", "petersilie", "hostie", "akazie", "bestie", "historie", "kastanie", "geranie",
    "begonie", "pinie", "glorie", "grazie", "orgie", "aktie", "ferie", "medie", "spezie", "zeremonie",
    "kolonie_", "pietie",
)
STRESSED_IEN = ("logie", "grafie", "graphie", "sophie", "kratie", "nomie", "pathie", "therapie",
                "metrie", "skopie", "energie", "strategie", "industrie", "theorie", "kategorie",
                "batterie", "galerie", "kopie", "akademie", "fantasie", "phantasie", "melodie",
                "harmonie", "kolonie", "monarchie", "garantie", "chemie", "partie", "allergie",
                "anarchie", "hierarchie", "magie", "regie", "sinfonie", "symphonie", "utopie",
                "ironie", "manie", "lotterie", "infanterie", "artillerie", "drogerie", "parfümerie",
                "maschinerie", "biografie", "fotografie", "geografie", "demokratie", "bürokratie",
                "aristokratie", "diplomatie", "ökonomie", "astronomie", "philosophie", "sympathie",
                "poesie", "genie", "linie_")
FOREIGN_ENDS = ("ion", "ionen", "ität", "itäten", "ie", "ien", "ik", "iker", "ismus", "ent", "enten",
                "ant", "anten", "anz", "enz", "iv", "ive", "iven", "ell", "elle", "ellen", "al", "ale",
                "alen", "isch", "ische", "ischen", "ischer", "isches")
FOREIGN_ENDS_IER = ("ier", "iere", "ieren", "iert", "ierte", "ierten", "iertet", "ierung", "ierungen")
PENULT_VOWELS = "aiouäöü"  # V C e(n|s) at the end of a word of 3+ syllables: Tomate, Maschine
PENULT_E_BEFORE = "bdgkmpsvz"  # e as V only before these
PENULT_CONS = "bdgklmnprstvz"
FULL_VOWEL_ENDING = "nrlmstd"  # e + these letters at the end is an ending, not a full vowel


def _ending_group(text: str, rule) -> int | None:
    """Position of the stressed group of a STRESSED_ENDINGS rule, or None."""
    befores, groups, after, tails, not_after = rule
    for start in range(len(text) + 1):
        for b in befores:
            if not text.startswith(b, start):
                continue
            g0 = start + len(b)
            for grp in groups:
                if not text.startswith(grp, g0) or any(text[:g0].endswith(x) for x in not_after):
                    continue
                a0 = g0 + len(grp)
                if text.startswith(after, a0) and text[a0 + len(after):] in tails:
                    return g0
    return None


def _not_stressed(text: str) -> bool:
    if text in NOT_STRESSED_WORDS:
        return True
    if any(text.endswith(e + t) for e in NOT_STRESSED_ENDS for t in NOT_STRESSED_TAILS):
        return True
    return text.endswith("erlei") and (len(text) == 5 or text[-6] != "i")


def _suffix_start(text: str, ends) -> int | None:
    """Start of the longest of `ends` that text ends with, or None."""
    starts = [len(text) - len(e) for e in ends if text.endswith(e)]
    return min(starts) if starts else None


def _penult(text: str) -> tuple[int, int] | None:
    """(vowel position, consonant position) of V C e(n|s) at the end of text, or None."""
    n = len(text)
    for st, tail in ((n - 4, True), (n - 3, False)):
        if st < 0:
            continue
        if tail and text[n - 1] not in "ns":
            continue
        v, c, e = text[st], text[st + 1], text[st + 2]
        if e != "e" or c not in PENULT_CONS:
            continue
        if not (v in PENULT_VOWELS or (v == "e" and c in PENULT_E_BEFORE)):
            continue
        if st > 0 and text[st - 1] in "aeiouäöüy":
            continue
        return st, st + 1
    return None


def _number_word(w: str) -> bool:
    """w is number morphs (NUMBER_MORPHS) and an optional ordinal ending (NUMBER_TAILS)."""
    n = len(w)
    ok = [False] * (n + 1)
    ok[0] = True
    for i in range(n):
        if ok[i]:
            for m in NUMBER_MORPHS:
                if w.startswith(m, i):
                    ok[i + len(m)] = True
    return ok[n] or any(ok[n - len(t)] for t in NUMBER_TAILS if n > len(t) and w.endswith(t))


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("de", "overrides")


@functools.cache
def stem_table() -> dict[str, str]:
    """Plain stem -> annotated stem (':' long, '.' short, "'" stress before a vowel)."""
    out: dict[str, str] = {}
    for w in sorted(load_words("de", "stems")):
        key = re.sub(r"[:.']", "", w)
        if len(key) < 3 or not any(ch in VOWELS for ch in key) or key in PREFIXES:
            continue
        if key not in out or key == out[key]:  # an annotated entry wins over a plain one
            out[key] = w
    return out


def fold(word: str) -> str:
    """Lower case, German letters kept, other accented letters reduced to a base letter."""
    out = []
    for ch in word.lower():
        if ch in LETTERS:
            out.append(ch)
        elif ch in FOLD:
            out.append(FOLD[ch])
        else:
            base = unicodedata.normalize("NFKD", ch)[0]
            if base.isascii() and base.isalpha():
                out.append(base.lower())
    return "".join(out)


# ---------------- 1. morphs ----------------

@dataclass
class Piece:
    kind: str  # up, sp (prefixes), stem, unk, suf, inf (inflection), lnk
    text: str  # plain letters
    ann: str  # annotated letters (stems, suffix readings)


def _full_vowel(rest: str) -> bool:
    """A vowel other than the e of an ending (stern, geben, Gegend have none after ge-/be-)."""
    k = len(rest)
    while k > 0 and rest[k - 1] in FULL_VOWEL_ENDING:
        k -= 1
    core = rest[:k - 1] if k > 0 and rest[k - 1] == "e" else rest
    return any(ch in VOWELS for ch in core)


def _onset(rest: str) -> str:
    k = 0
    while k < len(rest) and rest[k] not in VOWELS:
        k += 1
    return rest[:k]


def _prefix_ok(prefix: str, rest: str) -> bool:
    """May `prefix` stand before the unknown stem `rest`? Not before a foreign stressed ending
    (Generation, Geometrie; for stressed prefixes also -ieren: absolvieren)."""
    if len(rest) < 3 or not _full_vowel(rest):
        return False
    if rest.endswith(FOREIGN_ENDS) or (prefix in STRESSED_PREFIXES and rest.endswith(FOREIGN_ENDS_IER)):
        return False
    on = _onset(rest)
    if not on:
        return prefix in ("be", "ge", "ver", "zer", "ent") and rest[0] in "aiouäöü" and len(rest) >= 4
    if prefix == "emp":
        return rest[0] == "f"
    sch_onset = on.startswith("sch") and on[3:] in ("", "l", "m", "n", "r", "w")
    if len(on) > 1 and on not in ONSETS and not sch_onset:
        return False
    return prefix[-1] != rest[0]  # Anna, Mitte, Herren: a doubled consonant, not a prefix


def _inside_grapheme(w: str, i: int) -> bool:
    """Would a cut before w[i] split sch, ch, ck, ph, th, tz, a doubled letter or a vowel digraph?"""
    a, b = w[i - 1], w[i]
    if a == b:  # Volks|schule, aus|stellen: a cut before a consonant cluster is fine
        return not (i + 1 < len(w) and w[i + 1] not in VOWELS and b not in VOWELS)
    if a + b == "ng":
        return True
    if a + b in ("ch", "ck", "ph", "th", "tz", "qu") or w[i - 1:i + 2] == "sch" or (
            i >= 2 and w[i - 2:i + 1] == "sch"):
        return True
    return a + b in DIGRAPHS


def _split_cost(pieces: list[Piece]) -> tuple[int, int, int, int]:
    unk = sum(p.kind == "unk" for p in pieces)
    known = sum(len(p.text) for p in pieces if p.kind != "unk")
    return unk, -known, len(pieces), sum(p.kind in ("inf", "lnk") for p in pieces)


@functools.lru_cache(maxsize=65536)
def segment(w: str) -> tuple[Piece, ...]:
    """Lowest-cost split of a folded word into morphs (see the module docstring)."""
    stems = stem_table()
    n = len(w)
    # best[(i, state)] = (cost, pieces); state: start pre root suf lnk (+ whether the root is a stem)
    best: dict[tuple[int, str], tuple[tuple[int, int, int, int], list[Piece]]] = {(0, "start"): ((0, 0, 0), [])}

    def push(j: int, state: str, pieces: list[Piece]) -> None:
        cost = _split_cost(pieces)
        if (j, state) not in best or cost < best[(j, state)][0]:
            best[(j, state)] = (cost, pieces)

    foreign = w.endswith(FOREIGN_ENDS) or w.endswith(FOREIGN_ENDS_IER)
    for i in range(n):
        inside = 0 < i < n and _inside_grapheme(w, i)
        for state in ("start", "pre", "stem", "unk", "suf", "lnk"):
            if (i, state) not in best or (inside and state != "pre" and not (state == "stem" and w.startswith("chen", i))):
                continue
            _, pieces = best[(i, state)]
            rest = w[i:]
            prev = pieces[-1] if pieces else None
            # prefixes
            for p, (kind, _) in PREFIXES.items():
                if kind == "up" and prev is not None and prev.kind in ("up", "unk"):
                    continue
                if prev is not None and prev.kind == "unk" and len(prev.text) < 5:
                    continue
                if p == "er" and prev is not None and prev.kind in ("stem", "suf", "inf"):
                    continue
                if rest.startswith(p) and len(rest) > len(p):
                    push(i + len(p), "pre", [*pieces, Piece(kind, p, p)])
            # stems
            for j in range(i + 3, n + 1):
                sub = w[i:j]
                if sub in stems:
                    if prev is not None and prev.kind == "unk" and prev.text[-1] == sub[0]:
                        continue
                    if i > 0 and sub[0] in VOWELS and (len(sub) < 4 or prev.kind == "unk"):
                        continue
                    if prev is not None and prev.kind == "unk" and (len(prev.text) < 5 or foreign or len(sub) < 4):
                        continue
                    push(j, "stem", [*pieces, Piece("stem", sub, stems[sub])])
            # unknown stems
            if state != "unk":
                for j in range(i + 3, n + 1):
                    sub = w[i:j]
                    if not any(ch in VOWELS for ch in sub):
                        continue
                    if i > 0 and (sub[0] in VOWELS or len(sub) < 4):
                        continue
                    if sub in DERIVATION or sub in VOWEL_SUFFIXES or (i > 0 and sub[0] == sub[1]):
                        continue
                    if prev is not None and prev.kind in ("up", "sp") and not _prefix_ok(prev.text, w[i:]):
                        continue
                    if prev is not None and prev.text[-1] == sub[0] and prev.kind in ("up", "sp", "stem"):
                        continue
                    push(j, "unk", [*pieces, Piece("unk", sub, sub)])
            # suffixes and linkers
            if state in ("stem", "unk", "suf"):
                for s in ALL_SUFFIXES:
                    if not rest.startswith(s):
                        continue
                    kind = "inf" if s in INFLECTION else "suf"
                    root = next(q for q in reversed(pieces) if q.kind in ("stem", "unk"))
                    if kind == "inf" and root.kind == "unk" and not (
                            prev is root and len(root.text) >= 3 and root.text[-1] in "bg" and s[0] in "st"
                            and root.text[-2] in VOWELS and root.text[-3] not in VOWELS):
                        continue
                    if s == "chen" and (prev.text[-1] in VOWELS or (prev.text[-1] == "s" and prev.kind != "stem")):
                        continue
                    if prev.text[-1] == s[0] and s[0] not in VOWELS:
                        continue
                    push(i + len(s), "suf", [*pieces, Piece(kind, s, SUFFIX_READING.get(s, s))])
                if i > 0 and prev.kind != "unk":
                    for s in sorted(LINKERS):
                        if rest.startswith(s) and len(rest) > len(s):
                            push(i + len(s), "lnk", [*pieces, Piece("lnk", s, s)])
    finals = [best[(n, s)] for s in ("stem", "unk", "suf") if (n, s) in best]
    if not finals:
        return (Piece("unk", w, w),)
    return tuple(min(finals, key=lambda x: x[0])[1])


def _number_pieces(w: str) -> list[Piece] | None:
    """zweitausendsechsundzwanzig -> zwei tausend sechs und zwanzig (stems), or None."""
    if len(w) < 3 or not _number_word(w):
        return None
    out, i = [], 0
    morphs = sorted(NUMBER_MORPHS, key=len, reverse=True)
    while i < len(w):
        for m in morphs:
            if w.startswith(m, i):
                out.append(Piece("stem", m, stem_table().get(m, m)))
                i += len(m)
                break
        else:
            out.append(Piece("inf", w[i:], w[i:]))
            break
    return out


# ---------------- 2.-4. reading ----------------

@dataclass
class Grapheme:
    text: str
    kind: str  # V or C
    unit: int
    pos: int  # letter index in the group
    flags: str
    piece: str  # kind of the piece of its first letter
    glide: bool = False
    silent: bool = False
    ts: bool = False  # t of -tion read ts


def _annotated(ann: str) -> list[tuple[str, str]]:
    """'zur'ück' -> letters with flags L (long), S (short), ' (stressed)."""
    out: list[tuple[str, str]] = []
    pending = ""
    for ch in ann:
        if ch == "'":
            pending = "'"
        elif ch == ":":
            out[-1] = (out[-1][0], out[-1][1] + "L")
        elif ch == ".":
            out[-1] = (out[-1][0], out[-1][1] + "S")
        else:
            out.append((ch, pending))
            pending = ""
    return out


def _graphemes(letters: list[tuple[str, str, str, int]]) -> list[Grapheme]:
    """letters: (letter, flags, piece kind, unit) of one group."""
    out: list[Grapheme] = []
    k = 0
    n = len(letters)

    def same_unit(a: int, b: int) -> bool:
        return b < n and letters[a][3] == letters[b][3]

    while k < n:
        ch, flags, piece, unit = letters[k]
        text = None
        if ch in VOWELS:
            two = ch + letters[k + 1][0] if same_unit(k, k + 1) else ""
            if two in DIGRAPHS and not (ch == "e" and two == "eu" and "S" in letters[k + 1][1]):
                text = two
            if ch == "y" and same_unit(k, k + 1) and letters[k + 1][0] in VOWELS and (
                    k == 0 or letters[k - 1][3] != unit):
                out.append(Grapheme("y", "C", unit, k, flags, piece))
                k += 1
                continue
            text = text or ch
            fl = "".join(letters[j][1] for j in range(k, k + len(text)))
            out.append(Grapheme(text, "V", unit, k, fl, piece))
            k += len(text)
            continue
        for g in CONS_GRAPHEMES:
            if g == "chs" and out and out[-1].kind == "V" and "L" in out[-1].flags:
                continue
            if all(same_unit(k, k + j) or j == 0 for j in range(len(g))) and \
                    "".join(letters[j][0] for j in range(k, min(n, k + len(g)))) == g:
                text = g
                break
        if text is None:
            text = ch
            if same_unit(k, k + 1) and letters[k + 1][0] == ch and ch not in VOWELS:
                text = ch + ch
        out.append(Grapheme(text, "C", unit, k, flags, piece))
        k += len(text)
    for j, g in enumerate(out):  # h after a vowel lengthens it and is silent
        if g.text == "h" and j > 0 and out[j - 1].kind == "V" and out[j - 1].unit == g.unit:
            g.silent = True
    return out


def _vowel_at(gs: list[Grapheme], pos: int) -> int | None:
    for j, g in enumerate(gs):
        if g.kind == "V" and g.pos <= pos < g.pos + len(g.text):
            return j
    return None


def _ie_unstressed(text: str) -> bool:
    base = text[:-1] if text.endswith("ien") else text
    if not base.endswith("ie"):
        return False
    if base.endswith(UNSTRESSED_IE):
        return True
    if text.endswith("ien"):
        if not any(ch in VOWELS for ch in text[:-3]):  # Wien
            return False
        return not base.endswith(STRESSED_IEN)
    return False


def _head(gs: list[Grapheme], text: str, root_end: int) -> int | None:
    """Index of the stressed vowel grapheme of a group (stem + suffixes)."""
    vowels = [j for j, g in enumerate(gs) if g.kind == "V" and not g.glide]
    if not vowels:
        return None
    marked = [j for j in vowels if "'" in gs[j].flags]
    if marked:
        return marked[0]
    root_vowels = [j for j in vowels if gs[j].pos < root_end] or vowels
    if len(vowels) >= 2 and not _not_stressed(text):
        if text.endswith("ik") and text in STRESSED_IK:
            return vowels[-1]
        oren = _suffix_start(text, tuple("or" + t for t in OREN_TAILS))
        if oren is not None and len(vowels) >= 3:
            return _vowel_at(gs, oren)
        before_end = _suffix_start(text, BEFORE_ENDINGS)
        if before_end is None or (text.endswith(("ie", "ien")) and not _ie_unstressed(text)):
            for rule in STRESSED_ENDINGS:
                g0 = _ending_group(text, rule)
                if g0 is not None:
                    j = _vowel_at(gs, g0)
                    if j is not None and gs[j].pos < root_end:
                        return j
                    break
            pen = _penult(text)
            if pen is not None and len(vowels) >= 3 and not (text[pen[0]] == "i" and text[pen[1]] == "g"):
                j = _vowel_at(gs, pen[0])
                if j is not None and pen[1] < root_end:
                    return j
        if before_end is not None:
            before = [j for j in vowels if gs[j].pos < before_end]
            if before:
                j = before[-1]
                # -erisch, -elisch: skip the schwa syllable (regnerisch)
                if gs[j].text == "e" and len(before) > 1 and text[before_end - 1] in "rln":
                    j = before[-2]
                return j
    return root_vowels[0]


def _ig_g(gs: list[Grapheme], j: int, head: int | None, next_text: str) -> str | None:
    """-ig: g after an unstressed i at the end of a unit or before t, st, s (+ e ...) is C
    (König, beschäftigt); before -lich k (königlich)."""
    if j == 0 or gs[j - 1].kind != "V" or gs[j - 1].text != "i" or j - 1 == head:
        return None
    rest = "".join(g.text for g in gs[j + 1:] if g.unit == gs[j].unit)
    if rest not in IG_REST:
        return None
    if not rest:
        later = "".join(g.text for g in gs[j + 1:]) or next_text
        if later.startswith("lich"):
            return "k"
    return "C"


IG_REST = frozenset(("", "s", "st", "t", "te", "ten", "ter", "tes", "tem", "tet", "test", "ste", "sten",
                     "ster", "stes", "stem"))


def _read_group(gs: list[Grapheme], head: int | None, primary: bool, start: str,
                next_text: str) -> list[str]:
    """Phonemes of one group; start is how the group begins: word, | (after a prefix), # (stem)."""
    out: list[str] = []
    n = len(gs)
    for j, g in enumerate(gs):
        unit_first = j == 0 or gs[j - 1].unit != g.unit
        nxt = gs[j + 1] if j + 1 < n and gs[j + 1].unit == g.unit else None
        prv = gs[j - 1] if j > 0 and gs[j - 1].unit == g.unit else None
        if g.kind == "V":
            if unit_first and j == 0:
                out.append("?")
            out.append(_vowel(gs, j, head) + ("1" if primary and j == head else ""))
            continue
        if g.silent:
            continue
        out += _consonant(gs, j, g, prv, nxt, j == 0, head, next_text)
    # e + coda r: @ 6 -> 6
    res: list[str] = []
    for p in out:
        if p == "6" and res and res[-1] == "@":
            res[-1] = "6"
            continue
        res.append(p)
    return [p for p in res if p]


REDUCE_CODA = frozenset(("", "n", "r", "l", "m", "s", "t", "nd", "nt", "ns", "rn", "rs", "rt", "st",
                         "ls", "lt", "ms", "mt", "nst", "rst", "nds", "ndt", "rr", "ss", "ll", "nn",
                         "mm", "tt", "rnt"))


def _vowel(gs: list[Grapheme], j: int, head: int | None) -> str:
    g = gs[j]
    if g.glide:
        return "j"
    if g.text in DIGRAPHS:
        if g.text == "ie" and "@" in g.flags:
            return "@"
        nxt = gs[j + 1] if j + 1 < len(gs) and gs[j + 1].unit == g.unit else None
        if g.text == "eu" and nxt is not None and nxt.text == "r" and (
                j + 2 >= len(gs) or gs[j + 2].kind == "V" or gs[j + 2].unit != g.unit):
            return "2:"
        return DIGRAPHS[g.text]
    v = g.text
    if "S" in g.flags:
        return SHORT[v]
    if "L" in g.flags:
        return LONG[v]
    if "@" in g.flags:
        return "@"
    after = [x for x in gs[j + 1:] if x.unit == g.unit]
    cons: list[Grapheme] = []
    for x in after:
        if x.kind == "V":
            break
        cons.append(x)
    vowel_after = len(cons) < len(after)
    if v == "e" and j != head and (g.piece in ("suf", "inf", "lnk") or (head is not None and j > head)):
        if not cons and vowel_after:
            return "e:"
        if j > 0 and gs[j - 1].kind == "V" and gs[j - 1].text == "a" and gs[j - 1].unit == g.unit:
            return "e:"
        if vowel_after or g.piece != "stem" and g.piece != "unk" or "".join(c.text for c in cons) in REDUCE_CODA:
            return "@"
        return "E"
    if j != head and head is not None:
        if v == "a" and j < head:
            return "a"
        if v == "i" and cons and cons[0].text in ("g", "k", "ck"):
            return "I"
        if len(cons) == 1 and cons[0].text in ("r", "rr") and not vowel_after and v != "e":
            return LONG[v]
    if cons and cons[0].silent:
        return LONG[v]
    if not cons:
        if not vowel_after and v == "y":
            return "i:"
        return LONG[v]
    c0 = cons[0].text
    if c0 == "ß":
        return LONG[v]
    if len(cons) == 2 and vowel_after and cons[0].text in "bdgkptf" and cons[1].text in ("l", "r") \
            and len(cons[0].text) == 1:
        return LONG[v]
    if len(cons) == 1 and (len(c0) == 1 or c0 in ("ph", "th")) and c0 != "x":
        if vowel_after:
            return LONG[v]
        return LONG[v] if j == head else SHORT[v]
    return SHORT[v]


def _consonant(gs, j, g, prv, nxt, stem_start, head, next_text) -> list[str]:
    t = g.text
    nv = nxt is not None and nxt.kind == "V"
    if t in ("sch",):
        return ["S"]
    if t == "tsch":
        return ["t", "S"]
    if t == "chs":
        return ["k", "s"]
    if t == "ch":
        if g.piece in ("suf", "inf") and prv is None:
            return ["C"]
        if prv is None and stem_start:
            word = "".join(x.text for x in gs[j:])
            if word.startswith(INITIAL_CH_S) and not word.startswith("chor"):
                return ["S"]
            if nxt is not None and nxt.text[0] in FRONT:
                return ["C"]
            return ["k"]
        if prv is not None and prv.kind == "V" and prv.text in BACK and not prv.glide:
            return ["x"]
        return ["C"]
    if t == "ck":
        return ["k"]
    if t == "ph":
        return ["f"]
    if t == "th":
        return ["t"]
    if t == "qu":
        return ["k", "v"]
    if t == "ng":
        return ["N"]
    if t in ("tz", "zz", "z"):
        return ["t", "s"]
    if t == "dt":
        return ["t"]
    if t == "x":
        return ["k", "s"]
    if t in ("ß", "ss"):
        return ["s"]
    if t == "c":
        return ["t", "s"] if nxt is not None and nxt.text[0] in "eiäy" else ["k"]
    if t == "h":
        return ["h"]
    if t == "j" or t == "y":
        return ["j"]
    if t == "w":
        return ["v"]
    if t == "t" and g.ts:
        return ["t", "s"]
    if t in ("r", "rr"):
        if nv or (prv is not None and prv.kind == "C" and nxt is not None):
            return ["R"]
        if prv is None and nxt is not None:
            return ["R"]
        return ["6"]
    if t == "s":
        word_rest = "".join(x.text for x in gs[j + 1:] if x.unit == g.unit)
        if prv is None and stem_start and word_rest[:1] in ("p", "t") and g.piece not in ("suf", "inf"):
            return ["S"]
        if nv and (prv is None or prv.kind == "V" or prv.text in ("l", "m", "n", "r", "ng", "rr", "ll", "mm", "nn")):
            return ["z"]
        return ["s"]
    if t == "n" and nxt is not None and nxt.text in ("k", "ck"):
        return ["N"]
    if t == "g":
        ig = _ig_g(gs, j, head, next_text) if (nxt is None or not nv) else None
        if ig:
            return [ig]
    if t in ("v", "vv"):
        if prv is None:
            word = "".join(x.text for x in gs[j:])
            return ["f"] if _native_v(word) else ["v"]
        if prv.kind == "V" and nv:
            return ["v"]
        return ["f"]
    base = t[0]
    if base in "bdg":
        voiced = nxt is not None and (nv or nxt.text in ("l", "r", "n", "j", "w", "ll", "rr", "nn"))
        if not voiced:
            return [{"b": "p", "d": "t", "g": "k"}[base]]
        return [base]
    if base in "lmnkptfhj":
        return [base]
    return list(OTHER_CONSONANTS.get(base, ()))  # cc qq ww ßß xx and a q without u


OTHER_CONSONANTS = {"c": ("k",), "q": ("k",), "w": ("v",), "ß": ("s",), "x": ("k", "s")}


# v is f in native words: v + one of NATIVE_V_START (Vater, viel, von), or v + one of NATIVE_V_WORD
# as the whole rest (Vers).
NATIVE_V_START = ("ater", "ätter", "etter", "eil", "ie", "iel", "ier", "ogel", "ögel", "olk", "ölk",
                  "oll", "om", "on", "or", "ör", "orn", "order", "ögte", "ogt", "iert")
NATIVE_V_WORD = ("ers", "erse", "ersen")


def _native_v(word: str) -> bool:
    return word.startswith("v") and (word[1:].startswith(NATIVE_V_START) or word[1:] in NATIVE_V_WORD)


def _group_units(pieces: list[Piece]) -> list[tuple[str, list[int]]]:
    """Groups: ("pre", [piece]) for a prefix, ("root", [pieces]) for a stem with its suffixes."""
    groups: list[tuple[str, list[int]]] = []
    for k, p in enumerate(pieces):
        if p.kind in ("up", "sp"):
            groups.append(("pre", [k]))
        elif p.kind in ("stem", "unk") or not groups or groups[-1][0] == "pre":
            groups.append(("root", [k]))
        else:
            groups[-1][1].append(k)
    return groups


def _pieces(w: str) -> list[Piece]:
    pieces = _number_pieces(w)
    if pieces is None:
        if w in stem_table():
            pieces = [Piece("stem", w, stem_table()[w])]
        else:
            pieces = list(segment(w))
    pieces = _split_root_prefix(pieces)
    # über- unter- hinter- wider- before a verb form or -ung: unstressed (übersetzen)
    if pieces and pieces[0].kind == "sp" and pieces[0].text in INSEPARABLE_TOO and len(pieces) > 1:
        rest = "".join(p.text for p in pieces[1:])
        ending = pieces[-1].kind in ("suf", "inf") and pieces[-1].text in VERB_ENDINGS
        if pieces[1].text != "ge" and (rest.endswith(("ung", "ungen")) or ending):
            pieces[0] = Piece("up", pieces[0].text, pieces[0].ann)
    return pieces


def _split_root_prefix(pieces: list[Piece]) -> list[Piece]:
    """be- ge- ver- zer- ent- emp- er- at the start of a stem of the list or an unknown stem is a
    prefix when the rest is a stem or passes _prefix_ok (Gemeinde, besuchte, Verein)."""
    out: list[Piece] = []
    stems = stem_table()
    for k, p in enumerate(pieces):
        if p.kind in ("stem", "unk") and (k == 0 or pieces[k - 1].kind in ("up", "sp", "lnk", "stem", "suf", "inf")):
            for pre in sorted(PREFIXES, key=len, reverse=True):
                rest = p.text[len(pre):]
                if not p.text.startswith(pre) or len(rest) < 3:
                    continue
                if pre in STRESSED_PREFIXES and rest not in stems:
                    continue
                if rest[0] in VOWELS and rest not in stems:
                    continue
                full_rest = rest + "".join(q.text for q in pieces[k + 1:])
                if rest in stems or _prefix_ok(pre, full_rest):
                    out.append(Piece(PREFIXES[pre][0], pre, pre))
                    ann = _cut_annotated(p.ann, len(pre))
                    out.append(Piece(p.kind if rest not in stems else "stem", rest,
                                     stems.get(rest, ann) if rest in stems and ann == rest else ann))
                    break
            else:
                out.append(p)
            continue
        out.append(p)
    return out


def _cut_annotated(ann: str, n: int) -> str:
    """The annotated string without its first n letters."""
    k = seen = 0
    while seen < n:
        if ann[k] not in ":.'":
            seen += 1
        k += 1
    while k < len(ann) and ann[k] in ":.":
        k += 1
    return ann[k:]


@functools.lru_cache(maxsize=65536)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('Tage' -> t a:1 g @), without the DE: prefix."""
    w = fold(word.replace("'", ""))
    if not w:
        return ()
    ov = override_table().get(w)
    if ov is not None:
        return tuple(ov.split())
    pieces = _pieces(w)
    groups = _group_units(pieces)
    primary_group = next((g for g, (kind, idx) in enumerate(groups)
                          if kind == "root" or pieces[idx[0]].kind == "sp"), None)
    if (len(groups) > 1 and primary_group == 0 and pieces[0].text in ("nord", "süd")
            and pieces[groups[1][1][0]].text.startswith(("ost", "öst", "west"))):
        primary_group = 1
    out: list[str] = []
    for gi, (kind, idx) in enumerate(groups):
        primary = gi == primary_group
        if kind == "pre":
            p = pieces[idx[0]]
            phones = (UNSTRESSED_PREFIXES.get(p.text) or STRESSED_PREFIXES[p.text]).split()
            if phones[0].rstrip("1") in VOWEL_PHONES:
                out.append("?")
            marked = any(x.endswith("1") for x in phones)
            first_v = next((k for k, x in enumerate(phones) if x in VOWEL_PHONES), None)
            for k, x in enumerate(phones):
                if not primary or p.kind == "up":
                    out.append(x.rstrip("1"))
                elif marked:
                    out.append(x)
                else:
                    out.append(x + ("1" if k == first_v else ""))
            continue
        letters: list[tuple[str, str, str, int]] = []
        unit = 0
        root_end = 0
        for n_p, k in enumerate(idx):
            p = pieces[k]
            if n_p > 0:
                prev_text = pieces[idx[n_p - 1]].text
                joined = p.text[0] in VOWELS or prev_text[-1] in VOWELS and p.text[0] not in "s"
                if not joined:
                    unit += 1
            for ch, fl in _annotated(p.ann):
                letters.append((ch, fl, p.kind, unit))
            if n_p == 0:
                root_end = len(letters)
        if pieces[idx[0]].kind == "unk":  # vowel endings of an unknown stem are guesses
            root_end = len(letters)
            pos = 0
            for k in idx:
                if pieces[k].kind == "suf" and pieces[k].text in DERIVATION:
                    root_end = pos
                    break
                pos += len(pieces[k].text)
        text = "".join(ch for ch, *_ in letters)
        gs = _graphemes(letters)
        _mark_special(gs, text)
        rule_text = text
        last = pieces[idx[-1]]
        if len(idx) > 1 and (last.kind == "lnk" or (last.kind == "inf" and last.text == "s")):
            rule_text = text[:-len(last.text)]
        head = _head(gs, rule_text, min(root_end, len(rule_text)))
        _mark_glides(gs, head, text)
        next_text = ""
        if gi + 1 < len(groups):
            next_text = pieces[groups[gi + 1][1][0]].text
        start = "word" if gi == 0 else "#"
        out += _read_group(gs, head, primary, start, next_text)
    return tuple(_merge_doubles(out))


def _merge_doubles(phones: list[str]) -> list[str]:
    """A consonant doubled across a morph boundary is one (Haupt+teil, Bestand+teil)."""
    out: list[str] = []
    for k, p in enumerate(phones):
        if out and p == out[-1] and p not in VOWEL_PHONES and p != "?" and not (
                p == "t" and k + 1 < len(phones) and phones[k + 1] == "s"):
            continue
        out.append(p)
    return out


TI_ENDS = ("on", "ent", "enz", "al", "ell", "ös", "är")  # t + i + these: t s j (Nation, Patient)
IE_HIATUS_ENDS = ("nt", "nz", "nte", "nten", "ntin", "nzen")  # also ie + ll anywhere (speziell)


def _mark_special(gs: list[Grapheme], text: str) -> None:
    """-tion -tient -tial: t -> ts; unstressed -ie(n): i + e (Familie)."""
    for pos in range(len(text)):
        if text[pos] != "t" or not any(text.startswith("i" + e, pos + 1) for e in TI_ENDS):
            continue
        for g in gs:
            if g.kind == "C" and g.text == "t" and g.pos == pos:
                g.ts = True
            if g.kind == "V" and g.text == "i" and g.pos == pos + 1:
                g.glide = True
    pos = 1
    while pos + 1 < len(text):  # speziell, Patient: i + e
        if text[pos:pos + 2] != "ie" or text[pos - 1] in "aeiouäöüd" or not (
                text.startswith("ll", pos + 2) or text[pos + 2:] in IE_HIATUS_ENDS):
            pos += 1
            continue
        for k, g in enumerate(gs):
            if g.kind == "V" and g.text == "ie" and g.pos == pos:
                gs[k] = Grapheme("i", "V", g.unit, g.pos, g.flags, g.piece, glide=True)
                gs.insert(k + 1, Grapheme("e", "V", g.unit, g.pos + 1, g.flags, g.piece))
                break
        pos += 2
    if _ie_unstressed(text):
        end = len(text) - (1 if text.endswith("ien") else 0)
        for k, g in enumerate(gs):
            if g.kind == "V" and g.text == "ie" and g.pos == end - 2:
                gs[k] = Grapheme("i", "V", g.unit, g.pos, g.flags, g.piece, glide=True)
                gs.insert(k + 1, Grapheme("e", "V", g.unit, g.pos + 1, g.flags + "@", g.piece))
                break


def _mark_glides(gs: list[Grapheme], head: int | None, text: str) -> None:
    """An unstressed i before the last vowel of a unit is j (Radio, Gymnasium, Million)."""
    for j, g in enumerate(gs):
        if g.kind != "V" or g.text != "i" or j == head or g.glide or "L" in g.flags:
            continue
        if j + 1 >= len(gs) or gs[j + 1].kind != "V" or gs[j + 1].unit != g.unit:
            continue
        if j == 0 or gs[j - 1].kind != "C":
            continue
        later = [x for x in gs[j + 2:] if x.kind == "V" and x.unit == g.unit]
        if not later or j + 1 == head:
            g.glide = True


def word_tokens_de(word: str) -> list[str]:
    """de-en tokens of one word; a word without a vowel (km, ggf) is spelled letter by letter."""
    w = fold(word.replace("'", ""))
    if w and w not in override_table() and not any(ch in VOWELS for ch in w):
        from .normalize_de import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for n in NAMES[ch].split() for t in word_tokens_de(n)]
    return [f"DE:{p}" for p in phonemes(word)]


# ---------------- spelling check (German or English?) ----------------

def _foreign(w: str) -> bool:
    """English letter groups in a lower-case word in which sch was replaced by S: initial or final sh,
    wh, initial th not before a vowel or r, final th, tch, final dge, ght, igh, initial or final gh,
    final ook/oot, ou, an initial (1-2 consonants) oa + st/ch/rd or final t/d, oy, final aw/ew,
    initial sl sm sn sw tw dw wr, sc not before h, c not after s and not before h/k, q not before u,
    final y, ead/eak/eam, ay, ey, final ing not after l."""
    n = len(w)
    if w.startswith(("sh", "gh", "sl", "sm", "sn", "sw", "tw", "dw", "wr")) or w.endswith(
            ("sh", "th", "dge", "gh", "ook", "oot", "aw", "ew", "y", "ead", "eak", "eam", "ay", "ey")):
        return True
    if any(x in w for x in ("wh", "tch", "ght", "igh", "ou", "oy")):
        return True
    if w.startswith("th") and (n == 2 or w[2] not in "aeiouyr"):
        return True
    if w.startswith("sc") and (n == 2 or w[2] != "h"):
        return True
    for k in (1, 2):
        if n > k + 1 and all(ch not in "aeiou" for ch in w[:k]) and w[k:k + 2] == "oa":
            rest = w[k + 2:]
            if rest.startswith(("st", "ch", "rd")) or rest in ("t", "d"):
                return True
    for k, ch in enumerate(w):
        nxt = w[k + 1] if k + 1 < n else ""
        if ch == "c" and (k == 0 or w[k - 1] != "s") and nxt not in ("h", "k"):
            return True
        if ch == "q" and nxt != "u":
            return True
    return w.endswith("ing") and (n == 3 or w[-4] != "l")


def valid_spelling(w: str) -> bool:
    """True when a lower-case word fits German spelling: not in lexicons/de/english.txt, none of
    the English letter groups of FOREIGN_RE (sh at either end, wh, th at the end, tch, gh, ou, oa,
    oy, aw, ew, a final y, ay, ey, -ing, initial sl sm sn sw tw wr, c outside ch ck sch, q without
    u ...), and consonant clusters that German allows."""
    if not w or not w.isalpha() or w in load_words("de", "english"):
        return False
    w = fold(w)
    return not (_foreign(w.replace("sch", "S")) and w not in load_words("de", "native"))


def unreadable_de(text: str) -> list[str]:
    """Letters the German front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded to a base letter and are readable."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
