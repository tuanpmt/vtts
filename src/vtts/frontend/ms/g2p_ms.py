"""Malay word -> ms-en tokens: the Indonesian spelling rules with Malay letters and tables.

Malaysian Malay spelling (Ejaan Rumi Baharu) and Indonesian spelling were unified in 1972, so the
rules are those of id/g2p_id.py, shared in code (rule_phonemes, respell, fold, valid_spelling):
digraphs, final k and the apostrophe as the glottal stop, the two e's, final diphthongs and
penultimate stress moving off the schwa. Malay differs in:

- the digraphs gh (ghaib, loghat), dh (Ramadhan, fardhu) and th (Mahathir, Uthman: Arabic
  loanwords and names) are one sound each, and v stays v (universiti, televisyen) where
  Indonesian reads f; th is not part of the spelling check (English the, think stay English),
  so a Malay word with th needs an entry in lexicons/ms/native.txt;
- the e table: lexicons/ms/overrides.tsv (Malay words and loanwords, e.g. nénék, téksi, béza) is
  looked up first, then the Indonesian lexicons/id/overrides.tsv for the words both languages share
  (méja, keréta, mérah); an entry equal to its key cancels the Indonesian one;
- ngg is ng + g (tinggi, mangga, Inggeris), and the e of ke-/se- before a vowel is the schwa
  (seorang, keadaan); the Indonesian rules read ngg as ng and that e as e;
- final a is read a, as in the standard reading (Bahasa Baku), not reduced to the schwa of
  colloquial Peninsular speech;
- Malay function words (UNSTRESSED adds daripada, kepada).

valid_spelling() says whether a plain ASCII word could be Malay (latin.py uses it to tell Malay
from English words).
"""

from __future__ import annotations

import functools

from ..id import g2p_id
from ..id.g2p_id import VOWELS, fold, respell, rule_phonemes
from ..lexicons import load_table

DIGRAPH_SOUNDS = (*g2p_id.DIGRAPH_SOUNDS, "gh", "dh", "th", "sh", "ch")
LETTER_SOUNDS = {"q": "k", "sh": "sy", "ch": "c"}
UNSTRESSED = g2p_id.UNSTRESSED | {"daripada", "kepada"}
DIGRAPHS = (*g2p_id.DIGRAPHS, ("gh", "G"), ("dh", "D"))


@functools.cache
def override_table() -> dict[str, str]:
    """Malay entries over the shared Indonesian ones."""
    return {**load_table("id", "overrides"), **load_table("ms", "overrides")}


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('besar' -> b @ s a1 r), without the MS: prefix."""
    w, explicit = respell(fold(word), override_table())
    return rule_phonemes(fold(w), explicit, DIGRAPH_SOUNDS, LETTER_SOUNDS, UNSTRESSED, malay=True)


def word_tokens_ms(word: str) -> list[str]:
    """ms-en tokens of one word; a word without a vowel (km, dll) is spelled letter by letter."""
    w = fold(word)
    if w and not any(ch in VOWELS for ch in w):
        from .normalize_ms import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for t in word_tokens_ms(NAMES[ch])]
    return [f"MS:{p}" for p in phonemes(word)]


def valid_spelling(w: str) -> bool:
    """The Indonesian spelling check with gh and dh as one letter (ghaib, Ramadhan)."""
    return g2p_id.valid_spelling(w, DIGRAPHS)


def unreadable_ms(text: str) -> list[str]:
    """Letters the Malay front-end cannot read (other scripts), to filter training sentences."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
