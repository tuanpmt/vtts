"""Arabic word (Modern Standard Arabic) -> ar-en tokens.

Arabic is written without short vowels, so a word is read in two steps:

1. Vowels (vocalize). A word that already carries vowel marks (fatha, damma, kasra, sukun,
   tanwin, dagger alif) is read as written. Otherwise its vowels are restored:
   a. lexicons/ar/words.tsv (hand-written, the most frequent words with their vowels) for the
      whole word, else for its stem after proclitics (و ف, ب ك ل, the article ال, لل) and
      suffixes (pronouns ه ها هم هما هن ك كم كن نا ني ي; endings ة ات ون ين ان ية ي يين يون
      يات تان تين), the ending rebuilt with its own vowels (حكومات from حكومة, الدولية from
      دولة -> دولي + ية);
   b. else word patterns (PATTERNS: mafʕuul, faaʕil, istifʕaal, ...) on the stem without the
      article and endings;
   c. else the default reading: every consonant gets a, a consonant before ا و ي gets the
      matching long vowel.
2. Sounds (read_vocalized). Letters with their marks give phonemes; every word is read in its
   pausal form (no case endings, no tanwin; final -an written with alif is aa; ة is a). The
   article: hamzat al-wasl ا is "a" at the start of a word and silent after a proclitic
   (وال, بال); the ل is assimilated to a following sun letter (الشمس -> a sh sh a m s). Shadda
   doubles its consonant. Hamza forms أ إ ؤ ئ ء and آ are the glottal stop ? (آ = ? aa; an
   unmarked أ has a, إ has i). ا after a, و after u, ي after i are long vowels; و ي after a are
   diphthongs (a w, a y). ى is aa. The dagger alif ٰ is aa.
3. Stress (stress): the last syllable when it is superheavy (CVVC, CVCC), else the penultimate
   when heavy (CVV, CVC), else the antepenultimate, but never a word-initial syllable without
   an onset (the article al-, hamzat al-wasl: الولد a l w a1 l a d); one-syllable words are
   unstressed.

Inventory (42 tokens, AR: prefix; phoneme_set.TOKENS_AREN): 28 consonants ? b t th j H x d dh r
z s sh S D T Z 3 gh f q k l m n h w y (H = ħ ح, x = خ, 3 = ʕ ع, S D T Z = the emphatics
ص ض ط ظ), loanword g v (گ ڨ, ڤ), vowels a i u aa ii uu and the stressed vowels a1 i1 u1 aa1
ii1 uu1. A geminate is the consonant twice.
"""

from __future__ import annotations

import functools
import re
import unicodedata

from ..lexicons import load_table

FATHA, DAMMA, KASRA, SUKUN, SHADDA = "َ", "ُ", "ِ", "ْ", "ّ"
FATHATAN, DAMMATAN, KASRATAN, DAGGER_ALIF = "ً", "ٌ", "ٍ", "ٰ"
TATWEEL = "ـ"
VOWEL_MARKS = frozenset((FATHA, DAMMA, KASRA, SUKUN, FATHATAN, DAMMATAN, KASRATAN, DAGGER_ALIF))
MARKS = VOWEL_MARKS | {SHADDA}

CONSONANT_LETTERS = {
    "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "H", "خ": "x", "د": "d", "ذ": "dh", "ر": "r",
    "ز": "z", "س": "s", "ش": "sh", "ص": "S", "ض": "D", "ط": "T", "ظ": "Z", "ع": "3", "غ": "gh",
    "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n", "ه": "h", "و": "w", "ي": "y",
    "ء": "?", "أ": "?", "إ": "?", "ؤ": "?", "ئ": "?",
    "گ": "g", "ڨ": "g", "ڤ": "v", "پ": "b", "چ": "j",
}
# Letter variants folded before reading (Persian/Urdu forms, wasla, final forms of Kurdish etc).
FOLD = {"ی": "ي", "ې": "ي", "ى": "ى", "ک": "ك", "ٱ": "ا", "ھ": "ه", "ە": "ه", "ۀ": "ة",
        "ٹ": "ت", "ڈ": "د", "ں": "ن"}
LETTERS = frozenset(CONSONANT_LETTERS) | frozenset("اآىة")
SUN = frozenset("تثدذرزسشصضطظلن")
HAMZA_DEFAULT = {"أ": "a", "إ": "i"}
SHORT = ("a", "i", "u")
LONG = ("aa", "ii", "uu")
VOWELS = SHORT + LONG
CONSONANTS = ("?", "b", "t", "th", "j", "H", "x", "d", "dh", "r", "z", "s", "sh", "S", "D", "T",
              "Z", "3", "gh", "f", "q", "k", "l", "m", "n", "h", "w", "y", "g", "v")
