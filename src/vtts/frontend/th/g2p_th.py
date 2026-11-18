"""Thai text -> words -> syllables -> th-en tokens (spelling rules, consonant classes, tones).

Thai is written without spaces between words, so a run of Thai letters is read in three steps,
all table-driven (the C port follows the same steps):

1. Words (segment). Over lexicons/th/words.txt (a word list made offline from PyThaiNLP's CC0
   word list, see scripts/frontend/build_th_lexicon.py) and the keys of lexicons/th/overrides.tsv:
   the split with the fewest characters outside listed words (a lone consonant counts 3), then
   the fewest pieces. Text outside the list is read in one piece. ๆ repeats the word before it.
2. Syllables. A word in overrides.tsv is read from its respelling (one syllable per "-"
   separated piece, each read by the rules below, e.g. ราชการ -> ราด-ชะ-กาน); respelled words
   inside a longer word are read the same way (ได้ in ได้รับ). Any other word is split into
   syllables by dynamic programming over the syllable patterns: preposed vowels เ แ โ ใ ไ, the
   vowel table VOWELS (short and long vowels, diphthongs, ำ ไ ใ เา), initial clusters (กร กล กว
   ... ; จร ซร ศร สร with a silent ร, ทร read s), ห and leading consonants before a low sonorant,
   the final consonant, and syllables without a written vowel (closed: o, with a final ร: oor + n
   as in นคร; open: a, as in สบาย; บ alone is บอ). The split with the lowest cost wins: 10 per
   syllable, +4 for an unwritten o, +7 for an unwritten a (+10 more at the end of a word), +2 for
   a leading consonant split from a preposed vowel (เสมอ = ส + เมอ), +10 for an open preposed
   vowel before a syllable without a written vowel (แสดง), -1 for a true cluster.
   Silent letters (silence): under the thanthakhat ์ (with a vowel ิ ุ on them, and the consonant
   before a silent ร after a final: จันทร์ ศาสตร์), ร after a final stop at the end of a word
   (บุตร, เมตร), a final ิ ุ after ั + consonant (ปฏิบัติ). A final ฐ ฒ ษ ศ ธ ฏ inside a word is
   also read as the next initial with a (รัฐบาล = รัด-ถะ-บาน; LINKING).
3. Tones. Consonant class (mid, high, low) of the initial, or of the leading consonant (ห, or a
   mid/high consonant read with an unwritten a before a low sonorant: สนุก, ขนม, อร่อย), the tone
   mark and whether the syllable is live (long vowel or a sonorant final) or dead (short open
   vowel or a stop final), see tone(). Five tones: T1 mid, T2 low, T3 falling, T4 high, T5 rising.

Finals collapse to the six final sounds k p t m n ng and the glides w j (FINAL).
"""

from __future__ import annotations

import functools
from collections.abc import Collection
from dataclasses import dataclass, replace

from ..lexicons import load_table, load_words

# ---------------- letters ----------------

MID = "กจฎฏดตบปอ"
HIGH = "ขฃฉฐถผฝศษสห"
LOW = "คฅฆงชซฌญฑฒณทธนพฟภมยรลวฬฮ"
CONSONANTS = MID + HIGH + LOW
LOW_SONORANTS = "งญณนมยรลวฬ"
CLASS = {**dict.fromkeys(MID, "M"), **dict.fromkeys(HIGH, "H"), **dict.fromkeys(LOW, "L")}

