"""Swedish word -> sv-en tokens (Central Standard Swedish; rules of scand_g2p.py with the
Swedish tables below).

A word (lower case, after normalize_sv) is looked up in lexicons/sv/overrides.tsv (phonemes with
the tone tokens), else read by scand_g2p.word_phonemes: number words morph by morph, the unstressed
prefixes be- and för-, then the rules:

- sj skj stj sch ch -> S (sj-ljud), tj kj -> C (tj-ljud); at the start of a stem k -> C, g -> j and
  sk -> S before e i y ä ö; dj gj hj lj -> j at the start; ng -> N, gn -> N n, nk -> N k, ck -> k,
  x -> k s, z -> s, w -> v, qu -> k v, ph -> f, th -> t, dt -> t; -tion -sion -> S u: n.
- Vowels: long a: A:, e e:, i i:, o u:, u }:, y y:, å o:, ä E:, ö 2:; short a, e, I, O, 8, Y, O, E,
  9; ä ö before r: {: { and 9: 9. Complementary length: a stressed vowel is long before at most one
  consonant (and before rd rn rl), short before two; unstressed vowels are short; an unstressed e
  in an ending (-e -en -er -el -et ...) is the schwa @.
- -ig and -igt: the g is silent (rolig, roligt); g after l r at the end or before a front vowel is
  j (älg, berg, Norge).
- Stress on the first syllable, after be- and för-, or on a stressed foreign ending (-tion -ism
  -ist -ent -ant -era -eri -ik -ur -är -ör -ös -ell -iv -al -at -on -in -ett -itet -logi ...); the
  vowel before -isk -iker. Tones: see scand_g2p (accent 1 for a final stress and for two-syllable
  words in -el -er -en -et -em, else accent 2).

Tokens: SV:<phoneme>; the tone token SV:'1 / SV:'2 follows the stressed vowel, SV:, marks a
secondary stress (-het -dom -skap -lek -sam -bar after accent 2).
"""

from __future__ import annotations

import functools
import unicodedata

from ..lexicons import load_table, load_words
from ..scand_g2p import Rules, word_phonemes

LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzåäöé")
FOLD = {"æ": "ä", "ø": "ö", "ü": "y", "ß": "s", "ł": "l", "đ": "d", "þ": "t", "œ": "ö"}

NUMBER_MORPHS: dict[str, tuple[str, ...]] = {
    m: tuple(p.split()) for m, p in (
        ("noll", "n O '1 l"), ("ett", "E '1 t"), ("en", "e: '1 n"), ("två", "t v o: '1"),
        ("tre", "t r e: '1"), ("fyra", "f y: '2 r a"), ("fem", "f e '1 m"), ("sex", "s e '1 k s"),
        ("sju", "S }: '1"), ("åtta", "O '2 t a"), ("nio", "n i: '2 U"), ("tio", "t i: '2 U"),
        ("elva", "e '2 l v a"), ("tolv", "t O '1 l v"), ("tretton", "t r e '2 t O n"),
        ("fjorton", "f j u: '2 r t O n"), ("femton", "f e '2 m t O n"), ("sexton", "s e '2 k s t O n"),
        ("sjutton", "S 8 '2 t O n"), ("arton", "A: '2 r t O n"), ("nitton", "n I '2 t O n"),
        ("tjugo", "C }: '2 g U"), ("trettio", "t r e '2 t I U"), ("fyrtio", "f 9 '2 r t I U"),
        ("femtio", "f e '2 m t I U"), ("sextio", "s e '2 k s t I U"), ("sjuttio", "S 8 '2 t I U"),
        ("åttio", "O '2 t I U"), ("nittio", "n I '2 t I U"), ("hundra", "h 8 '2 n d r a"),
        ("tusen", "t }: '1 s @ n"),
        ("första", "f 9 '2 r s t a"), ("andra", "a '2 n d r a"), ("tredje", "t r e: '2 d j @"),
        ("fjärde", "f j {: '2 r d @"), ("femte", "f e '2 m t @"), ("sjätte", "S E '2 t @"),
        ("sjunde", "S 8 '2 n d @"), ("åttonde", "O '2 t O n d @"), ("nionde", "n i: '2 O n d @"),
        ("tionde", "t i: '2 O n d @"), ("elfte", "e '2 l f t @"), ("tolfte", "t O '2 l f t @"),
        ("hundrade", "h 8 '2 n d r a d @"), ("tusende", "t }: '2 s @ n d @"), ("de", "d @"),
        ("nde", "n d @"),
    )
}

