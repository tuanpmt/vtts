"""Lao text -> words -> syllables -> lo-en tokens (spelling patterns, consonant classes, tones).

Lao is written without spaces between words. Modern Lao spelling writes every vowel and has no
silent letters, so a run of Lao letters is read like Thai (th/g2p_th.py) with simpler tables, in
three steps (the C port follows the same steps):

1. Words (segment). Over lexicons/lo/words.txt (a word list made offline from Google's Lao
   spell-check list, Apache-2.0, and the Lao-English dictionary of the Lao E-Government Center,
   MIT, kept when they occur in Lao Wikipedia; scripts/frontend/build_lo_lexicon.py) and the keys
   of lexicons/lo/overrides.tsv: the split with the fewest characters outside listed words (a lone
   consonant counts 3), then the fewest pieces. ໆ repeats the word before it.
2. Syllables. A word in overrides.tsv is read from its respelling (one syllable per "-" separated
   piece). Any other word is split into syllables by dynamic programming over the syllable
   patterns: preposed vowels ເ ແ ໂ ໃ ໄ, the vowel table VOWELS (short and long vowels, the
   diphthongs ia ua uea, ຳ ໄ ໃ ເົາ), the initial (one consonant; ຫ before a low sonorant and the
   ligatures ໜ ໝ ຫຼ; a consonant + ວ or + ຼ cluster), the final consonant, and syllables without a
   written vowel (closed: o, open: a; rare in modern spelling). The split with the lowest cost wins:
   10 per syllable, +4 for an unwritten o, +7 for an unwritten a (+10 more at the end of a word),
   +1 for a ວ cluster, -1 for a loanword cluster of a stop or f + ຣ/ລ (ໂປຣແກຣມ, ກຣາມ). Letters
   under the cancellation mark ໌ are silent.
3. Tones (Vientiane Lao, six tones). Consonant class (high ຂ ສ ຖ ຜ ຝ ຫ, also ຫ before a low
   sonorant; middle ກ ຈ ດ ຕ ບ ປ ຢ ອ; low the rest), the tone mark and whether the syllable is live
   (long vowel or a sonorant final) or dead (short open vowel or a stop final), see tone(). T1 low
   rising, T2 high rising, T3 mid, T4 low falling, T5 high falling, T6 mid rising.

Finals collapse to the six final sounds k p t m n ng and the glides w j (FINAL).
"""

from __future__ import annotations

import functools
from collections.abc import Collection
from dataclasses import dataclass

from ..lexicons import load_table, load_words

# ---------------- letters ----------------

HIGH = "ຂສຖຜຝຫຐຨຩ"
MID = "ກຈດຕບປຢອຉຏ"
LOW = "ຄງຊຍທນພຟມຣລວຮຆຌຎຑຒຓຘຠຬ"
CONSONANTS = HIGH + MID + LOW
CLASS = {**dict.fromkeys(HIGH, "H"), **dict.fromkeys(MID, "M"), **dict.fromkeys(LOW, "L")}
LOW_SONORANTS = "ງຍນມຣລວ"

INITIAL = {
    "ກ": "k", "ຂ": "kh", "ຄ": "kh", "ຆ": "kh", "ງ": "ng", "ຈ": "c", "ຉ": "c", "ສ": "s", "ຊ": "s",
    "ຌ": "s", "ຨ": "s", "ຩ": "s", "ຍ": "ny", "ຎ": "ny", "ດ": "d", "ຕ": "t", "ຏ": "t", "ຖ": "th",
    "ທ": "th", "ຐ": "th", "ຑ": "th", "ຒ": "th", "ຘ": "th", "ນ": "n", "ຓ": "n", "ບ": "b", "ປ": "p",
    "ຜ": "ph", "ພ": "ph", "ຠ": "ph", "ຝ": "f", "ຟ": "f", "ມ": "m", "ຢ": "j", "ຣ": "r", "ລ": "l",
    "ຬ": "l", "ວ": "w", "ຫ": "h", "ຮ": "h", "ອ": "?",
}
FINAL = {
    **dict.fromkeys("ກຂຄຆ", "k"), "ງ": "ng",
    **dict.fromkeys("ຈຉສຊຌຨຩດຕຏຖທຐຑຒຘ", "t"),
    **dict.fromkeys("ບປຜພຠຝຟ", "p"), "ມ": "m", **dict.fromkeys("ນຓລຣຬຎ", "n"), "ຍ": "j", "ວ": "w",
}