INITIAL = {
    "ก": "k", "ข": "kh", "ฃ": "kh", "ค": "kh", "ฅ": "kh", "ฆ": "kh", "ง": "ng", "จ": "c",
    "ฉ": "ch", "ช": "ch", "ซ": "s", "ฌ": "ch", "ญ": "j", "ฎ": "d", "ฏ": "t", "ฐ": "th",
    "ฑ": "th", "ฒ": "th", "ณ": "n", "ด": "d", "ต": "t", "ถ": "th", "ท": "th", "ธ": "th",
    "น": "n", "บ": "b", "ป": "p", "ผ": "ph", "ฝ": "f", "พ": "ph", "ฟ": "f", "ภ": "ph", "ม": "m",
    "ย": "j", "ร": "r", "ล": "l", "ว": "w", "ศ": "s", "ษ": "s", "ส": "s", "ห": "h", "ฬ": "l",
    "อ": "?", "ฮ": "h",
}
FINAL = {
    **dict.fromkeys("กขฃคฅฆ", "k"),
    **dict.fromkeys("จฉชซฌฎฏฐฑฒดตถทธศษส", "t"),
    **dict.fromkeys("บปพฟภ", "p"),
    "ง": "ng", "ม": "m", **dict.fromkeys("ญณนรลฬ", "n"), "ย": "j", "ว": "w",
}
# True clusters (both consonants sounded); the class is that of the first consonant.
CLUSTERS = frozenset(["กร", "กล", "กว", "ขร", "ขล", "ขว", "คร", "คล", "คว", "ตร", "ปร", "ปล",
                      "พร", "พล", "บล", "ดร", "ฟร", "ฟล"])
SILENT_R = frozenset("จซศส")  # จร ซร ศร สร: ร silent (จริง, สร้าง); ทร is read s (ทราย)

PREPOSED = "เแโใไ"
TONE_MARKS = "่้๊๋"
ABOVE_BELOW = "ัิีึืุู"
THANTHAKHAT = "์"
REPEAT, ABBREV = "ๆ", "ฯ"
LINKING = "ฐฒษศธฏ"  # Pali/Sanskrit finals read again as the next initial inside a word
# Characters that attach to the consonant before them (a syllable cannot start with them).
DEPENDENT = "ะัาำิีึืฺุู็่้๊๋์ํ๎ๅ"
SHORT = frozenset(("a", "i", "ue", "u", "e", "ae", "o", "or", "oe"))

# (preposed vowel, letters after the initial, vowel, final: "" none, "F" required, "f" optional,
#  or the final sound the pattern itself ends in). Order does not matter (the costs decide).
VOWELS: tuple[tuple[str, str, str, str], ...] = (
    ("", "ะ", "a", ""), ("", "ั", "a", "F"), ("", "า", "aa", "f"), ("", "ำ", "a", "=m"),
    ("", "ิ", "i", "f"), ("", "ี", "ii", "f"), ("", "ึ", "ue", "f"), ("", "ือ", "uue", ""),
    ("", "ื", "uue", "F"), ("", "ุ", "u", "f"), ("", "ู", "uu", "f"),
    ("", "ัวะ", "ua.", ""), ("", "ัว", "ua", ""), ("", "ว", "ua", "F"),
    ("", "็อ", "or", "F"), ("", "อ", "oor", "f"), ("", "รร", "a", "F"), ("", "รร", "a", "=n"),
    ("เ", "ะ", "e", ""), ("เ", "็", "e", "F"), ("เ", "", "ee", "f"),
    ("แ", "ะ", "ae", ""), ("แ", "็", "ae", "F"), ("แ", "", "aae", "f"),
    ("โ", "ะ", "o", ""), ("โ", "", "oo", "f"),
    ("เ", "าะ", "or", ""), ("เ", "า", "a", "=w"),
    ("เ", "อะ", "oe", ""), ("เ", "อ", "ooe", "f"), ("เ", "ิ", "ooe", "F"), ("เ", "ย", "ooe", "=j"),
    ("เ", "ียะ", "ia.", ""), ("เ", "ีย", "ia", "f"), ("เ", "ือะ", "uea.", ""), ("เ", "ือ", "uea", "f"),
    ("ใ", "", "a", "=j"), ("ไ", "ย", "a", "=j"), ("ไ", "", "a", "=j"),
)
SYLLABLE, UNWRITTEN_O, UNWRITTEN_A, WORD_FINAL_A, SPLIT_LEAD, OPEN_PREPOSED = 10, 4, 7, 10, 2, 10

# Tone without a mark: (class, live) for mid/high, (class, live, short) for low.
T_MID, T_LOW, T_FALLING, T_HIGH, T_RISING = 1, 2, 3, 4, 5