RULES = Rules(
    code="sv",
    vowels="aeiouyåäöé",
    front=("e", "i", "y", "ä", "ö", "é"),
    front_c="eiyäöé",
    long={"a": "A:", "e": "e:", "i": "i:", "o": "u:", "u": "}:", "y": "y:", "å": "o:", "ä": "E:",
          "ö": "2:", "é": "e:"},
    short={"a": "a", "e": "e", "i": "I", "o": "O", "u": "8", "y": "Y", "å": "O", "ä": "E", "ö": "9",
           "é": "e"},
    before_r={"ä": ("{:", "{"), "ö": ("9:", "9"), "e": ("e:", "{")},
    before_r_coda="e",
    diphthongs=(),
    graphemes=(
        ("sch", ("S",)), ("skj", ("S",)), ("stj", ("S",)), ("ssi|on", ("S",)), ("ti|on", ("S",)),
        ("si|on", ("S",)), ("sj", ("S",)), ("tj", ("C",)),
        ("kj", ("C",)), ("ch", ("S",)), ("ck", ("k",)), ("ng", ("N",)), ("gn", ("N", "n")),
        ("nk", ("N", "k")), ("ph", ("f",)), ("th", ("t",)), ("qu", ("k", "v")), ("dt", ("t",)),
        ("x", ("k", "s")),
    ),
    initial=(("dj", ("j",)), ("gj", ("j",)), ("hj", ("j",)), ("lj", ("j",))),
    soft=(("sk", ("S",)), ("k", ("C",)), ("g", ("j",))),
    single={"b": "b", "d": "d", "f": "f", "g": "g", "h": "h", "j": "j", "k": "k", "l": "l", "m": "m",
            "n": "n", "p": "p", "q": "k", "r": "r", "s": "s", "t": "t", "v": "v", "w": "v", "z": "s"},
    prefixes=(("för", ("f", "9", "r")), ("be", ("b", "@"))),
    not_prefix=("berg", "bett", "beta", "bete", "bensin", "först", "första", "förste", "förr", "förra",
                "förut", "förare", "fören", "berlin", "bevis"),
    onsets=frozenset(("bl", "br", "dr", "dv", "fl", "fr", "gl", "gr", "kl", "kn", "kr", "kv", "pl", "pr",
                      "sk", "skr", "sl", "sm", "sn", "sp", "spl", "spr", "st", "str", "sv", "tr", "tv",
                      "vr", "sj", "skj", "stj", "tj", "kj", "dj", "gj", "hj", "lj", "gn", "fj", "nj", "pj",
                      "bj", "mj", "sch", "ch", "th", "ph")),
    stressed_endings=(("ssion", 3), ("tion", 2), ("sion", 2), ("ologi", 4), ("logi", 3), ("grafi", 4),
                      ("itet", 2), ("ism", 0), ("ist", 0), ("ent", 0), ("ant", 0), ("erade", 0),
                      ("erads", 0), ("erad", 0), ("erar", 0), ("erat", 0), ("era", 0), ("eri", 2), ("ik", 0), ("ur", 0), ("är", 0),
                      ("ör", 0), ("ös", 0), ("ell", 0), ("iv", 0), ("al", 0), ("at", 0), ("on", 0),
                      ("in", 0), ("ett", 0), ("ern", 0), ("é", 0), ("og", 0)),
    inflections=("en", "er", "et", "erna", "ens", "ets", "a", "e", "na", "n", "ar", "arna", "or",
                 "orna", "s", "t"),
    prestress=("iska", "iskt", "isk", "ikerna", "iker", "ikern"),
    acute_endings=("el", "er", "en", "et", "em"),
    secondary=("heten", "het", "domen", "dom", "skapen", "skap", "lek", "sam", "bar"),
    function_words=frozenset((
        "och", "att", "en", "ett", "i", "på", "av", "för", "med", "till", "som", "om", "men", "så",
        "det", "den", "de", "dem", "du", "jag", "han", "hon", "vi", "ni", "man", "sig", "mig", "dig",
        "sin", "sitt", "sina", "är", "var", "har", "kan", "ska", "vill", "har", "hade", "från", "vid",
        "hos", "mot", "där", "när", "då", "ju", "nu", "här", "hur", "vad", "vem", "eller", "utan",
    )),
    schwa_endings=("e", "en", "er", "el", "et", "es", "em", "ens", "ets", "ers", "els", "erna", "ena",
                   "ende", "else", "elser", "ade", "ande", "ad", "ats"),
    number_morphs=NUMBER_MORPHS,
    silent=("ig", "igt"),
    unstressed={"o": "U"},
    final_g_j=True,
)


@functools.cache
def override_table() -> dict[str, tuple[str, ...]]:
    return {k: tuple(v.split()) for k, v in load_table("sv", "overrides").items()}


def fold(word: str) -> str:
    """Lower case, Swedish letters kept, æ ø ü read as ä ö y, other accented letters reduced to
    their base letter, anything else dropped."""
    out = []
    for ch in word.lower():
        if ch in LETTERS:
            out.append(ch)
            continue
        base = FOLD.get(ch) or (unicodedata.normalize("NFKD", ch) or " ")[0]
        if base in LETTERS:
            out.append(base)
    return "".join(out)


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word with the tone tokens ('bilen' -> b i: '1 l @ n)."""
    return word_phonemes(fold(word), RULES, override_table())


def word_tokens_sv(word: str) -> list[str]:
    """sv-en tokens of one word; a word without a vowel (km, st) is spelled letter by letter."""
    w = fold(word)
    if w and not any(ch in RULES.vowels for ch in w) and w not in override_table():
        from .normalize_sv import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for t in word_tokens_sv(NAMES[ch])]
    return [f"SV:{p}" for p in phonemes(word)]


# ---------------- spelling check (Swedish or English?) ----------------

FOREIGN = ("sh", "ch", "ph", "wh", "ou", "ay", "ey", "oy", "aw", "ew", "ow", "ght", "dge", "tch", "w",
           "q")
FOREIGN_START = ("th",)
FOREIGN_END = ("igh",)


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Swedish spelling: none of the English letter groups of
    FOREIGN (sh ch ph wh ou ay ey oy aw ew ow ght dge tch, w q; qv of names is Swedish: Lindqvist), no
    th at the start or igh at the end (inside a word they are a morph boundary: myndigheter,
    lutherska), c only in ck or before e i y (cykel, centrum), and not in lexicons/sv/english.txt."""
    if not w or not w.isascii() or not w.isalpha() or w in load_words("sv", "english"):
        return False
    if any(f in w.replace("qv", "kv") for f in FOREIGN) or w.startswith(FOREIGN_START) or w.endswith(FOREIGN_END):
        return False
    return all(ch != "c" or w[k + 1:k + 2] in ("k", "e", "i", "y") for k, ch in enumerate(w))


def unreadable_sv(text: str) -> list[str]:
    """Letters the Swedish front-end cannot read (other scripts), to filter training sentences."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