PREPOSED = "ເແໂໃໄ"
TONE_MARKS = "່້໊໋"
ABOVE_BELOW = "ັິີຶືຸູົໍ"
CANCEL = "໌"
REPEAT, ELLIPSIS = "ໆ", "ຯ"
SUB_LO = "ຼ"  # subscript l: ຫຼ = l (high class), C + ຼ = C l
# Characters that attach to the consonant before them (a syllable cannot start with them).
DEPENDENT = "ະັາຳິີຶື຺ຸູົຼຽ່້໊໋໌ໍ໎"
SHORT = frozenset(("a", "i", "ue", "u", "e", "ae", "o", "or", "oe"))

# (preposed vowel, letters after the initial, vowel, final: "" none, "F" required, "f" optional,
#  or "=" + the final sound the pattern itself ends in). A vowel ending in "." is short.
VOWELS: tuple[tuple[str, str, str, str], ...] = (
    ("", "ະ", "a", ""), ("", "ັ", "a", "F"), ("", "າ", "aa", "f"), ("", "ຳ", "a", "=m"),
    ("", "ິ", "i", "f"), ("", "ີ", "ii", "f"), ("", "ຶ", "ue", "f"), ("", "ື", "uue", "f"),
    ("", "ຸ", "u", "f"), ("", "ູ", "uu", "f"), ("", "ົ", "o", "F"),
    ("", "ໍ", "oor", ""), ("", "ອ", "oor", "F"), ("", "ັອ", "or", "F"),
    ("", "ົວະ", "ua.", ""), ("", "ົວ", "ua", ""), ("", "ວ", "ua", "F"), ("", "ຽ", "ia", "F"),
    ("ເ", "ະ", "e", ""), ("ເ", "ັ", "e", "F"), ("ເ", "", "ee", "f"),
    ("ແ", "ະ", "ae", ""), ("ແ", "ັ", "ae", "F"), ("ແ", "", "aae", "f"),
    ("ໂ", "ະ", "o", ""), ("ໂ", "", "oo", "f"),
    ("ເ", "າະ", "or", ""), ("ເ", "ົາ", "a", "=w"),
    ("ເ", "ິ", "oe", "f"), ("ເ", "ີ", "ooe", "f"),
    ("ເ", "ັຍ", "ia.", ""), ("ເ", "ຍ", "ia", ""),
    ("ເ", "ຶອ", "uea.", ""), ("ເ", "ືອ", "uea", "f"),
    ("ໃ", "", "a", "=j"), ("ໄ", "", "a", "=j"),
)
SYLLABLE, UNWRITTEN_O, UNWRITTEN_A, WORD_FINAL_A, CLUSTER_W, CLUSTER_RL = 10, 4, 7, 10, 1, -1
# Loanword clusters with ຣ or ລ (ໂປຣແກຣມ, ກຣາມ, ຟລູ): a stop or f + r/l, preferred to a final.
RL_FIRST = "ກຂຄປພຜຕທບດຟ"

# Tones: T1 low rising, T2 high rising, T3 mid, T4 low falling, T5 high falling, T6 mid rising.
T_LR, T_HR, T_MID, T_LF, T_HF, T_MR = 1, 2, 3, 4, 5, 6


@dataclass(frozen=True)
class Syllable:
    initials: tuple[str, ...]  # 1 or 2 initial sounds
    cls: str                   # H, M or L (ຫ before a low sonorant: H)
    vowel: str
    final: str = ""            # k p t m n ng w j or ""
    mark: str = ""             # tone mark
    short: bool = False
    kind: str = "x"            # x: written vowel, o: unwritten o, a: unwritten a

    @property
    def live(self) -> bool:
        return self.final in ("m", "n", "ng", "w", "j") or (not self.final and not self.short)

    @property
    def tone(self) -> int:
        return tone(self.cls, self.mark, self.live, self.short)

    def tokens(self) -> list[str]:
        out = [f"LO:I:{c}" for c in self.initials] + [f"LO:V:{self.vowel}"]
        if self.final:
            out.append(f"LO:F:{self.final}")
        return out + [f"LO:T{self.tone}"]


def tone(cls: str, mark: str, live: bool, short: bool) -> int:
    """Tone 1..6 of Vientiane Lao from class, tone mark and syllable type."""
    if mark == "່":
        return T_MID
    if mark == "້":
        return T_LF if cls == "H" else T_HF
    if mark == "໊":
        return T_HR
    if mark == "໋":
        return T_LR
    if live:
        return T_HR if cls == "L" else T_LR
    if short:
        return T_MID if cls == "L" else T_MR
    return T_LF if cls == "H" else T_HF