@dataclass(frozen=True)
class Syllable:
    initials: tuple[str, ...]  # 1 or 2 initial sounds
    cls: str                   # M, H or L (after ห / leading consonants)
    vowel: str
    final: str = ""            # k p t m n ng w j or ""
    mark: str = ""             # tone mark
    short: bool = False
    kind: str = "x"            # x: written vowel, o: unwritten o, a: unwritten a
    lone: str = ""             # the consonant of an unwritten-a syllable (leading rule)
    coda: str = ""             # the letter of the final (linking rule)

    @property
    def live(self) -> bool:
        return self.final in ("m", "n", "ng", "w", "j") or (not self.final and not self.short)

    @property
    def tone(self) -> int:
        return tone(self.cls, self.mark, self.live, self.short)

    def tokens(self) -> list[str]:
        out = [f"TH:I:{c}" for c in self.initials] + [f"TH:V:{self.vowel}"]
        if self.final:
            out.append(f"TH:F:{self.final}")
        return out + [f"TH:T{self.tone}"]


def tone(cls: str, mark: str, live: bool, short: bool) -> int:
    """Tone 1..5 (mid, low, falling, high, rising) from class, tone mark and syllable type."""
    if mark == "่":
        return T_FALLING if cls == "L" else T_LOW
    if mark == "้":
        return T_HIGH if cls == "L" else T_FALLING
    if mark == "๊":
        return T_HIGH
    if mark == "๋":
        return T_RISING
    if cls == "L":
        return T_MID if live else (T_HIGH if short else T_FALLING)
    if not live:
        return T_LOW
    return T_RISING if cls == "H" else T_MID


# ---------------- one word -> syllables ----------------

def _initials(w: str, k: int, split: bool) -> list[tuple[int, tuple[str, ...], str, Syllable | None, int]]:
    """(end, sounds, class, syllable split off before, extra cost) for the initial at w[k]."""
    n, c = len(w), w[k]
    out: list[tuple[int, tuple[str, ...], str, Syllable | None, int]] = [(k + 1, (INITIAL[c],), CLASS[c], None, 0)]
    if k + 1 >= n or w[k + 1] not in CLASS:
        return out
    c2 = w[k + 1]
    if c + c2 in CLUSTERS:  # preferred to a final ร/ล on a tie: โปร = pro, not pon
        out.append((k + 2, (INITIAL[c], INITIAL[c2]), CLASS[c], None, -1))
    elif c2 == "ร" and c in SILENT_R:
        out.append((k + 2, (INITIAL[c],), CLASS[c], None, 0))
    elif c2 == "ร" and c == "ท":
        out.append((k + 2, ("s",), "L", None, 0))
    if c == "ห" and c2 in LOW_SONORANTS:
        out.append((k + 2, (INITIAL[c2],), "H", None, 0))
    elif split:  # preposed vowel before a leading consonant: เสมอ = ส(a) + เมอ
        lead = Syllable((INITIAL[c],), CLASS[c], "a", short=True, kind="a", lone=c)
        cls2 = CLASS[c] if c2 in LOW_SONORANTS and CLASS[c] != "L" else CLASS[c2]
        out.append((k + 2, (INITIAL[c2],), cls2, lead, SYLLABLE + UNWRITTEN_A + SPLIT_LEAD))
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


def _closed_next(w: str, pos: int, pre: str) -> bool:
    """The next syllable would be C + อ, a consonant pair without a written vowel, or (after เ)
    C + ิ: then the preposed vowel more likely belongs to it (เสมอ, แสดง, เฉลิม)."""
    n = len(w)
    if pos + 1 >= n or w[pos] not in CLASS:
        return False
    c = w[pos + 1]
    return c == "อ" or (pre == "เ" and c == "ิ") or (c in FINAL and (pos + 2 >= n or w[pos + 2] not in DEPENDENT))


