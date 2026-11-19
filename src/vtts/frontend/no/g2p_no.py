"""Norwegian (Bokmål, Urban East Norwegian pronunciation) word -> no-en tokens (rules of
scand_g2p.py with the Norwegian tables below).

A word (lower case, after normalize_no) is looked up in lexicons/no/overrides.tsv (phonemes with
the tone tokens), else read by scand_g2p.word_phonemes: number words morph by morph, the unstressed
prefixes be- and for-, then the rules:

- skj sj sch -> S, kj tj -> C; at the start of a stem k -> C, g -> j and sk -> S before i y ei øy;
  gj hj dj lj -> j and hv -> v at the start; ng -> N, gn -> N n, nk -> N k, ck -> k, x -> k s,
  z -> s, w -> v, qu -> k v, ph -> f, th -> t; c is s before e i y, else k.
- Vowels: long a A:, e e:, i i:, o u:, u }:, y y:, æ {:, ø 2:, å o:; short A E I O } Y { 9 O;
  e before r: {: {; the diphthongs ei {I, øy 9Y, au {}, ai Ai. Complementary length as in Swedish;
  an unstressed e in an ending (-e -en -er -el -et -ene ...) is the schwa @; unstressed o is U.
- Silent letters: a final d after a vowel, l, n or r (god, tid, land, kald, gård, ord), d after l n
  before a final -e -er -en -et (holde, landet); the g of -ig and -ige (viktig, hyggelig); the t of
  an unstressed final -et (huset -> h }: '1 s @).
- Stress on the first syllable, after be- and for-, or on a stressed foreign ending (-sjon -isme
  -ist -ent -ant -ere -eri -ikk -ur -ør -øs -ell -iv -al -at -on -in -itet -logi ...); the vowel
  before -isk -iker. Tones: tonem 1 for a final stress and for two-syllable words in -el -en -et,
  else tonem 2 (plurals in -er have tonem 2).

Tokens: NO:<phoneme>; the tone token NO:'1 / NO:'2 follows the stressed vowel, NO:, marks a
secondary stress (-het -dom -skap -else -sam -bar after tonem 2).
"""

from __future__ import annotations

import functools
import unicodedata

from ..lexicons import load_table, load_words
from ..scand_g2p import Rules, word_phonemes

LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzæøåéèòôó")
FOLD = {"ä": "æ", "ö": "ø", "ü": "y", "ß": "s", "ł": "l", "đ": "d", "þ": "t", "œ": "ø"}

NUMBER_MORPHS: dict[str, tuple[str, ...]] = {
    m: tuple(p.split()) for m, p in (
        ("null", "n } '1 l"), ("en", "e: '1 n"), ("ett", "E '1 t"), ("to", "t u: '1"),
        ("tre", "t r e: '1"), ("fire", "f i: '2 r @"), ("fem", "f E '1 m"), ("seks", "s E '1 k s"),
        ("sju", "S }: '1"), ("syv", "s y: '1 v"), ("åtte", "O '2 t @"), ("ni", "n i: '1"),
        ("ti", "t i: '1"), ("elleve", "E '2 l v @"), ("tolv", "t O '1 l"), ("tretten", "t r E '2 t @ n"),
        ("fjorten", "f j U '2 r t @ n"), ("femten", "f E '2 m t @ n"), ("seksten", "s {I '2 s t @ n"),
        ("sytten", "s Y '2 t @ n"), ("atten", "A '2 t @ n"), ("nitten", "n I '2 t @ n"),
        ("tjue", "C }: '2 @"), ("tretti", "t r E '2 t I"), ("førti", "f 9 '2 r t I"),
        ("femti", "f E '2 m t I"), ("seksti", "s E '2 k s t I"), ("sytti", "s Y '2 t I"),
        ("åtti", "O '2 t I"), ("nitti", "n I '2 t I"), ("hundre", "h } '2 n d r @"),
        ("tusen", "t }: '1 s @ n"),
        ("første", "f 9 '2 r s t @"), ("andre", "A '2 n d r @"), ("tredje", "t r e: '2 d j @"),
        ("fjerde", "f j {: '2 r @"), ("femte", "f E '2 m t @"), ("sjette", "S E '2 t @"),
        ("sjuende", "S }: '2 @ n @"), ("syvende", "s y: '2 v @ n @"), ("åttende", "O '2 t @ n @"),
        ("niende", "n i: '2 @ n @"), ("tiende", "t i: '2 @ n @"), ("ellevte", "E '2 l f t @"),
        ("tolvte", "t O '2 l t @"), ("hundrede", "h } '2 n d r @ d @"), ("tusende", "t }: '2 s @ n @"),
        ("ende", "@ n @"), ("nde", "n @"), ("de", "@"),
    )
}