STRESSED = tuple(f"{v}1" for v in VOWELS)
PHONEMES = CONSONANTS + VOWELS + STRESSED
PROCLITIC_LETTERS = frozenset("وفبكل")


def is_arabic(ch: str) -> bool:
    return ("؀" <= ch <= "ۿ" or "ݐ" <= ch <= "ݿ" or "ࢠ" <= ch <= "ࣿ"
            or "ﭐ" <= ch <= "﷿" or "ﹰ" <= ch <= "﻿")


def is_arabic_letter(ch: str) -> bool:
    return is_arabic(ch) and unicodedata.category(ch) == "Lo"


def is_arabic_word(word: str) -> bool:
    return any(is_arabic_letter(ch) for ch in word)


def strip_marks(word: str) -> str:
    """The bare letters of a word: no vowel marks, shadda, tatweel or Quranic signs; NFC."""
    w = unicodedata.normalize("NFC", word)
    return "".join(FOLD.get(c, c) for c in w
                   if c not in MARKS and c != TATWEEL and not "ۖ" <= c <= "ۭ"
                   and not "ؐ" <= c <= "ؚ" and c not in "ٕٓٔ")


def has_vowel_marks(word: str) -> bool:
    return any(c in VOWEL_MARKS for c in word)


def _letters(word: str) -> list[tuple[str, frozenset[str]]]:
    """(letter, its marks) of a word; NFC composes ا + hamza / madda into أ إ آ."""
    out: list[tuple[str, set[str]]] = []
    for c in unicodedata.normalize("NFC", word):
        c = FOLD.get(c, c)
        if c in LETTERS:
            out.append((c, set()))
        elif c in MARKS and out:
            out[-1][1].add(c)
    return [(b, frozenset(m)) for b, m in out]


def _vowel(marks: frozenset[str]) -> str | None:
    for mark, v in ((DAGGER_ALIF, "aa"), (FATHA, "a"), (DAMMA, "u"), (KASRA, "i"),
                    (FATHATAN, "an"), (DAMMATAN, "un"), (KASRATAN, "in"), (SUKUN, "0")):
        if mark in marks:
            return v
    return None


def _article(letters: list[tuple[str, frozenset[str]]]) -> tuple[int | None, int | None]:
    """(index of the article's alif or None, index of its lam) when the word has the article:
    unmarked ا + unmarked ل (or ل with sukun) at the start or after vowelled proclitics, or the
    ل of لل (li + al). (None, None) otherwise."""
    n = len(letters)
    k = 0
    while (k < 2 and k < n and letters[k][0] in PROCLITIC_LETTERS
           and _vowel(letters[k][1]) in ("a", "i")):
        if (letters[k][0] == "ل" and k + 2 < n and letters[k + 1][0] == "ل"
                and _vowel(letters[k + 1][1]) in (None, "0")):
            return None, k + 1
        k += 1
    if (k + 2 < n and letters[k][0] == "ا" and _vowel(letters[k][1]) is None
            and letters[k + 1][0] == "ل"
            and (_vowel(letters[k + 1][1]) in (None, "0")
                 or (_vowel(letters[k + 1][1]) == "i" and letters[k + 2][0] == "ا"))):
        return k, k + 1
    return None, None


