"""Khmer text -> words -> syllables -> km-en tokens (spelling rules over orthographic clusters).

Khmer is written without spaces between words, so a run of Khmer letters is read in three
steps, all table-driven (the C port follows the same steps):

1. Words (segment). Over lexicons/km/words.txt (words of the Google Khmer pronunciation lexicon,
   CC BY 4.0, that occur in Khmer Wikipedia, see scripts/frontend/build_km_lexicon.py) and the
   keys of lexicons/km/overrides.tsv: the split with the fewest characters outside listed words,
   then the fewest pieces. Text outside the list is read in one piece. ៗ repeats the word before
   it. Spelling variants are folded first (spell: subscript ដ = subscript ត, ឲ = ឱ, coeng ro last).
2. Clusters and syllables. A word is cut into orthographic clusters: a base (consonant or
   independent vowel), its subscripts (coeng ្ + consonant), a register shifter (៉ ៊, or ុ under
   an upper vowel), the dependent vowels and signs (ំ ះ ៈ ័ ៏), bantoc ់, and the silencing signs
   ៍ ៑ (the cluster is not read). A cluster with a vowel is a syllable. Read left to right, a bare
   cluster (no vowel) closes the open syllable before it (one that does not end in ំ ះ ៈ) unless
   the next cluster needs it as a nucleus: the next consonant carries bantoc or is the last of the
   word, or the next cluster starts with a subscript pair. A bare subscript cluster at the end of
   a word closes the syllable before it (ចិត្ត, សត្វ: the subscript is silent). A subscript pair
   C1្C2 after an open syllable splits (C1 closes that syllable, C2 starts the next) after the
   inherent vowel (សង្គម, កម្ពុជា), and after a written vowel when C2 is C1 or of the same row
   of the consonant table, or one of EXTRA_SPLIT (ពុទ្ធ, ពិភាក្សា); otherwise it is an initial
   cluster (ទីក្រុង).
3. Readings. Onsets: lexicons/km/onsets.tsv for clusters, else the letter sounds (ប is p in a
   cluster or with ៉, ហ្វ ហ្គ ហ្ស are f g z, an aspirated consonant before another loses its
   aspiration). The series (a / o) is that of the base, or of a non-sonorant subscript (ផ្ទះ is
   o-series), set by ៉ ៊ (or flipped by ុ under an upper vowel). The rhyme (vowel and final) comes
   from lexicons/km/rhymes.tsv, keyed by series, vowel signs (with bantoc), the final sound and,
   for an open syllable, whether it ends the word (rhyme). Both tables were made from the lexicon
   (scripts/frontend/build_km_lexicon.py). Words in lexicons/km/overrides.tsv (frequent words the
   rules read differently from the lexicon) are read from their phonemes.

Phonemes are written as in the lexicon (IPA: ʔ ɓ ɗ ɲ ŋ, ɑ ɔ ə ɛ ɨ, long vowels doubled,
diphthongs ie iə ea oa uə ɨə ɛə ae aə ao); KM_TOKEN maps them to the km-en token names.
"""

from __future__ import annotations

import functools
from collections.abc import Collection
from dataclasses import dataclass

from ..lexicons import load_table, load_words
from ..phoneme_set import KM_CONSONANTS, KM_FINALS

# ---------------- letters ----------------

CONSONANTS = "កខគឃងចឆជឈញដឋឌឍណតថទធនបផពភមយរលវឝឞសហឡអ"
ONSET = dict(zip(CONSONANTS, (
    "k", "kh", "k", "kh", "ŋ", "c", "ch", "c", "ch", "ɲ", "ɗ", "th", "ɗ", "th", "n", "t", "th", "t",
    "th", "n", "ɓ", "ph", "p", "ph", "m", "j", "r", "l", "w", "s", "s", "s", "h", "l", "ʔ"), strict=True))
