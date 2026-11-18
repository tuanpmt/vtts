"""Korean word -> surface syllables (standard pronunciation rules, 표준 발음법) -> ko-en tokens.

A word (어절, Hangul only) is first rewritten by the exception table lexicons/ko/overrides.tsv
(forward longest match; readings are spelled as pronounced), then decomposed into
(onset, vowel, coda) jamo and rewritten by RULES, an ordered table of rules over each pair of
adjacent syllables, applied left to right one rule at a time. Rules never cross a space.

Order: palatalization, coda ㅎ, aspiration before onset ㅎ, liaison, tensification, coda
neutralization (7 codas; double codas simplified), ㄹ -> ㄴ after ㅁ ㅇ ㄱ ㄷ ㅂ, nasalization,
liquidization; then the vowel rules of one syllable (ㅢ after a consonant -> ㅣ, 져 쪄 쳐 -> 저 쩌 처).
Known gaps (use overrides.tsv): ㄴ insertion, 사잇소리, Sino-Korean ㄹ + ㄷㅅㅈ tensification,
tensification after the ㄹ of the future adnominal (할 수, 할게) and rules across words.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from ..lexicons import load_table
from .hangul import compose, decompose, is_hangul_syllable

Syl = list[str]  # [onset, vowel, coda]; onset ㅇ = silent, coda "" = none

ONSET_NAMES = {"ㄱ": "g", "ㄲ": "kk", "ㅋ": "k", "ㄷ": "d", "ㄸ": "tt", "ㅌ": "t", "ㅂ": "b",
               "ㅃ": "pp", "ㅍ": "p", "ㅅ": "s", "ㅆ": "ss", "ㅈ": "j", "ㅉ": "jj", "ㅊ": "ch",
               "ㅎ": "h", "ㄴ": "n", "ㅁ": "m", "ㄹ": "r"}
VOWEL_NAMES = {"ㅏ": "a", "ㅐ": "ae", "ㅑ": "ya", "ㅒ": "yae", "ㅓ": "eo", "ㅔ": "e", "ㅕ": "yeo",
               "ㅖ": "ye", "ㅗ": "o", "ㅘ": "wa", "ㅙ": "wae", "ㅚ": "oe", "ㅛ": "yo", "ㅜ": "u",
               "ㅝ": "wo", "ㅞ": "we", "ㅟ": "wi", "ㅠ": "yu", "ㅡ": "eu", "ㅢ": "ui", "ㅣ": "i"}
CODA_NAMES = {"ㄱ": "k", "ㄴ": "n", "ㄷ": "t", "ㄹ": "l", "ㅁ": "m", "ㅂ": "p", "ㅇ": "ng"}

# Coda -> one of the 7 coda sounds (ㄺ before ㄱ is handled in _neutralize).
NEUTRAL = {"ㄱ": "ㄱ", "ㄲ": "ㄱ", "ㅋ": "ㄱ", "ㄳ": "ㄱ", "ㄺ": "ㄱ",
           "ㄴ": "ㄴ", "ㄵ": "ㄴ", "ㄶ": "ㄴ",
           "ㄷ": "ㄷ", "ㅅ": "ㄷ", "ㅆ": "ㄷ", "ㅈ": "ㄷ", "ㅊ": "ㄷ", "ㅌ": "ㄷ", "ㅎ": "ㄷ",
           "ㄹ": "ㄹ", "ㄼ": "ㄹ", "ㄽ": "ㄹ", "ㄾ": "ㄹ", "ㅀ": "ㄹ",
           "ㅁ": "ㅁ", "ㄻ": "ㅁ",
           "ㅂ": "ㅂ", "ㅍ": "ㅂ", "ㅄ": "ㅂ", "ㄿ": "ㅂ",
           "ㅇ": "ㅇ", "": ""}
# Liaison: coda -> (part that stays, part that moves to the empty onset). The ㅅ of ㄳ ㄽ ㅄ is tense.
LIAISON = {"ㄳ": ("ㄱ", "ㅆ"), "ㄵ": ("ㄴ", "ㅈ"), "ㄺ": ("ㄹ", "ㄱ"), "ㄻ": ("ㄹ", "ㅁ"),
           "ㄼ": ("ㄹ", "ㅂ"), "ㄽ": ("ㄹ", "ㅆ"), "ㄾ": ("ㄹ", "ㅌ"), "ㄿ": ("ㄹ", "ㅍ"),
           "ㅄ": ("ㅂ", "ㅆ")}
# Coda before onset ㅎ -> (part that stays, aspirated onset).
ASPIRATE_BEFORE_H = {"ㄱ": ("", "ㅋ"), "ㄲ": ("", "ㅋ"), "ㅋ": ("", "ㅋ"), "ㄳ": ("", "ㅋ"),
                     "ㄺ": ("ㄹ", "ㅋ"), "ㄷ": ("", "ㅌ"), "ㅅ": ("", "ㅌ"), "ㅆ": ("", "ㅌ"),
                     "ㅊ": ("", "ㅌ"), "ㅌ": ("", "ㅌ"), "ㅈ": ("", "ㅊ"), "ㄵ": ("ㄴ", "ㅊ"),
                     "ㅂ": ("", "ㅍ"), "ㅍ": ("", "ㅍ"), "ㅄ": ("", "ㅍ"), "ㄼ": ("ㄹ", "ㅍ")}
ASPIRATED = {"ㄱ": "ㅋ", "ㄷ": "ㅌ", "ㅈ": "ㅊ"}
H_CODAS = {"ㅎ": "", "ㄶ": "ㄴ", "ㅀ": "ㄹ"}  # coda with ㅎ -> what is left without it
TENSE = {"ㄱ": "ㄲ", "ㄷ": "ㄸ", "ㅂ": "ㅃ", "ㅅ": "ㅆ", "ㅈ": "ㅉ"}
# Codas after which a lax onset is tensified: obstruents (rule 23) and the verb-stem double
# codas ㄵ ㄻ (rule 24, not before the causative/passive 기) and ㄼ ㄾ (rule 25).
OBSTRUENT_CODAS = frozenset("ㄱㄲㅋㄳㄺㄷㅅㅆㅈㅊㅌㅂㅍㅄㄿ")
STEM_CODAS = frozenset("ㄵㄻㄼㄾ")
Y_TO_PLAIN = {"ㅑ": "ㅏ", "ㅒ": "ㅐ", "ㅕ": "ㅓ", "ㅖ": "ㅔ", "ㅛ": "ㅗ", "ㅠ": "ㅜ"}


def _palatalize(a: Syl, b: Syl) -> None:
    """Rule 17: ㄷ ㅌ (ㄾ) + 이 -> 지 치 (굳이 [구지], 같이 [가치]); ㄷ + 히 -> 치 (닫히다 [다치다])."""
    if b[1] not in ("ㅣ", "ㅕ"):
        return
    if b[0] == "ㅇ" and a[2] in ("ㄷ", "ㅌ", "ㄾ"):
        a[2], b[0] = {"ㄷ": ("", "ㅈ"), "ㅌ": ("", "ㅊ"), "ㄾ": ("ㄹ", "ㅊ")}[a[2]]
    elif b[0] == "ㅎ" and a[2] == "ㄷ":
        a[2], b[0] = "", "ㅊ"


def _coda_h(a: Syl, b: Syl) -> None:
    """Rule 12: coda ㅎ (ㄶ ㅀ) aspirates ㄱ ㄷ ㅈ (좋다 [조타]), tenses ㅅ (닿소 [다쏘]), is ㄴ
    before ㄴ (놓는 [논는]) and is silent before a vowel (좋아 [조아])."""
    rest = H_CODAS.get(a[2])
    if rest is None:
        return
    if b[0] in ASPIRATED:
        a[2], b[0] = rest, ASPIRATED[b[0]]
    elif b[0] == "ㅅ":
        a[2], b[0] = rest, "ㅆ"
    elif b[0] == "ㄴ":
        a[2] = rest or "ㄴ"
    elif b[0] == "ㅇ":
        a[2] = rest


def _aspirate(a: Syl, b: Syl) -> None:
    """Rule 12: ㄱ ㄷ ㅂ ㅈ (and codas read so) + ㅎ -> ㅋ ㅌ ㅍ ㅊ (축하 [추카], 입학 [이팍])."""
    if b[0] == "ㅎ" and a[2] in ASPIRATE_BEFORE_H:
        a[2], b[0] = ASPIRATE_BEFORE_H[a[2]]


def _liaison(a: Syl, b: Syl) -> None:
    """Rules 13-14: a coda moves to a following empty onset (한국어 [한구거], 앉아 [안자])."""
    if b[0] == "ㅇ" and a[2] not in ("", "ㅇ"):
        a[2], b[0] = LIAISON.get(a[2], ("", a[2]))


def _tensify(a: Syl, b: Syl) -> None:
    """Rules 23-25: lax onset after an obstruent coda is tense (학교 [학꾜], 앉고 [안꼬])."""
    if b[0] not in TENSE:
        return
    if a[2] in OBSTRUENT_CODAS or (a[2] in STEM_CODAS and not (a[2] in "ㄵㄻ" and b[:2] == ["ㄱ", "ㅣ"])):
        b[0] = TENSE[b[0]]


def _neutralize(a: Syl, b: Syl | None) -> None:
    """Rules 9-11: codas are read as one of ㄱ ㄴ ㄷ ㄹ ㅁ ㅂ ㅇ; ㄺ is ㄹ before ㄱ (읽고 [일꼬])."""
    if a[2] == "ㄺ" and b is not None and b[0] in ("ㄱ", "ㄲ"):
        a[2] = "ㄹ"
    else:
        a[2] = NEUTRAL[a[2]]


def _l_to_n(a: Syl, b: Syl) -> None:
    """Rule 19: onset ㄹ after ㅁ ㅇ ㄱ ㄷ ㅂ is ㄴ (종로 [종노], 독립 [동닙] with rule 18)."""
    if b[0] == "ㄹ" and a[2] in ("ㅁ", "ㅇ", "ㄱ", "ㄷ", "ㅂ"):
        b[0] = "ㄴ"


def _nasalize(a: Syl, b: Syl) -> None:
    """Rule 18: ㄱ ㄷ ㅂ before ㄴ ㅁ are ㅇ ㄴ ㅁ (국물 [궁물], 십만 [심만])."""
    if b[0] in ("ㄴ", "ㅁ") and a[2] in ("ㄱ", "ㄷ", "ㅂ"):
        a[2] = {"ㄱ": "ㅇ", "ㄷ": "ㄴ", "ㅂ": "ㅁ"}[a[2]]


def _liquidize(a: Syl, b: Syl) -> None:
    """Rule 20: ㄴ next to ㄹ is ㄹ (신라 [실라], 칼날 [칼랄])."""
    if (a[2], b[0]) in (("ㄴ", "ㄹ"), ("ㄹ", "ㄴ")):
        a[2], b[0] = "ㄹ", "ㄹ"


def _vowels(s: Syl) -> None:
    """Rule 5: ㅢ after a consonant is ㅣ (희망 [히망]); 져 쪄 쳐 are 저 쩌 처."""
    if s[1] == "ㅢ" and s[0] != "ㅇ":
        s[1] = "ㅣ"
    elif s[0] in ("ㅈ", "ㅉ", "ㅊ") and s[1] in Y_TO_PLAIN:
        s[1] = Y_TO_PLAIN[s[1]]


RULES: list[tuple[str, Callable[[Syl, Syl], None]]] = [
    ("palatalization", _palatalize),
    ("coda_h", _coda_h),
    ("aspiration", _aspirate),
    ("liaison", _liaison),
    ("tensification", _tensify),
    ("neutralization", _neutralize),
    ("l_to_n", _l_to_n),
    ("nasalization", _nasalize),
    ("liquidization", _liquidize),
]


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("ko", "overrides")


def apply_overrides(word: str, table: dict[str, str] | None = None) -> str:
    """Replace exception entries in a word, forward longest match ('물고기를' -> '물꼬기를')."""
    table = override_table() if table is None else table
    if not table:
        return word
    longest = max(map(len, table))
    out, i = [], 0
    while i < len(word):
        for n in range(min(longest, len(word) - i), 0, -1):
            if (r := table.get(word[i:i + n])) is not None:
                out.append(r)
                i += n
                break
        else:
            out.append(word[i])
            i += 1
    return "".join(out)


def _apply_rules(syls: list[Syl]) -> None:
    for name, rule in RULES:
        for i in range(len(syls)):
            nxt = syls[i + 1] if i + 1 < len(syls) else None
            if nxt is not None or name == "neutralization":  # the last coda is neutralized too
                rule(syls[i], nxt)
    for s in syls:
        _vowels(s)


@functools.lru_cache(maxsize=8192)
def pronounce(word: str) -> tuple[tuple[str, str, str], ...]:
    """Surface (onset, vowel, coda) per syllable of a word; characters that are not Hangul
    syllables are skipped and split the word into parts that do not interact."""
    out: list[tuple[str, str, str]] = []
    run: list[Syl] = []
    for ch in apply_overrides(word) + " ":
        if is_hangul_syllable(ch):
            run.append(list(decompose(ch)))
        elif run:
            _apply_rules(run)
            out.extend((s[0], s[1], s[2]) for s in run)
            run = []
    return tuple(out)


def pronounce_text(text: str) -> str:
    """Space-separated words spelled as pronounced ('국물 좋아' -> '궁물 조아'), for tests/docs."""
    return " ".join("".join(compose(*s) for s in pronounce(w)) for w in text.split())


def syllable_tokens(syl: tuple[str, str, str]) -> list[str]:
    on, vo, co = syl
    out = [] if on == "ㅇ" else [f"KO:I:{ONSET_NAMES[on]}"]
    out.append(f"KO:V:{VOWEL_NAMES[vo]}")
    if co:
        out.append(f"KO:C:{CODA_NAMES[co]}")
    return out


def word_tokens_ko(word: str) -> list[str]:
    """ko-en tokens of one Korean word ('학교' -> KO:I:h KO:V:a KO:C:k KO:I:kk KO:V:yo)."""
    return [t for s in pronounce(word) for t in syllable_tokens(s)]


def unreadable_ko(text: str) -> list[str]:
    """Letters the Korean front-end skips (Hanja, bare jamo, other scripts), to filter training
    sentences; Hangul syllables, ASCII and punctuation are readable."""
    return [ch for ch in text if ch.isalpha() and not ch.isascii() and not is_hangul_syllable(ch)]