def read_vocalized(word: str, pausal: bool = True) -> list[str]:
    """Phonemes (no stress) of a word with vowel marks, read in pausal form."""
    letters = _letters(word)
    n = len(letters)
    alif, lam = _article(letters)
    out: list[str] = []
    geminate = False
    last_mark_vowel = False
    for i, (b, m) in enumerate(letters):
        v = _vowel(m)
        prev_sukun = i > 0 and SUKUN in letters[i - 1][1]
        last_mark_vowel = False
        prev = out[-1] if out else None
        if i == alif:
            if i == 0:
                out.append("a")
            continue
        if i == lam:
            if v == "i":  # liaison vowel before a hamzat al-wasl (الِاتحاد)
                out += ["l", "i"]
            elif i + 1 < n and letters[i + 1][0] in SUN:
                geminate = SHADDA not in letters[i + 1][1]
            else:
                out.append("l")
            continue
        if b == "ا":
            if i == 0:
                out.append(v if v in SHORT else "a" if n > 1 and letters[1][0] == "ل" else "i")
            elif v in SHORT and prev is not None and prev not in VOWELS:
                out.append(v)  # hamzat al-wasl after the article: الاِتحاد
            elif prev == "a":
                out[-1] = "aa"
            elif prev is not None and prev not in VOWELS:
                out.append("aa")
            continue
        if b == "آ":
            out += ["?", "aa"]
            continue
        if b == "ى":
            if prev == "a":
                out[-1] = "aa"
            elif prev == "i":
                out[-1] = "ii"
            elif prev is not None and prev not in VOWELS:
                out.append("aa")
            continue
        if b == "ة":
            if prev is not None and prev not in VOWELS:
                out.append("a")
            if i + 1 < n:
                out.append("t")
            continue
        if b in "وي" and i > 0 and SHADDA not in m and v in (None, "0"):
            short, long_ = ("u", "uu") if b == "و" else ("i", "ii")
            if prev == short:
                out[-1] = long_
                continue
            if prev == "a" or v == "0" or prev_sukun:
                out.append(CONSONANT_LETTERS[b])
                continue
            if prev in LONG:  # a long vowel then و/ي: consonant
                out.append(CONSONANT_LETTERS[b])
                continue
            if prev is not None:
                out.append(long_)
                continue
        c = CONSONANT_LETTERS[b]
        if v is None and b in HAMZA_DEFAULT and not (i + 1 < n and letters[i + 1][0] == "ا"):
            v = HAMZA_DEFAULT[b]
        out += [c, c] if (SHADDA in m or geminate) else [c]
        geminate = False
        if v in SHORT or v == "aa":
            out.append(v)
            last_mark_vowel = v in SHORT
        elif v in ("an", "un", "in"):
            out.append(v[0])
            last_mark_vowel = True
    if pausal and last_mark_vowel and out and out[-1] in SHORT:
        bare = sum(1 for b, _ in letters)
        tanwin = any(t in letters[-1][1] for t in (FATHATAN, DAMMATAN, KASRATAN))
        if bare >= 3 or tanwin:
            out.pop()
    if pausal and out[-3:] == ["i", "y", "y"]:  # nisba -iyy in pause: -ii
        out[-3:] = ["ii"]
    return out


def _syllables(ph: list[str]) -> list[tuple[int, str]]:
    """(index of the nucleus, weight "L" | "H" | "S") per syllable."""
    nuclei = [k for k, p in enumerate(ph) if p in VOWELS]
    out = []
    for j, k in enumerate(nuclei):
        end = nuclei[j + 1] if j + 1 < len(nuclei) else len(ph) + 1
        coda = max(0, end - k - 2) if j + 1 < len(nuclei) else len(ph) - k - 1
        long_ = ph[k] in LONG
        weight = "S" if (long_ and coda >= 1) or coda >= 2 else "H" if long_ or coda == 1 else "L"
        out.append((k, weight))
    return out


def stress(ph: list[str]) -> list[str]:
    """Mark the stressed vowel (a -> a1) by the MSA rule (see the module docstring)."""
    syl = _syllables(ph)
    if len(syl) < 2:
        return list(ph)
    if syl[-1][1] == "S":
        j = len(syl) - 1
    elif syl[-2][1] != "L" or len(syl) == 2:
        j = len(syl) - 2
    else:
        j = len(syl) - 3
    if j == 0 and syl[0][0] == 0:  # no stress on a word-initial onsetless syllable (the article)
        j = 1
    k = syl[j][0]
    out = list(ph)
    out[k] += "1"
    return out


# ---------------- vowel restoration ----------------

PROCLITICS = {"و": "وَ", "ف": "فَ", "ب": "بِ", "ك": "كَ", "ل": "لِ"}
# Pronoun suffixes (longest first) with their vowels; LINK is the case vowel before them.
PRONOUNS = (("هما", "هُمَا"), ("كما", "كُمَا"), ("هم", "هُمْ"), ("هن", "هُنَّ"), ("كم", "كُمْ"),
            ("كن", "كُنَّ"), ("ها", "هَا"), ("نا", "نَا"), ("ني", "نِي"), ("ه", "هُ"), ("ك", "كَ"))