def syllables_at(w: str, i: int) -> list[tuple[int, list[Syllable], int]]:
    """Every syllable (end, syllables, cost) that can start at w[i]; a leading consonant split
    from a preposed vowel gives two syllables."""
    n = len(w)
    out: list[tuple[int, list[Syllable], int]] = []
    pre = w[i] if w[i] in PREPOSED else ""
    k = i + len(pre)
    if k >= n:
        return out
    if w[k] in "ฤฦ" and not pre:
        return _rue(w, i, None)
    if w[k] not in CLASS:
        return out
    if not pre and k + 1 < n and w[k + 1] in "ฤ":
        return _rue(w, i + 1, w[k])
    for k2, sounds, cls, lead, extra in _initials(w, k, bool(pre)):
        before = [lead] if lead else []
        if pre:
            patterns = [p for p in VOWELS if p[0] == pre]
        else:
            patterns = [p for p in VOWELS if not p[0]]
        for _, letters, vowel, fin in patterns:
            got = _take(w, k2, letters, "")
            if got is None:
                continue
            pos, mark = got
            short = vowel in SHORT or vowel.endswith(".")
            v = vowel.rstrip(".")
            cost = SYLLABLE + extra
            if fin.startswith("="):
                out.append((pos, before + [Syllable(sounds, cls, v, fin[1:], mark, short)], cost))
                continue
            if fin in ("", "f"):
                if pre and not letters and _closed_next(w, pos, pre):  # เสมอ: not เส-มอ
                    cost += OPEN_PREPOSED
                out.append((pos, before + [Syllable(sounds, cls, v, "", mark, short)], cost))
            if fin in ("F", "f"):
                f = _final_at(w, pos)
                if letters == "ั" and f == "w":  # ัว is the vowel ua (ตัว), never a + w
                    f = ""
                if f and not (pre == "เ" and not letters and w[pos] == "ย"):  # เ-ย is ooe + j
                    out.append((pos + 1, before + [Syllable(sounds, cls, v, f, mark, short, coda=w[pos])],
                                cost))
                elif (letters == "ั" and pos + 2 < n and w[pos] in FINAL and w[pos + 1] in "ิุ"
                      and w[pos + 2] not in DEPENDENT):  # บัติ inside a word: bat + ti (ปฏิบัติการ)
                    c = w[pos]
                    out.append((pos + 2, before + [
                        Syllable(sounds, cls, v, FINAL[c], mark, short),
                        Syllable((INITIAL[c],), CLASS[c], "i" if w[pos + 1] == "ิ" else "u",
                                 short=True)], cost + SYLLABLE))
        if pre:
            continue
        # no written vowel: closed -> o (oor before a final ร), open -> a
        pos, mark = k2, ""
        if pos < n and w[pos] in TONE_MARKS:
            mark, pos = w[pos], pos + 1
        f = _final_at(w, pos)
        if f:
            if w[pos] == "ร":
                syl = Syllable(sounds, cls, "oor", "n", mark, False, "o", coda="ร")
            else:
                syl = Syllable(sounds, cls, "o", f, mark, True, "o", coda=w[pos])
            out.append((pos + 1, [syl], SYLLABLE + UNWRITTEN_O + extra))
        if len(sounds) == 1 and k2 == k + 1 and not mark:
            if w[k] == "บ":  # บ alone is read บอ: บริษัท, บรม, บดี
                syl = Syllable(sounds, cls, "oor", "", "", False, "a")
            else:
                syl = Syllable(sounds, cls, "a", "", "", True, "a", w[k])
            out.append((k2, [syl], SYLLABLE + UNWRITTEN_A))
    return out


def _rue(w: str, i: int, head: str | None) -> list[tuple[int, list[Syllable], int]]:
    """ฤ: alone r + ue (ฤๅ: uue), after a consonant C + r + i (พฤ: ph + r + ue); ฦ: l + ue."""
    n = len(w)
    letter = w[i]
    pos = i + 1
    long = pos < n and w[pos] == "ๅ"
    pos += long
    if head is None:
        init, cls = ("r",) if letter == "ฤ" else ("l",), "L"
        vowel = "uue" if long else "ue"
    else:
        init, cls = (INITIAL[head], "r"), CLASS[head]
        vowel = "ue" if head == "พ" else "i"
    out = [(pos, [Syllable(init, cls, vowel, "", "", not long)], SYLLABLE)]
    f = _final_at(w, pos)
    if f and not long:
        out.append((pos + 1, [Syllable(init, cls, vowel, f, "", True, coda=w[pos])], SYLLABLE))
    return out