SERIES_O = frozenset("គឃងជឈញឌឍទធនពភមយរលវ")  # o-series (second register); the others a-series
# Final sounds; រ is silent ("r" in the rhyme keys: the table gives the vowel before it).
FINAL = {
    **dict.fromkeys("កខគឃ", "k"), "ង": "ŋ", **dict.fromkeys("ចឆជឈ", "c"), "ញ": "ɲ",
    **dict.fromkeys("ដឋឌឍតថទធ", "t"), **dict.fromkeys("ណន", "n"), **dict.fromkeys("បផពភ", "p"),
    "ម": "m", "យ": "j", "រ": "r", **dict.fromkeys("លឡ", "l"), "វ": "w",
    **dict.fromkeys("ឝឞសហ", "h"), "អ": "ʔ", "\u17cc": "R",
}
SONORANTS = frozenset("ងញណនមយរលវ")  # a sonorant subscript keeps the series of the base
LOSE_ASP = {"kh": "k", "ch": "c", "th": "t", "ph": "p"}
LOAN_ONSETS = {"ហវ": "f", "ហគ": "g", "ហក": "g", "ហស": "z"}
# Rows of the consonant table (same place of articulation): a subscript of the same row as the
# consonant above it starts a new syllable after a written vowel (ពុទ្ធ, បណ្ឌិត).
VARGA = ("កខគឃង", "ចឆជឈញ", "ដឋឌឍណ", "តថទធន", "បផពភម")
ROW = {c: k for k, row in enumerate(VARGA) for c in row}
EXTRA_SPLIT = frozenset(("កស", "ងហ", "ងស", "ហម", "ហល", "លល", "យយ", "សស"))
# Independent vowels: their sounds; a final consonant after them is read with them.
INDEPENDENT = {
    "ឣ": "ʔ ɑɑ", "ឤ": "ʔ aa", "ឥ": "ʔ e", "ឦ": "ʔ ə j", "ឧ": "ʔ o", "ឨ": "ʔ o w",
    "ឩ": "ʔ uu", "ឪ": "ʔ ə w", "ឫ": "r ɨ", "ឬ": "r ɨɨ", "ឭ": "l ɨ", "ឮ": "l ɨɨ", "ឯ": "ʔ ae",
    "ឰ": "ʔ a j", "ឱ": "ʔ ao", "ឳ": "ʔ a w",
}
COENG = "\u17d2"
MUUSIKATOAN, TRIISAP = "\u17c9", "\u17ca"  # ៉ (to the a-series) ៊ (to the o-series)
BANTOC = "\u17cb"  # ់
SILENCERS = "\u17cd\u17d1"  # ៍ toandakhiat, ៑ viriam: the consonant is not read
ROBAT = "\u17cc"  # ៌ (silent)
DEP_VOWELS = "ាិីឹឺុូួើឿៀេែៃោៅ"
SIGNS = "ំះៈ័៏"  # nikahit, reahmuk, yuukaleapintu, samyok sannya, ahsda (vowel key, this order)
UPPER = "ិីឹឺើ"  # ុ written with one of these is a register shifter, not the vowel u
IGNORED = "\u17b4\u17b5\u17ce\u17d3\u17dd\u200b\u200c\u200d\u2060"  # inherent-vowel signs, ៎, ZW*
NO_FINAL = "ំះៈ"  # a syllable ending in these takes no final consonant
REPEAT = "ៗ"


def spell(word: str) -> str:
    """Canonical spelling: subscript ដ as subscript ត (written alike, used interchangeably), ឲ as
    ឱ, coeng ro after the other subscripts (ស្រ្តី -> ស្ត្រី), ignored signs dropped."""
    w = "".join(ch for ch in word if ch not in IGNORED)
    w = w.replace(COENG + "ដ", COENG + "ត").replace("ឲ", "ឱ")
    ro = COENG + "រ"
    k = w.find(ro + COENG)
    while k >= 0:
        if k + 3 < len(w) and w[k + 3] in ONSET:
            w = w[:k] + w[k + 2:k + 4] + ro + w[k + 4:]
        k = w.find(ro + COENG, k + 2)
    return w


@dataclass
class Cluster:
    base: str
    subs: str = ""      # subscript consonants
    shift: int = 0      # 1: ៉ (a-series), 2: ៊ (o-series), 3: ុ under an upper vowel (flip)
    vowel: str = ""     # dependent vowels, then the signs of SIGNS
    bantoc: bool = False
    silent: bool = False
    robat: bool = False

    @property
    def bare(self) -> bool:
        return not self.vowel and self.base in ONSET


def clusters(word: str) -> list[Cluster]:
    """Orthographic clusters of a Khmer word (characters that start none are skipped)."""
    out: list[Cluster] = []
    i, n = 0, len(word)
    while i < n:
        ch = word[i]
        i += 1
        if ch not in ONSET and ch not in INDEPENDENT:
            continue
        c = Cluster(ch)
        vowels, signs, shift = "", "", ""
        while i < n:
            x = word[i]
            if x == COENG:
                if i + 1 < n and word[i + 1] in ONSET:
                    c.subs += word[i + 1]
                    i += 1
            elif x in DEP_VOWELS:
                vowels += x
            elif x in SIGNS:
                signs += x
            elif x in (MUUSIKATOAN, TRIISAP):
                shift = shift or x
            elif x == BANTOC:
                c.bantoc = True
            elif x in SILENCERS:
                c.silent = True
            elif x == ROBAT:
                c.robat = True
            elif x not in IGNORED:
                break
            i += 1
        if "ុ" in vowels and any(v in UPPER for v in vowels):
            vowels = vowels.replace("ុ", "", 1)
            shift = shift or "ុ"
        c.vowel = vowels + "".join(s for s in SIGNS if s in signs)
        c.shift = {"": 0, MUUSIKATOAN: 1, TRIISAP: 2}.get(shift, 3)
        out.append(c)
    return out