LINK = KASRA
# Endings added to a stem of the lexicon: (ending, stem ending it attaches to, vowelled ending).
# "" = the stem as listed; "ة" = a feminine stem whose ة is replaced.
ENDINGS = (
    ("يين", "", "ِيِّين"), ("يون", "", "ِيُّون"), ("يات", "", "ِيَّات"), ("ية", "", "ِيَّة"),
    ("ية", "ة", "ِيَّة"), ("يين", "ة", "ِيِّين"), ("يات", "ة", "ِيَّات"), ("ي", "ة", "ِيّ"),
    ("تين", "ة", "َتَيْن"), ("تان", "ة", "َتَان"), ("ات", "ة", "َات"), ("ات", "", "َات"),
    ("ون", "", "ُون"), ("ين", "", "ِين"), ("ان", "", "َان"), ("ي", "", "ِيّ"), ("ة", "", "َة"),
)


@functools.cache
def lexicon() -> dict[str, str]:
    """Bare word -> vowelled word (lexicons/ar/words.tsv)."""
    return load_table("ar", "words")


@functools.cache
def _unseated() -> dict[str, str]:
    """The lexicon under keys whose first letter أ إ آ is written ا (text often omits the
    hamza of the first letter: احمد, اكثر)."""
    out: dict[str, str] = {}
    for k, v in lexicon().items():
        if k[0] in "أإآ":
            out.setdefault("ا" + k[1:], v)
    return out


def _lookup(stem: str) -> str | None:
    return lexicon().get(stem) or _unseated().get(stem)


def _strip_final_vowel(voc: str) -> str:
    """A lexicon value without a final short vowel mark (to attach an ending)."""
    while voc and voc[-1] in (FATHA, DAMMA, KASRA, SUKUN, FATHATAN, DAMMATAN, KASRATAN):
        voc = voc[:-1]
    return voc


def _with_ending(stem: str) -> str | None:
    """A stem of the lexicon, directly or with one of ENDINGS."""
    found = _lookup(stem)
    if found:
        return found
    for ending, base_end, voc in ENDINGS:
        if stem.endswith(ending) and len(stem) - len(ending) >= 3 - len(base_end):
            base = stem[: len(stem) - len(ending)] + base_end
            found = _lookup(base)
            if found:
                core = _strip_final_vowel(found)
                if base_end == "ة":
                    core = _strip_final_vowel(core.rstrip("ة")) if core.endswith("ة") else None
                    if core is None:
                        continue
                return core + voc
    return None


def _proclitic_splits(word: str) -> list[tuple[str, str, bool]]:
    """(vowelled proclitics, rest, has article) candidates, most proclitics first."""
    out: list[tuple[str, str, bool]] = []
    for conj in ("و", "ف", ""):
        if not word.startswith(conj):
            continue
        w = word[len(conj):]
        pre = PROCLITICS.get(conj, "")
        if w.startswith("لل") and len(w) > 3:
            out.append((pre + "لِل", w[2:], True))
        for prep in ("ب", "ك", "ل", ""):
            if not w.startswith(prep):
                continue
            rest = w[len(prep):]
            p = pre + PROCLITICS.get(prep, "")
            if rest.startswith("ال") and len(rest) > 3:
                out.append((p + "ال", rest[2:], True))
            if conj or prep:
                out.append((p, rest, False))
    out.append(("", word, False))
    return out


def _pronoun_splits(rest: str) -> list[tuple[str, str]]:
    out = []
    for suf, voc in PRONOUNS:
        if rest.endswith(suf) and len(rest) - len(suf) >= 2:
            stem = rest[: -len(suf)]
            if stem.endswith("ت"):  # a feminine noun first (حياته = حياة + ه)
                out.append((stem[:-1] + "ة", voc))
            out.append((stem, voc))
    return out


_HI = {"هُ": "هِ", "هُمْ": "هِمْ", "هُمَا": "هِمَا", "هُنَّ": "هِنَّ"}


def _attach(stem_voc: str, pron: str) -> str:
    """A vowelled stem + a pronoun suffix: a stem ending in sukun or fatha (مِنْ, إِنَّ, verbs)
    keeps it, a noun takes the genitive i (the most frequent case before a pronoun); ه هم هما
    هن become hi him himaa hinna after i, ii or y."""
    if stem_voc.endswith((SUKUN, FATHA)):
        core = stem_voc
    else:
        core = _strip_final_vowel(stem_voc)
        if core.endswith("ة"):
            core = core[:-1] + "ت"
        if not core.endswith(("ا", "ى", "ي", "و")):
            core += LINK
        elif core.endswith("ى"):
            core = core[:-1] + "ا"
    if core.endswith((KASRA, "ي", "ي" + SUKUN)):
        pron = _HI.get(pron, pron)
    return core + pron


