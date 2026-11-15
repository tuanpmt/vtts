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
