"""Versioned, spelling-based token inventory shared by teacher, student and C runtime.

Token ids are the index in TOKENS. Changing the order or contents requires a
new PHONEME_SET_VERSION.

Prefixes: O: onset, G: on-glide, N: nucleus, C: coda, T1..T6 tones in the order
ngang, huyền, sắc, hỏi, ngã, nặng. The set is dialect-neutral: spellings that
merge in Hanoi speech (tr/ch, s/x, r/d/gi) stay distinct tokens.
"""

PHONEME_SET_VERSION = "1"

PAD, BOS, EOS, SPACE = "<pad>", "<bos>", "<eos>", " "
PUNCTUATION = (",", ".", "?", "!", ";", ":")

ONSETS = ("b", "k", "ch", "d", "đ", "g", "gi", "h", "kh", "l", "m", "n", "ng", "nh",
          "p", "ph", "r", "s", "t", "th", "tr", "v", "x")
NUCLEI = ("a", "ă", "â", "e", "ê", "i", "o", "ô", "ơ", "u", "ư", "iê", "uô", "ươ", "oo")
CODAS = ("c", "ch", "m", "n", "ng", "nh", "p", "t", "j", "w")
TONE_COUNT = 6

TOKENS: tuple[str, ...] = (
    (PAD, BOS, EOS, SPACE)
    + PUNCTUATION
    + tuple(f"O:{o}" for o in ONSETS)
    + ("G:w",)
    + tuple(f"N:{n}" for n in NUCLEI)
    + tuple(f"C:{c}" for c in CODAS)
    + tuple(f"T{i}" for i in range(1, TONE_COUNT + 1))
)
VOCAB_SIZE = len(TOKENS)

_TOKEN_TO_ID = {tok: i for i, tok in enumerate(TOKENS)}


def token_to_id(tok: str) -> int:
    return _TOKEN_TO_ID[tok]


def id_to_token(i: int) -> str:
    return TOKENS[i]


# ---------------- version 2: Vietnamese + English (ids 0..64 unchanged) ----------------
# English uses the 39 ARPAbet phonemes (CMUdict); a stress token S0/S1/S2 follows each vowel,
# the way a tone token follows each Vietnamese syllable.

PHONEME_SET_VERSION_V2 = "2"
ARPABET = ("AA", "AE", "AH", "AO", "AW", "AY", "B", "CH", "D", "DH", "EH", "ER", "EY", "F", "G",
           "HH", "IH", "IY", "JH", "K", "L", "M", "N", "NG", "OW", "OY", "P", "R", "S", "SH", "T",
           "TH", "UH", "UW", "V", "W", "Y", "Z", "ZH")
ARPABET_VOWELS = frozenset(("AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY",
                            "OW", "OY", "UH", "UW"))
STRESS = ("S0", "S1", "S2")

TOKENS_V2: tuple[str, ...] = TOKENS + tuple(f"EN:{p}" for p in ARPABET) + STRESS
VOCAB_SIZE_V2 = len(TOKENS_V2)

_TOKEN_TO_ID_V2 = {tok: i for i, tok in enumerate(TOKENS_V2)}


def token_to_id_v2(tok: str) -> int:
    return _TOKEN_TO_ID_V2[tok]


# ---------------- token set "zh-en": Mandarin + English (ids 0..106 = v2 unchanged) ----------------
# A model uses only the ids of its pair; the Vietnamese rows (8..64) stay unused by zh-en models
# so that the English rows (65..106) can be warm-started from a vi-en teacher. Mandarin syllables
# are [ZI:initial] ZF:final ZTtone; finals are written in full (iou, uei, uen; v for u-umlaut),
# "ii" is the apical vowel after zh/ch/sh/r and "i0" after z/c/s. Tone 5 is the neutral tone.

TOKEN_SET_V2 = "vi-en"
TOKEN_SET_ZHEN = "zh-en"

ZH_INITIALS = ("b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "j", "q", "x",
               "zh", "ch", "sh", "r", "z", "c", "s")
ZH_FINALS = ("a", "o", "e", "ai", "ei", "ao", "ou", "an", "en", "ang", "eng", "ong", "er",
             "i", "ia", "ie", "iao", "iou", "ian", "in", "iang", "ing", "iong",
             "u", "ua", "uo", "uai", "uei", "uan", "uen", "uang", "ueng",
             "v", "ve", "van", "vn", "ii", "i0")
ZH_TONE_COUNT = 5

TOKENS_ZHEN: tuple[str, ...] = (
    TOKENS_V2
    + tuple(f"ZI:{i}" for i in ZH_INITIALS)
    + tuple(f"ZF:{f}" for f in ZH_FINALS)
    + tuple(f"ZT{i}" for i in range(1, ZH_TONE_COUNT + 1))
)
VOCAB_SIZE_ZHEN = len(TOKENS_ZHEN)

TOKEN_SETS: dict[str, tuple[str, ...]] = {TOKEN_SET_V2: TOKENS_V2, TOKEN_SET_ZHEN: TOKENS_ZHEN}

_TOKEN_TO_ID_ZHEN = {tok: i for i, tok in enumerate(TOKENS_ZHEN)}


def token_to_id_zhen(tok: str) -> int:
    return _TOKEN_TO_ID_ZHEN[tok]