def lexicon_vocalize(word: str) -> str | None:
    """Vowelled form from the lexicon: the whole word, else the split (proclitics, stem,
    ending or pronoun) with the longest stem found, fewer proclitics first."""
    found = _lookup(word)
    if found:
        return found
    best: tuple[int, int, str] | None = None
    for pre, rest, art in _proclitic_splits(word):
        if len(rest) < 2:
            continue
        cands = [(len(rest), _with_ending(rest), "")]
        if not art:
            cands += [(len(stem), _with_ending(stem), pron) for stem, pron in _pronoun_splits(rest)]
        for size, voc, pron in cands:
            if voc and (best is None or (size, -len(pre)) > best[:2]):
                best = (size, -len(pre), pre + (_attach(voc, pron) if pron else voc))
    return best[2] if best else None


# Word patterns for stems not in the lexicon: (regex over the bare stem, vowelled template).
# In the template the digits 1..5 are the stem's consonants matched by the groups.
C = "([^اويىةآ])"
CW = "([^اىةآ])"  # a consonant slot that may be و or ي
CCC_TEMPLATE = "1َ2ْ3"  # CaCC (nouns) reads better than CaCaC (verbs)
PATTERNS: tuple[tuple[str, str], ...] = (
    ("است" + C + C + "ا" + C, "اِسْتِ1ْ2َا3"),
    ("مست" + C + C + C, "مُسْتَ1ْ2ِ3"),
    ("مت" + CW + C + C, "مُتَ1َ2ِّ3"),
    ("ان" + C + C + "ا" + C, "اِنْ1ِ2َا3"),
    ("ا" + C + "ت" + C + "ا" + C, "اِ1ْتِ2َا3"),
    ("م" + C + "ت" + C + C, "مُ1ْتَ2ِ3"),
    ("است" + C + C + C, "اِسْتَ1ْ2َ3"),
    ("ان" + C + C + C, "اِنْ1َ2َ3"),
    ("ا" + C + "ت" + C + C, "اِ1ْتَ2َ3"),
    ("م" + CW + C + "و" + C, "مَ1ْ2ُو3"),
    ("م" + C + "ا" + C + "ي" + C, "مَ1َا2ِي3"),
    ("م" + C + "ا" + C + C, "مُ1َا2ِ3"),
    ("م" + C + "ي" + C, "مُ1ِي2"),
    ("م" + C + "ا" + C, "مَ1َا2"),
    ("ت" + C + C + "ي" + C, "تَ1ْ2ِي3"),
    ("ت" + C + "ا" + C + C, "تَ1َا2ُ3"),
    ("ت" + CW + C + C, "تَ1َ2ُّ3"),
    ("إ" + C + C + "ا" + C, "إِ1ْ2َا3"),
    ("ا" + C + C + "ا" + C, "اِ1ْ2َا3"),
    ("أ" + C + C + "ا" + C, "أَ1ْ2َا3"),
    ("أ" + C + C + C, "أَ1ْ2َ3"),
    ("م" + C + C + C, "مُ1ْ2ِ3"),
    ("ي" + C + C + C, "يَ1ْ2َ3"),
    (C + "ا" + C + "ي" + C, "1َا2ِي3"),
    (C + CW + "ا" + C + C, "1َ2َا3ِ4"),
    (C + C + C + "و" + C, "1ُ2ْ3ُو4"),
    (C + C + C + "ى", "1َ2ْ3َى"),
    (C + "ا" + C + C, "1َا2ِ3"),
    (C + C + "ا" + C, "1ِ2َا3"),
    (C + C + "ي" + C, "1َ2ِي3"),
    (C + C + "و" + C, "1ُ2ُو3"),
    (C + "ا" + C, "1َا2"),
    (CW + "و" + C, "1َوْ2"),
    (CW + "ي" + C, "1َيْ2"),
    (C + C + C, CCC_TEMPLATE),
)
_PATTERNS = tuple((re.compile(p + "$"), t) for p, t in PATTERNS)
FALLBACK_ENDINGS = (("يات", "ِيَّات"), ("يين", "ِيِّين"), ("ية", "ِيَّة"), ("يا", "ِيًّا"),
                    ("ات", "َات"), ("ون", "ُون"), ("ين", "ِين"), ("ة", "َة"), ("ي", "ِيّ"),
                    ("وا", "ُوا"), ("ا", "ًا"), ("ت", "َت"))


def _template(stem: str) -> str | None:
    for rx, tpl in _PATTERNS:
        m = rx.match(stem)
        if m:
            out = tpl
            for k, g in enumerate(m.groups(), 1):
                out = out.replace(str(k), g)
            return out
    return None