def prepare(word: str) -> str:
    """ໍາ -> ຳ (also with a tone mark between them), ໜ ໝ -> ຫນ ຫມ, Pali virama ຺ and ໎ dropped,
    a consonant under ໌ (with ິ ຸ on it) dropped."""
    w = word.replace("ໜ", "ຫນ").replace("ໝ", "ຫມ").replace("຺", "").replace("໎", "")
    for t in TONE_MARKS:
        w = w.replace("ໍ" + t + "າ", t + "ຳ")
    w = w.replace("ໍາ", "ຳ")
    out: list[str] = []
    for ch in w:
        if ch != CANCEL:
            out.append(ch)
            continue
        if out and out[-1] in "ິຸ":
            out.pop()
        if out and out[-1] in CLASS:
            out.pop()
    return "".join(out)


# ---------------- one word -> syllables ----------------

def _initials(w: str, k: int) -> list[tuple[int, tuple[str, ...], str, int]]:
    """(end, sounds, class, extra cost) for the initial at w[k]."""
    n, c = len(w), w[k]
    out = [(k + 1, (INITIAL[c],), CLASS[c], 0)]
    if k + 1 >= n:
        return out
    c2 = w[k + 1]
    if c == "ຫ" and c2 in LOW_SONORANTS:
        out.append((k + 2, (INITIAL[c2],), "H", 0))
    elif c2 == SUB_LO:
        out.append((k + 2, ("l",) if c == "ຫ" else (INITIAL[c], "l"), "H" if c == "ຫ" else CLASS[c], 0))
    elif c2 == "ວ" and c != "ວ":
        out.append((k + 2, (INITIAL[c], "w"), CLASS[c], CLUSTER_W))
    elif c2 in "ຣລ" and c in RL_FIRST:
        out.append((k + 2, (INITIAL[c], INITIAL[c2]), CLASS[c], CLUSTER_RL))
    if c == "ຫ" and c2 in LOW_SONORANTS and k + 2 < n and w[k + 2] == "ວ":
        out.append((k + 3, (INITIAL[c2], "w"), "H", CLUSTER_W))
    return out


def _take(w: str, pos: int, letters: str, mark: str) -> tuple[int, str] | None:
    """Match letters at w[pos] allowing one tone mark after the initial or an above/below vowel."""
    n = len(w)
    if not mark and pos < n and w[pos] in TONE_MARKS:
        mark, pos = w[pos], pos + 1
    for ch in letters:
        if pos >= n or w[pos] != ch:
            return None
        pos += 1
        if ch in ABOVE_BELOW and not mark and pos < n and w[pos] in TONE_MARKS:
            mark, pos = w[pos], pos + 1
    return pos, mark


def _final_at(w: str, pos: int) -> str:
    """The final sound of w[pos] when it can close a syllable (not followed by a vowel sign)."""
    if pos >= len(w) or w[pos] not in FINAL:
        return ""
    if pos + 1 < len(w) and w[pos + 1] in DEPENDENT:
        return ""
    return FINAL[w[pos]]


def syllables_at(w: str, i: int) -> list[tuple[int, Syllable, int]]:
    """Every syllable (end, syllable, cost) that can start at w[i]."""
    n = len(w)
    out: list[tuple[int, Syllable, int]] = []
    pre = w[i] if w[i] in PREPOSED else ""
    k = i + len(pre)
    if k >= n or w[k] not in CLASS:
        return out
    for k2, sounds, cls, extra in _initials(w, k):
        for p_pre, letters, vowel, fin in VOWELS:
            if p_pre != pre:
                continue
            got = _take(w, k2, letters, "")
            if got is None:
                continue
            pos, mark = got
            short = vowel in SHORT or vowel.endswith(".")
            v = vowel.rstrip(".")
            cost = SYLLABLE + extra
            if fin.startswith("="):
                out.append((pos, Syllable(sounds, cls, v, fin[1:], mark, short), cost))
                continue
            if fin in ("", "f"):
                out.append((pos, Syllable(sounds, cls, v, "", mark, short), cost))
            if fin in ("F", "f"):
                f = _final_at(w, pos)
                if f and not (letters == "ົ" and f == "w"):  # ົວ is the vowel ua
                    out.append((pos + 1, Syllable(sounds, cls, v, f, mark, short), cost))
        if pre:
            continue
        # no written vowel: closed -> o, open -> a
        pos, mark = k2, ""
        if pos < n and w[pos] in TONE_MARKS:
            mark, pos = w[pos], pos + 1
        f = _final_at(w, pos)
        if f:
            out.append((pos + 1, Syllable(sounds, cls, "o", f, mark, True, "o"), SYLLABLE + UNWRITTEN_O + extra))
        if pos == k2 and (pos >= n or w[pos] not in DEPENDENT):
            out.append((k2, Syllable(sounds, cls, "a", "", "", True, "a"), SYLLABLE + UNWRITTEN_A + extra))
    return out


