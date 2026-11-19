import random

import pytest

from vtts.frontend.nl.g2p_nl import phonemes, valid_spelling, word_tokens_nl
from vtts.frontend.phoneme_set import TOKENS_NLEN, VOCAB_SIZE_NLEN


def ph(word):
    return " ".join(phonemes(word))


@pytest.mark.parametrize("word, out", [
    # vowel length: open and closed syllables, digraphs
    ("maken", "m a:1 k @ n"), ("kat", "k A1 t"), ("katten", "k A1 t @ n"), ("bomen", "b o:1 m @ n"),
    ("boom", "b o:1 m"), ("zebra", "z e:1 b r a:"), ("lachen", "l A1 x @ n"),
    # diphthongs and the other digraphs
    ("huis", "h 9y1 s"), ("tijd", "t Ei1 t"), ("vrouw", "v r Au1"), ("nieuw", "n i1 w"),
    ("leeuw", "l e:1 w"), ("reus", "r 2:1 s"), ("boek", "b u1 k"), ("muur", "m y1 r"),
    # schwa, -ig, -lijk, final devoicing, ch/g, sch, ng/nk, sj
    ("prettig", "p r E1 t @ x"), ("lelijk", "l e:1 l @ k"), ("hond", "h O1 n t"),
    ("dag", "d A1 x"), ("schip", "s x I1 p"), ("bank", "b A1 N k"), ("koning", "k o:1 n I N"),
    ("meisje", "m Ei1 S @"), ("historisch", "h I s t o:1 r i s"),
    # unstressed prefixes
    ("begin", "b @ x I1 n"), ("gebouw", "x @ b Au1"), ("vereniging", "v @ r e:1 n i x I N"),
    ("ontvangen", "O n t v A1 N @ n"), ("geven", "x e:1 v @ n"), ("beter", "b e:1 t @ r"),
    # stressed endings
    ("student", "s t y d E1 n t"), ("universiteit", "y n i v E r s i t Ei1 t"), ("muziek", "m y z i1 k"),
    ("partij", "p A r t Ei1"), ("informatie", "I n f O r m a:1 t s i"), ("functie", "f Y1 N k s i"),
    ("studeert", "s t y d e:1 r t"), ("telefoon", "t e: l @ f o:1 n"), ("idee", "i d e:1"),
    # number words: morph by morph, stress on the first
    ("eenentwintig", "e:1 n @ n t w I n t @ x"), ("zesentwintig", "z E1 s @ n t w I n t @ x"),
    ("tweeëntwintig", "t w e:1 @ n t w I n t @ x"), ("één", "e:1 n"),
    # function words and overrides
    ("de", "d @"), ("een", "@ n"), ("het", "h @ t"), ("station", "s t a: S O1 n"),
])
def test_phonemes(word, out):
    assert ph(word) == out


def test_word_tokens_and_spelling():
    assert word_tokens_nl("Kat") == ["NL:k", "NL:A1", "NL:t"]
    assert word_tokens_nl("km") == word_tokens_nl("ka") + word_tokens_nl("em")
    assert word_tokens_nl("'s") == ["NL:s"]
    assert word_tokens_nl("café") == ["NL:k", "NL:a:", "NL:f", "NL:e:1"]


@pytest.mark.parametrize("word, ok", [
    ("huis", True), ("vrouw", True), ("staatshoofd", True), ("opheffing", True), ("vaardigheid", True),
    ("grondgebied", True), ("schip", True), ("show", False), ("check", False), ("weekday", False),
    ("light", False), ("bridge", False), ("software", False), ("shirt", False),
])
def test_valid_spelling(word, ok):
    assert valid_spelling(word) == ok


def test_random_words_stay_in_the_token_set():
    names = set(TOKENS_NLEN[107:])
    letters = "abcdefghijklmnopqrstuvwxyzéëïöüèáóúíàêç'"
    rng = random.Random(0)
    for _ in range(3000):
        w = "".join(rng.choice(letters) for _ in range(rng.randint(1, 12)))
        assert set(word_tokens_nl(w)) <= names, w
    assert VOCAB_SIZE_NLEN == 159