@dataclass
class Syllable:
    onset: str           # letters of the onset (base and subscripts); "" for an independent vowel
    shift: int
    vowel: str           # vowel key (Cluster.vowel)
    final: str = ""      # final letter
    bantoc: bool = False
    indep: str = ""      # independent vowel letter
    last: bool = False   # last syllable of the word
    sub: bool = False    # the onset is a subscript (the consonant above closed the syllable before)

    def series(self) -> int:
        """1 (a-series) or 2 (o-series): the base, or a non-sonorant subscript; ៉ ៊ ុ set it."""
        if not self.onset:
            return 1
        base = self.onset[0]
        if self.shift == 3:
            return 1 if base in SERIES_O else 2
        if self.shift:
            return self.shift
        c = self.onset[1] if len(self.onset) > 1 and self.onset[1] not in SONORANTS else base
        return 2 if c in SERIES_O else 1

    def key(self) -> str:
        """Rhyme table key: series + vowel signs (+ ់) | final sound (- none, R robat) | e (last
        syllable of the word), c (open, not last, onset cluster) or m (other)."""
        fin = FINAL.get(self.final, self.final) if self.final else "-"
        if self.last:
            pos = "e"
        elif not self.final and len(self.onset) > 1:
            pos = "c"
        else:
            pos = "m"
        return f"{self.series()}{self.vowel}{BANTOC if self.bantoc else ''}|{fin}|{pos}"


def _pair_splits(c: Cluster) -> bool:
    """A subscript pair read across a syllable boundary after a written vowel: a geminate, the same
    row of the consonant table, or one of EXTRA_SPLIT."""
    a, b = c.base, c.subs[0]
    return a == b or (a in ROW and ROW.get(b) == ROW[a]) or a + b in EXTRA_SPLIT


def _takes_final(s: Syllable, c: Cluster) -> bool:
    """Whether the syllable s can be closed by the consonant of c."""
    if s.final:
        return False
    if s.vowel.endswith("ំ") and c.base == "ង" and not c.subs:
        return True  # ាំង, ុំង: the nasal is ŋ
    return not any(x in s.vowel for x in NO_FINAL)


def _closes(prev: Syllable, cs: list[Cluster], i: int) -> bool:
    """Whether the bare cluster cs[i] closes the open syllable prev (else it is a nucleus)."""
    c = cs[i]
    nx = cs[i + 1] if i + 1 < len(cs) else None
    if c.robat or c.bantoc or nx is None:
        return True  # ធម៌; a bare cluster at the end (ចិត្ត, សត្វ: the subscript is silent)
    if c.subs:
        return False
    if len(prev.onset) > 1 and not prev.vowel:
        return False  # a minor syllable with a cluster onset stays open: ប្រកប
    if nx.bare and not nx.subs and (nx.bantoc or i + 2 == len(cs)):
        return False  # the next consonant closes this one: របស់, នគរ
    return not (nx.subs and _pair_splits(nx))  # the pair after it closes this one: សមត្ថ


def syllables(word: str) -> list[Syllable]:
    """Syllables of one Khmer word (canonical spelling) by the cluster rules (module docstring)."""
    cs = [c for c in clusters(word) if not (c.silent and not c.vowel)]
    out: list[Syllable] = []
    for i, c in enumerate(cs):
        prev = out[-1] if out else None
        if prev is not None and _takes_final(prev, c):
            if c.bare and _closes(prev, cs, i):
                prev.final, prev.bantoc = (ROBAT if c.robat else c.base), c.bantoc
                continue
            if (i + 1 == len(cs) and c.vowel in ("ិ", "ុ") and not c.subs and c.base in ONSET
                    and (prev.vowel or prev.indep)):
                prev.final = c.base  # a final ិ ុ after a written vowel is silent: ជាតិ, ហេតុ
                continue
        if c.base in INDEPENDENT:
            out.append(Syllable("", 0, c.vowel, indep=c.base, final=c.subs[:1]))
            continue
        onset, sub = c.base + c.subs, False
        if (c.subs and prev is not None and _takes_final(prev, c)
                and ((not prev.vowel and not prev.indep) or _pair_splits(c))):
            prev.final = c.base  # សង្គម, កម្ពុជា after the inherent vowel; ពុទ្ធ, ពិភាក្សា
            onset, sub = c.subs, True
        out.append(Syllable(onset, c.shift, c.vowel, sub=sub))
    if out:
        out[-1].last = True
    return out