def silence(word: str) -> str:
    """Drop letters that are not pronounced: under ์ (with ิ or ุ on them, and the consonant before
    before a silent ร when it follows another consonant: จันทร์ -> จัน), phinthu/yamakkan, and ร after a final stop
    at the end of a word (บุตร, จักร, เมตร); a final ิ ุ after ั + consonant (ปฏิบัติ)."""
    w = word.replace("ฺ", "").replace("๎", "")
    out: list[str] = []
    for ch in w:
        if ch != THANTHAKHAT:
            out.append(ch)
            continue
        if out and out[-1] in "ิุ":
            out.pop()
        if (out and out[-1] in CLASS and out.pop() == "ร" and len(out) >= 2
                and out[-1] in CLASS and out[-1] != "อ" and out[-2] in CLASS):
            out.pop()  # ทร์ ตร์ after a final: จันทร์, ศาสตร์
    w = "".join(out)
    if len(w) >= 3 and w[-1] in "ิุ" and w[-2] in FINAL and w[-3] == "ั":  # ปฏิบัติ, สมบัติ
        w = w[:-1]
    if (len(w) >= 3 and w[-1] == "ร" and FINAL.get(w[-2]) in ("k", "p", "t")
            and (w[-3] in "ัิีุู" or (len(w) >= 4 and w[-4] in PREPOSED))):  # บุตร, เมตร
        w = w[:-1]
    return w


def parse_word(word: str) -> list[Syllable]:
    """Syllables of one Thai word by the lowest-cost split; characters that start no syllable
    are skipped."""
    w = silence(word)
    n = len(w)
    best: list[tuple[int, list[Syllable]] | None] = [None] * (n + 1)
    best[0] = (0, [])
    for i in range(n):
        if best[i] is None:
            continue
        cost0, syls0 = best[i]
        steps = syllables_at(w, i) or [(i + 1, [], 100)]
        for j, syls, cost in steps:
            if j < n and w[j] in DEPENDENT:
                continue
            if j == n and syls and syls[-1].kind == "a" and (syls0 or len(syls) > 1):
                cost += WORD_FINAL_A
            total = cost0 + cost
            if best[j] is None or total < best[j][0]:
                best[j] = (total, syls0 + syls)
    if best[n] is None:  # a dependent sign with nothing before it: skip it
        last = max(i for i in range(n) if best[i] is not None)
        return best[last][1] + parse_word(w[last + 1:]) if last + 1 < n else best[last][1]
    return _leading(_link(best[n][1]))


def _link(syls: list[Syllable]) -> list[Syllable]:
    """A final ฐ ฒ ษ ศ ธ ฏ inside a word is also read as an initial with an unwritten a
    (รัฐบาล = รัด-ถะ-บาน, เทศกาล, พิษณุ, อยุธยา); the inserted syllable leads no consonant."""
    out: list[Syllable] = []
    for k, s in enumerate(syls):
        out.append(s)
        if s.coda and s.coda in LINKING and k + 1 < len(syls):
            out.append(Syllable((INITIAL[s.coda],), CLASS[s.coda], "a", short=True, kind="a"))
    return out


def _leading(syls: list[Syllable]) -> list[Syllable]:
    """A mid/high consonant read with an unwritten a lends its class to a following single low
    sonorant initial (สนุก, ขนม, อร่อย)."""
    out = list(syls)
    for k in range(len(out) - 1):
        a, b = out[k], out[k + 1]
        if (a.kind == "a" and a.lone and a.cls != "L" and b.cls == "L" and len(b.initials) == 1
                and _sonorant(b)):
            out[k + 1] = replace(b, cls=a.cls)
    return out


_SONORANT_SOUNDS = frozenset(("ng", "j", "n", "m", "r", "l", "w"))


def _sonorant(s: Syllable) -> bool:
    return s.initials[0] in _SONORANT_SOUNDS


# ---------------- lexicon: words and respellings ----------------

@functools.cache
def override_table() -> dict[str, tuple[str, ...]]:
    return {k: tuple(v.split("-")) for k, v in load_table("th", "overrides").items()}


@functools.cache
def word_set() -> frozenset[str]:
    return load_words("th", "words") | frozenset(override_table())


@functools.cache
def _max_word() -> int:
    return max((len(w) for w in word_set()), default=1)


def read_respelling(pieces: tuple[str, ...]) -> list[Syllable]:
    """One syllable per piece of a respelling; a piece with no single-syllable reading is split."""
    out: list[Syllable] = []
    for p in pieces:
        one = [s for j, s, _ in syllables_at(p, 0) if j == len(p) and len(s) == 1]
        out.extend(min(one, key=lambda s: s[0].kind != "x") if one else parse_word(p))
    return out