def parse_word(word: str) -> list[Syllable]:
    """Syllables of one Lao word by the lowest-cost split; characters that start no syllable are
    skipped."""
    w = prepare(word)
    n = len(w)
    best: list[tuple[int, list[Syllable]] | None] = [None] * (n + 1)
    best[0] = (0, [])
    for i in range(n):
        if best[i] is None:
            continue
        cost0, syls0 = best[i]
        steps = [(j, [s], c) for j, s, c in syllables_at(w, i)] or [(i + 1, [], 100)]
        for j, syls, cost in steps:
            if j < n and w[j] in DEPENDENT:
                continue
            if j == n and syls and syls[-1].kind == "a" and syls0:
                cost += WORD_FINAL_A
            total = cost0 + cost
            if best[j] is None or total < best[j][0]:
                best[j] = (total, syls0 + syls)
    if best[n] is None:  # a dependent sign with nothing before it: skip it
        last = max(i for i in range(n) if best[i] is not None)
        return best[last][1] + parse_word(w[last + 1:]) if last + 1 < n else best[last][1]
    return best[n][1]


# ---------------- lexicon: words and respellings ----------------

@functools.cache
def override_table() -> dict[str, tuple[str, ...]]:
    return {k: tuple(v.split("-")) for k, v in load_table("lo", "overrides").items()}


@functools.cache
def word_set() -> frozenset[str]:
    return load_words("lo", "words") | frozenset(override_table())


@functools.cache
def _max_word() -> int:
    return max((len(w) for w in word_set()), default=1)


def read_respelling(pieces: tuple[str, ...]) -> list[Syllable]:
    """One syllable per piece of a respelling (a piece that is not one syllable is parsed)."""
    out: list[Syllable] = []
    for p in pieces:
        q = prepare(p)
        one = [s for j, s, _ in syllables_at(q, 0) if j == len(q)]
        out.extend([min(one, key=lambda s: s.kind != "x")] if one else parse_word(p))
    return out


def word_syllables(word: str) -> list[Syllable]:
    table = override_table()
    return read_respelling(table[word]) if word in table else parse_word(word)


def segment(run: str, words: Collection[str] | None = None, maxw: int | None = None) -> list[str]:
    """Words of a run of Lao letters (after prepare()): fewest characters outside the word list (a lone consonant
    read with an unwritten a counts 3), then fewest pieces. Consecutive pieces outside the list are
    returned as one piece."""
    if words is None:
        words, maxw = word_set(), _max_word()
    elif maxw is None:
        maxw = max(map(len, words), default=1)
    n = len(run)
    best: list[tuple[int, int, int, bool] | None] = [None] * (n + 1)
    best[0] = (0, 0, 0, False)
    w = run
    for i in range(n):
        if best[i] is None or w[i] in DEPENDENT:
            continue
        unk, cnt = best[i][:2]
        cands = [(j, 0) for j in range(min(n, i + maxw), i, -1) if w[i:j] in words]
        cands += [(j, j - i + 2 * (s.kind == "a")) for j, s, _ in syllables_at(w, i)] or [(i + 1, 1)]
        for j, u in cands:
            if j < n and w[j] in DEPENDENT:
                continue
            key = (unk + u, cnt + 1, i, u > 0)
            if best[j] is None or key[:2] < best[j][:2]:
                best[j] = key
    if best[n] is None:
        return [run]
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


def run_syllables(run: str) -> list[Syllable]:
    """Syllables of a run of Lao letters (ໆ repeats the word before it)."""
    out: list[Syllable] = []
    last: list[Syllable] = []
    for k, piece in enumerate(prepare(run).split(REPEAT)):
        if k > 0:
            out.extend(last)
        if piece:
            for word in segment(piece):
                last = word_syllables(word)
                out.extend(last)
    return out


def lao_syllable_tokens(run: str) -> list[list[str]]:
    """Tokens per syllable of a run of Lao letters."""
    return [s.tokens() for s in run_syllables(run)]


def is_lao(ch: str) -> bool:
    """Lao letters and signs (U+0E81..U+0ECD, ໜ ໝ ໞ ໟ; not the digits)."""
    return "ກ" <= ch <= "ໍ" or "ໜ" <= ch <= "ໟ"


def unreadable_lo(text: str) -> list[str]:
    """Letters the Lao front-end cannot read (other scripts than Lao and Latin), to filter training
    sentences."""
    import unicodedata

    out = []
    for ch in text:
        if not ch.isalpha() or is_lao(ch) or ch.isascii():
            continue
        base = unicodedata.normalize("NFKD", ch)[:1]
        if not (base.isascii() and base.isalpha()):
            out.append(ch)
    return out