@functools.cache
def rhyme_table() -> dict[str, str]:
    return load_table("km", "rhymes")


@functools.cache
def onset_table() -> dict[str, str]:
    return load_table("km", "onsets")


def onset_phones(s: Syllable) -> list[str]:
    """Sounds of the onset letters: lexicons/km/onsets.tsv for clusters, else ប is p with ៉ or in
    a cluster, ហ្វ ហ្គ ហ្ស are the loan sounds f g z and an aspirated consonant before another
    loses its aspiration."""
    o = s.onset
    if not o:
        return []
    if len(o) > 1 and o in onset_table():
        return onset_table()[o].split()
    if o[:2] in LOAN_ONSETS:
        return [LOAN_ONSETS[o[:2]]] + [ONSET[ch] for ch in o[2:]]
    ph = []
    for k, ch in enumerate(o):
        p = ONSET[ch]
        if ch == "ប" and (s.shift == 1 or len(o) > 1 or s.sub):
            p = "p"
        if k + 1 < len(o):
            p = LOSE_ASP.get(p, p)
        ph.append(p)
    return ph


def rhyme(s: Syllable) -> list[str]:
    """Vowel and final of a syllable from the rhyme table; backed off to the other positions of
    an open syllable, then to the inherent vowel and the final sound."""
    table = rhyme_table()
    key = s.key()
    if key in table:
        return table[key].split()
    head = key.rsplit("|", 1)[0] + "|"
    for k in (head + "m", head + "e", head + "c"):
        if k in table:
            return table[k].split()
    fin = FINAL[s.final] if s.final else ""
    return ["ɑɑ" if s.series() == 1 else "ɔɔ"] + ([fin] if fin and fin not in "rR" else [])


def syllable_phones(s: Syllable) -> list[str]:
    if s.indep:
        base = INDEPENDENT[s.indep].split()
        fin = FINAL[s.final] if s.final else ""
        return base + ([fin] if fin and fin not in "rR" else [])
    return onset_phones(s) + rhyme(s)


def rule_phones(word: str) -> list[list[str]]:
    """Phonemes per syllable of one word (canonical spelling) by the rules alone."""
    return [syllable_phones(s) for s in syllables(word)]


# ---------------- word segmentation ----------------

def _cluster_ends(run: str) -> list[int]:
    """ends[i] = end of the orthographic cluster starting at run[i] (i + 1 for a character that
    starts none); words start only at cluster starts."""
    n = len(run)
    ends = list(range(1, n + 1))
    i = 0
    while i < n:
        j = i + 1
        if run[i] in ONSET or run[i] in INDEPENDENT:
            while j < n:
                x = run[j]
                if x == COENG and j + 1 < n and run[j + 1] in ONSET:
                    j += 2
                elif x in ONSET or x in INDEPENDENT:
                    break
                elif "឴" <= x <= "៓" or x == "៝":
                    j += 1
                else:
                    break
        ends[i] = j
        i = j
    return ends


def segment(run: str, words: Collection[str] | None = None, maxw: int | None = None) -> list[str]:
    """Words of a run of Khmer letters (canonical spelling): fewest characters outside the word
    list, then fewest pieces; consecutive pieces outside the list are returned as one piece."""
    if words is None:
        words, maxw = word_set(), _max_word()
    elif maxw is None:
        maxw = max(map(len, words), default=1)
    n = len(run)
    ends = _cluster_ends(run)
    starts = [False] * (n + 1)
    i = 0
    while i < n:
        starts[i] = True
        i = ends[i]
    starts[n] = True
    best: list[tuple[int, int, int, bool] | None] = [None] * (n + 1)
    best[0] = (0, 0, 0, False)
    for i in range(n):
        if best[i] is None or not starts[i]:
            continue
        unk, cnt = best[i][:2]
        cands = [(j, 0) for j in range(min(n, i + maxw), i, -1) if starts[j] and run[i:j] in words]
        cands.append((ends[i], ends[i] - i))
        for j, u in cands:
            key = (unk + u, cnt + 1, i, u > 0)
            if best[j] is None or key[:2] < best[j][:2]:
                best[j] = key
    cuts: list[tuple[int, int, bool]] = []
    j = n
    while j > 0:
        i, unknown = best[j][2], best[j][3]
        if cuts and unknown and cuts[-1][2]:
            cuts[-1] = (i, cuts[-1][1], True)
        else:
            cuts.append((i, j, unknown))
        j = i
    return [run[i:j] for i, j, _ in reversed(cuts)]