RULES = Rules(
    code="no",
    vowels="aeiouyæøåéèòôó",
    front=("i", "y", "ei", "øy"),
    front_c="eiyæø",
    long={"a": "A:", "e": "e:", "i": "i:", "o": "u:", "u": "}:", "y": "y:", "æ": "{:", "ø": "2:",
          "å": "o:", "é": "e:", "è": "{:", "ò": "o:", "ô": "o:", "ó": "u:"},
    short={"a": "A", "e": "E", "i": "I", "o": "O", "u": "}", "y": "Y", "æ": "{", "ø": "9", "å": "O",
           "é": "E", "è": "{", "ò": "O", "ô": "O", "ó": "O"},
    before_r={"e": ("{:", "{")},
    before_r_coda="e",
    diphthongs=(("ei", "{I"), ("øy", "9Y"), ("au", "{}"), ("ai", "Ai")),
    graphemes=(
        ("sch", ("S",)), ("skj", ("S",)), ("sj", ("S",)), ("kj", ("C",)), ("tj", ("C",)),
        ("ch", ("S",)), ("ck", ("k",)), ("ng", ("N",)), ("gn", ("N", "n")), ("nk", ("N", "k")),
        ("ph", ("f",)), ("th", ("t",)), ("qu", ("k", "v")), ("dt", ("t",)), ("x", ("k", "s")),
    ),
    initial=(("hv", ("v",)), ("gj", ("j",)), ("hj", ("j",)), ("dj", ("j",)), ("lj", ("j",))),
    soft=(("sk", ("S",)), ("k", ("C",)), ("g", ("j",))),
    single={"b": "b", "d": "d", "f": "f", "g": "g", "h": "h", "j": "j", "k": "k", "l": "l", "m": "m",
            "n": "n", "p": "p", "q": "k", "r": "r", "s": "s", "t": "t", "v": "v", "w": "v", "z": "s"},
    prefixes=(("for", ("f", "O", "r")), ("be", ("b", "E"))),
    not_prefix=("berg", "bet", "bete", "bensin", "fort", "form", "forum", "forsk", "forhold", "forbi",
                "fordi", "forrige", "fors", "forte", "berlin", "beste", "bedre", "bevis"),
    onsets=frozenset(("bl", "br", "dr", "dv", "fl", "fr", "gl", "gr", "kl", "kn", "kr", "kv", "pl", "pr",
                      "sk", "skr", "sl", "sm", "sn", "sp", "spl", "spr", "st", "str", "sv", "tr", "tv",
                      "vr", "sj", "skj", "tj", "kj", "dj", "gj", "hj", "lj", "hv", "gn", "fj", "nj", "pj",
                      "bj", "mj", "sch", "ch", "th", "ph")),
    stressed_endings=(("sjon", 2), ("ologi", 4), ("logi", 3), ("grafi", 4), ("itet", 2), ("isme", 0),
                      ("ist", 0), ("ent", 0), ("ant", 0), ("erte", 0), ("erer", 0), ("ert", 0),
                      ("ere", 0), ("eri", 2), ("ikk", 0), ("ur", 0), ("ør", 0), ("øs", 0), ("ell", 0),
                      ("iv", 0), ("al", 0), ("at", 0), ("on", 0), ("in", 0), ("ett", 0), ("é", 0),
                      ("og", 0), ("anse", 0), ("ense", 0)),
    inflections=("en", "er", "et", "ene", "ens", "ets", "e", "a", "n", "s", "t"),
    prestress=("iske", "isk", "ikere", "ikerne", "iker", "ikeren"),
    acute_endings=("el", "en", "et"),
    secondary=("heten", "het", "dommen", "dom", "skapen", "skap", "else", "sam", "bar"),
    function_words=frozenset((
        "og", "å", "i", "på", "av", "for", "med", "til", "som", "om", "men", "så", "det", "den", "de",
        "dem", "du", "jeg", "han", "hun", "vi", "dere", "man", "seg", "meg", "deg", "sin", "sitt", "sine",
        "er", "var", "har", "kan", "skal", "vil", "en", "et", "ei", "at", "fra", "ved", "hos", "mot",
        "da", "når", "der", "her", "hvor", "hva", "hvem", "eller", "uten", "nå",
    )),
    schwa_endings=("e", "en", "er", "el", "et", "es", "em", "ene", "ens", "ets", "ers", "els", "ende",
                   "else", "elser", "ere", "erne", "elig", "elige"),
    number_morphs=NUMBER_MORPHS,
    silent=("d", "ig", "ige", "et"),
    unstressed={"o": "U"},
    final_g_j=False,
)


@functools.cache
def override_table() -> dict[str, tuple[str, ...]]:
    return {k: tuple(v.split()) for k, v in load_table("no", "overrides").items()}


def fold(word: str) -> str:
    """Lower case, Norwegian letters kept, ä ö ü read as æ ø y, other accented letters reduced to
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


def word_tokens_no(word: str) -> list[str]:
    """no-en tokens of one word; a word without a vowel (km, st) is spelled letter by letter."""
    w = fold(word)
    if w and not any(ch in RULES.vowels for ch in w) and w not in override_table():
        from .normalize_no import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for t in word_tokens_no(NAMES[ch])]
    return [f"NO:{p}" for p in phonemes(word)]


# ---------------- spelling check (Norwegian or English?) ----------------

FOREIGN = ("ch", "wh", "ay", "ey", "oy", "aw", "ew", "ow", "ght", "dge", "tch", "ck", "w", "q")
FOREIGN_START = ("sh", "ph", "th")
FOREIGN_END = ("sh", "ph", "igh")


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Norwegian spelling: none of the English letter groups
    of FOREIGN (ch wh ay ey oy aw ew ow ght dge tch ck, w q), no sh ph th at the start or sh ph igh
    at the end (inside a word they are a morph boundary: Akershus, opphav), c only before e i y,
    and not in lexicons/no/english.txt."""
    if not w or not w.isascii() or not w.isalpha() or w in load_words("no", "english"):
        return False
    if any(f in w for f in FOREIGN) or w.startswith(FOREIGN_START) or w.endswith(FOREIGN_END):
        return False
    return all(ch != "c" or w[k + 1:k + 2] in ("e", "i", "y") for k, ch in enumerate(w))


def unreadable_no(text: str) -> list[str]:
    """Letters the Norwegian front-end cannot read (other scripts), to filter training sentences."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
