"""Token set tl-en and Tagalog spelling-to-phoneme rules (tl/g2p_tl.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.lexicons import load_table
from vtts.frontend.tl.g2p_tl import (
    _pattern,
    fold,
    phonemes,
    unreadable_tl,
    valid_spelling,
    word_tokens_tl,
)


def test_token_set_tlen_extends_v2():
    assert ps.TOKENS_TLEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_TLEN[107:]
    assert all(t.startswith("TL:") for t in block)
    assert len(block) == len(set(block)) == 32 and ps.VOCAB_SIZE_TLEN == 139
    assert ps.TOKEN_SETS[ps.TOKEN_SET_TLEN] is ps.TOKENS_TLEN and ps.TOKEN_SET_TLEN == "tl-en"
    assert ps.PAIR_MODES["tl"] == "tl-en"
    idx = ps.token_index("tl-en")
    assert idx["TL:a"] == 107 and idx["TL:a1"] == 112 and idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_TLEN[107:]}
    text = ("salamat bata hindi ng mga tao kumain mag'aral tsinelas cebu quezon niño villa "
            "pamilya fiesta zoo jeep shampoo dalawampu't ako'y xerox")
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w


@pytest.mark.parametrize("word, ph", [
    # default stress: second-to-last syllable
    ("salamat", "s a l a1 m a t"), ("bahay", "b a1 h a y"), ("tubig", "t u1 b i g"),
    # the particles ng and mga
    ("ng", "n a ng"), ("mga", "m a ng a"), ("sa", "s a"), ("ang", "a ng"),
    # glottal stops: between vowels, after a hyphen (written ' by the normalizer)
    ("tao", "t a1 ? o"), ("saan", "s a ? a1 n"), ("maaari", "m a ? a ? a1 r i ?"),
    ("mag'aral", "m a g ? a1 r a l"), ("pag-asa", "p a g ? a1 s a"),
    # table: mabilis, malumi, maragsa
    ("ako", "a k o1"), ("bata", "b a1 t a ?"), ("hindi", "h i n d i1 ?"), ("wala", "w a l a1 ?"),
    # accent marks in the text
    ("batà", "b a1 t a ?"), ("ákin", "a1 k i n"), ("walâ", "w a l a1 ?"), ("gandá", "g a n d a1"),
    # affixed forms keep the root's stress; the linker -ng and 't/'y add no syllable
    ("maganda", "m a g a n d a1"), ("kumain", "k u m a1 ? i n"), ("isang", "i s a1 ng"),
    ("limang", "l i m a1 ng"), ("dalawampu't", "d a l a w a m p u1 t"), ("ako'y", "a k o1 y"),
    ("kagandahan", "k a g a n d a h a1 n"), ("napakaganda", "n a p a k a g a n d a1"),
    # loanword letters
    ("tsinelas", "ch i n e1 l a s"), ("cebu", "s e1 b u"), ("quezon", "k e1 z o n"),
    ("niño", "n i1 n y o"), ("villa", "v i1 l y a"), ("xerox", "k s e1 r o k s"),
])
def test_phonemes(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_stress_table():
    respelled = 0
    for key, reading in load_table("tl", "stress").items():
        assert key == key.lower() and key.isascii() and phonemes(key), key
        same_letters = "".join(c for c in fold(reading) if c.isascii()) == key
        respelled += not same_letters
        # an entry with the same letters changes the default, or (no marks) only stops the root lookup
        assert not same_letters or _pattern(fold(reading)) != (None, False) or reading == key, key
    assert respelled <= 10  # letters are changed only for a few Spanish names
    assert " ".join(phonemes("jose")) == "h o s e1"


def test_word_without_vowel_is_spelled():
    assert word_tokens_tl("km") == word_tokens_tl("key") + word_tokens_tl("em")
    assert word_tokens_tl("ng") == ["TL:n", "TL:a", "TL:ng"]


@pytest.mark.parametrize("word", ["salamat", "pilipinas", "maganda", "kumain", "maaari", "pamilya",
                                  "siyudad", "kuwento", "dyip", "trabaho", "eskuwela", "ngayon",
                                  "tsismis", "plano", "pag-asa"])
def test_valid_tagalog_spelling(word):
    assert valid_spelling(word)


@pytest.mark.parametrize("word", ["smart", "weekend", "facebook", "bluetooth", "spotify", "check",
                                  "playlist", "download", "shopping", "party", "happy", "router",
                                  "computer", "jazz", "feedback", "coffee"])
def test_english_looking_spelling(word):
    assert not valid_spelling(word)


def test_unreadable():
    assert unreadable_tl("Kumusta? Niño, Café, mag-aral 123") == []
    assert unreadable_tl("Maynila 東京") == list("東京")