@functools.cache
def override_table() -> dict[str, tuple[tuple[str, ...], ...]]:
    """word -> phonemes per syllable ("k m ae . r" style, syllables separated by " . ")."""
    return {k: tuple(tuple(s.split()) for s in v.split(" . "))
            for k, v in load_table("km", "overrides").items()}


@functools.cache
def word_set() -> frozenset[str]:
    return load_words("km", "words") | frozenset(override_table())


@functools.cache
def _max_word() -> int:
    return max((len(w) for w in word_set()), default=1)


def word_phones(word: str) -> list[list[str]]:
    """Phonemes per syllable of one word (canonical spelling): its override, else the rules."""
    o = override_table().get(word)
    if o is not None:
        return [list(s) for s in o]
    return rule_phones(word)


def run_phones(run: str) -> list[list[str]]:
    """Phonemes per syllable of a run of Khmer letters (ៗ repeats the word before it)."""
    out: list[list[str]] = []
    last: list[list[str]] = []
    for k, piece in enumerate(spell(run).split(REPEAT)):
        if k > 0:
            out.extend(last)
        for word in segment(piece) if piece else []:
            last = word_phones(word)
            out.extend(last)
    return out


# ---------------- tokens ----------------

ONSET_TOKEN = {"ʔ": "?", "ɓ": "b", "ɗ": "d", "ɲ": "ny", "ŋ": "ng"}
VOWEL_TOKEN = {"ɨ": "y", "ɨɨ": "yy", "ə": "@", "əə": "@@", "ɛ": "E", "ɛɛ": "EE", "ɑ": "A", "ɑɑ": "AA",
               "ɔ": "O", "ɔɔ": "OO", "aə": "a@", "iə": "i@", "uə": "u@", "ɨə": "y@", "ɛə": "E@"}
# Finals: the 13 native final sounds and f s of loanwords; rare loan finals take the nearest.
FINAL_TOKEN = {"ʔ": "?", "ɲ": "ny", "ŋ": "ng", "z": "s", "g": "k", "ch": "c", "ɓ": "p", "ɗ": "t",
               "kh": "k", "th": "t", "ph": "p"}
VOWEL_PHONES = frozenset(("i", "ii", "ɨ", "ɨɨ", "u", "uu", "e", "ee", "ə", "əə", "o", "oo", "ɛ",
                           "ɛɛ", "a", "aa", "ɑ", "ɑɑ", "ɔ", "ɔɔ", "ae", "aə", "ao", "ie", "iə",
                           "ea", "oa", "uə", "ɨə", "ɛə"))


def syllable_tokens(phones: list[str]) -> list[str]:
    """km-en tokens of one syllable: KM:<consonant>... KM:<vowel> [KM:F:<final>]."""
    out: list[str] = []
    seen_vowel = False
    for p in phones:
        if p in VOWEL_PHONES:
            out.append("KM:" + VOWEL_TOKEN.get(p, p))
            seen_vowel = True
        elif seen_vowel:  # a final outside the inventory (r of a loanword) is not read
            name = FINAL_TOKEN.get(p, p)
            if name in KM_FINALS:
                out.append("KM:F:" + name)
        else:
            name = ONSET_TOKEN.get(p, p)
            if name in KM_CONSONANTS:
                out.append("KM:" + name)
    return out


def khmer_syllable_tokens(run: str) -> list[list[str]]:
    """Tokens per syllable of a run of Khmer letters."""
    return [syllable_tokens(p) for p in run_phones(run)]


def is_khmer(ch: str) -> bool:
    """Khmer letters and signs (U+1780..U+17D3, ៗ, ៝; not the digits, ។ ៕ ៖ or ៛)."""
    return "ក" <= ch <= "៓" or ch in "ៗ៝"


def unreadable_km(text: str) -> list[str]:
    """Letters the Khmer front-end cannot read (other scripts than Khmer and Latin), to filter
    training sentences."""
    import unicodedata

    out = []
    for ch in text:
        if not ch.isalpha() or is_khmer(ch) or ch.isascii():
            continue
        base = unicodedata.normalize("NFKD", ch)[:1]
        if not (base.isascii() and base.isalpha()):
            out.append(ch)
    return out