def word_syllables(word: str) -> list[Syllable]:
    """Syllables of one word: its respelling, or the rules, with the respelled words inside it
    (ได้ in ได้รับ, เหตุ in อุบัติเหตุ) read from their respellings."""
    table = override_table()
    if word in table:
        return read_respelling(table[word])
    pieces = segment(word, table, _max_override())
    if len(pieces) == 1:
        return parse_word(word)
    return [s for p in pieces for s in (read_respelling(table[p]) if p in table else parse_word(p))]


@functools.cache
def _max_override() -> int:
    return max(map(len, override_table()), default=1)


def _after_silent(run: str, j: int) -> int:
    """j moved past letters silenced by ์ that follow it (การณ์, จันทร์)."""
    for k in (j + 1, j + 2, j + 3):
        if k < len(run) and run[k] == THANTHAKHAT and all(c in CLASS or c in "ิุ" for c in run[j:k]):
            return k + 1
    return j


def segment(run: str, words: Collection[str] | None = None, maxw: int | None = None) -> list[str]:
    """Words of a run of Thai letters: fewest characters outside the word list (a lone consonant
    read with an unwritten a counts 3), then fewest pieces. Text outside the list is cut into syllables while searching; consecutive such
    pieces are returned as one piece (read together, so leading consonants still apply)."""
    if words is None:
        words, maxw = word_set(), _max_word()
    elif maxw is None:
        maxw = max(map(len, words), default=1)
    n = len(run)
    # best[j] = (unknown characters, pieces, start, piece is outside the list)
    best: list[tuple[int, int, int, bool] | None] = [None] * (n + 1)
    best[0] = (0, 0, 0, False)
    for i in range(n):
        if best[i] is None or run[i] in DEPENDENT:
            continue
        unk, cnt = best[i][:2]
        cands = [(j, 0) for j in range(min(n, i + maxw), i, -1) if run[i:j] in words]
        # a lone consonant outside the list counts 3: คาก is not คา + ก
        cands += [(_after_silent(run, j), _after_silent(run, j) - i + 2 * (syls[0].kind == "a"))
                  for j, syls, _ in syllables_at(run, i)] or [(i + 1, 1)]
        for j, u in cands:
            if j < n and run[j] in DEPENDENT:
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
        lone = unknown and j == i + 1 and run[i] in CLASS
        if cuts and unknown and (cuts[-1][2] or lone):  # อ + รัส: read together (leading)
            cuts[-1] = (i, cuts[-1][1], True)
        else:
            cuts.append((i, j, unknown))
        j = i
    return [run[i:j] for i, j, _ in reversed(cuts)]


def run_syllables(run: str) -> list[Syllable]:
    """Syllables of a run of Thai letters (ๆ repeats the word before it)."""
    out: list[Syllable] = []
    last: list[Syllable] = []
    for k, piece in enumerate(run.split(REPEAT)):
        if k > 0:
            out.extend(last)
        if piece:
            for word in segment(piece):
                if out and out[-1].coda == "ฐ":  # รัฐ + another word: rat-tha (รัฐสภา)
                    out.append(Syllable(("th",), "H", "a", short=True, kind="a"))
                last = word_syllables(word)
                out.extend(last)
    return out


def thai_syllable_tokens(run: str) -> list[list[str]]:
    """Tokens per syllable of a run of Thai letters."""
    return [s.tokens() for s in run_syllables(run)]


def is_thai(ch: str) -> bool:
    """Thai letters and signs (U+0E01..U+0E4E; not the digits or ฿)."""
    return "ก" <= ch <= "๎" and ch != "฿"


def unreadable_th(text: str) -> list[str]:
    """Letters the Thai front-end cannot read (other scripts than Thai and Latin), to filter
    training sentences."""
    import unicodedata

    out = []
    for ch in text:
        if not ch.isalpha() or is_thai(ch) or ch.isascii():
            continue
        base = unicodedata.normalize("NFKD", ch)[:1]
        if not (base.isascii() and base.isalpha()):
            out.append(ch)
    return out