def default_vocalize(stem: str) -> str:
    """The default reading: a consonant before و / ي followed by a consonant (or the end) has
    the long vowel uu / ii; a consonant before ا or ى has aa; word-final يا / وا after a
    consonant is y aa / w aa; every other consonant but the last gets a."""
    n = len(stem)
    out = []
    k = 0
    while k < n:
        ch = stem[k]
        out.append(ch)
        if ch in "اىةآ":
            k += 1
            continue
        nxt = stem[k + 1] if k + 1 < n else ""
        after = stem[k + 2] if k + 2 < n else ""
        if nxt in ("و", "ي") and after not in ("ا", "ى", "ة"):
            out.append((DAMMA if nxt == "و" else KASRA) + nxt)
            k += 2
            continue
        if nxt in ("و", "ي") and after == "ا" and k + 3 == n:
            out.append(SUKUN)  # سوريا, ألمانيا
        elif nxt in ("ا", "ى", "ة"):
            out.append(FATHA)
        elif nxt and k > 0 and after in ("ا", "و", "ي") and stem[k - 1] not in "و":
            out.append(SUKUN)  # a closed syllable before C + long vowel: فيسبوك, دارفور
        elif nxt:
            out.append(FATHA)
        k += 1
    return "".join(out)


def _stem_vocalize(rest: str) -> str | None:
    """A stem by the patterns, with or without one of FALLBACK_ENDINGS; None if none fits."""
    for ending, voc in FALLBACK_ENDINGS:
        if rest.endswith(ending) and len(rest) - len(ending) >= 3:
            tpl = _template(rest[: -len(ending)])
            if tpl:
                return tpl + voc
    return _template(rest)


def pattern_vocalize(word: str) -> str:
    """Vowels by the word patterns: the article (with its proclitics) or one proclitic when the
    rest fits a pattern, then the stem and its ending; else the default reading."""
    for pre, rest, art in _proclitic_splits(word):
        if art and len(rest) >= 2:
            return pre + (_stem_vocalize(rest) or default_vocalize(rest))
    voc = _stem_vocalize(word)
    if voc:
        return voc
    for pre, rest, _art in _proclitic_splits(word):
        if pre and len(rest) >= 3 and len(pre.replace(FATHA, "").replace(KASRA, "")) == 1:
            voc = _stem_vocalize(rest)
            if voc:
                return pre + voc
    return default_vocalize(word)


@functools.cache
def spelling_table() -> dict[str, str]:
    """Words whose spelling hides a long vowel or has a silent letter (lexicons/ar/spelling.tsv)."""
    return load_table("ar", "spelling")


def spelling_vocalize(bare: str) -> str | None:
    """The spelling-table form of a bare word, also after proclitics (وهذا, بالله)."""
    table = spelling_table()
    if bare in table:
        return table[bare]
    for pre, rest, art in _proclitic_splits(bare):
        if not art and pre and rest in table:
            return pre + table[rest]
    return None


@functools.lru_cache(maxsize=65536)
def vocalize(word: str) -> str:
    """The word with vowel marks: the spelling table (هذا, ذلك, الله) first, then the word as
    written when it has vowel marks, else from the lexicon, else from the patterns."""
    w = unicodedata.normalize("NFC", word).replace(TATWEEL, "")
    bare = strip_marks(w)
    special = spelling_vocalize(bare)
    if special:
        return special
    if has_vowel_marks(w):
        return w
    found = lexicon_vocalize(bare)
    if not found and bare.endswith("ى") and len(bare) > 2:
        found = lexicon_vocalize(bare[:-1] + "ي")  # Egyptian spelling: final ي written ى
    return found or pattern_vocalize(bare)


@functools.lru_cache(maxsize=65536)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one Arabic word with stress ('كتاب' -> k i t aa1 b), no AR: prefix."""
    return tuple(stress(read_vocalized(vocalize(word))))


def word_tokens_ar(word: str) -> list[str]:
    return [f"AR:{p}" for p in phonemes(word)]


def unreadable_ar(text: str) -> list[str]:
    """Letters the Arabic front-end cannot read (other scripts), to filter training sentences;
    Arabic letters and Latin letters (read by the English module) are readable."""
    def readable(ch: str) -> bool:
        if is_arabic(ch):
            return FOLD.get(ch, ch) in LETTERS or not is_arabic_letter(ch)
        return unicodedata.normalize("NFKD", ch)[:1].isascii()

    return [ch for ch in text if ch.isalpha() and not readable(ch)]
