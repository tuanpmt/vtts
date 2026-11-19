"""Token set sw-en and Swahili spelling-to-phoneme rules (sw/g2p_sw.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.lexicons import load_table
from vtts.frontend.sw.g2p_sw import phonemes, unreadable_sw, valid_spelling, word_tokens_sw


def test_token_set_swen_extends_v2():
    assert ps.TOKENS_SWEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_SWEN[107:]
    assert all(t.startswith("SW:") for t in block)
    assert len(block) == len(set(block)) == 40 and ps.VOCAB_SIZE_SWEN == 147
    assert ps.TOKEN_SETS[ps.TOKEN_SET_SWEN] is ps.TOKENS_SWEN and ps.TOKEN_SET_SWEN == "sw-en"
    assert ps.PAIR_MODES["sw"] == "sw-en"
    idx = ps.token_index("sw-en")
    assert idx["SW:a"] == 107 and idx["SW:a1"] == 112 and idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_SWEN[107:]}
    text = ("kitabu mtoto nchi ng'ombe ngoma nyumba mbuzi njia nzuri mvua mwalimu thelathini "
            "dhahabu ghali khabari chakula shule kaa mzee kiatu sifuri jambo vijana fedha zawadi "
            "xerox quran")
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w


@pytest.mark.parametrize("word, ph", [
    # penultimate stress, every vowel a syllable
    ("kitabu", "k i t a1 b u"), ("barabara", "b a r a b a1 r a"), ("kiatu", "k i a1 t u"),
    ("kaa", "k a1 a"), ("mzee", "m z e1 e"),
    # digraphs and the velar nasal
    ("chakula", "ch a k u1 l a"), ("shule", "sh u1 l e"), ("nyumba", "ny u1 mb a"),
    ("ng'ombe", "ng o1 mb e"), ("ng’ombe", "ng o1 mb e"), ("thelathini", "th e l a th i1 n i"),
    ("dhahabu", "dh a h a1 b u"), ("ghali", "gh a1 l i"), ("khabari", "kh a b a1 r i"),
    # prenasalized stops
    ("mbuzi", "mb u1 z i"), ("ndege", "nd e1 g e"), ("ngoma", "ngg o1 m a"), ("njia", "nj i1 a"),
    ("nzuri", "n z u1 r i"),
    # syllabic nasals count as syllables
    ("mtoto", "m t o1 t o"), ("mtu", "m t u"), ("nchi", "n ch i"), ("nne", "n n e"),
    ("mmea", "m m e1 a"), ("mvua", "m v u1 a"), ("mwalimu", "m w a l i1 m u"),
    # function words, the stress table, loanword letters
    ("na", "n a"), ("kwa", "k w a"), ("lazima", "l a1 z i m a"), ("allah", "a1 l a h"),
])
def test_phonemes(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_stress_table():
    for key in load_table("sw", "stress"):
        assert key == key.lower() and key.isascii() and phonemes(key), key
        vowels = [p for p in phonemes(key) if p[0] in "aeiou"]
        assert any(v.endswith("1") for v in vowels) and not vowels[-2].endswith("1"), key


def test_word_without_vowel_is_spelled():
    assert word_tokens_sw("km") == word_tokens_sw("kei") + word_tokens_sw("em")


@pytest.mark.parametrize("word", ["kitabu", "mtoto", "nchi", "ng'ombe", "mwalimu", "nyumba",
                                  "barabara", "kiswahili", "ndege", "mzee", "nne", "kwanza",
                                  "shule", "thelathini", "watoto", "tanzania"])
def test_valid_swahili_spelling(word):
    assert valid_spelling(word)


@pytest.mark.parametrize("word", ["smart", "weekend", "facebook", "bluetooth", "spotify", "check",
                                  "playlist", "download", "shopping", "party", "router", "single",
                                  "google", "style", "jazz", "email"])
def test_english_looking_spelling(word):
    assert not valid_spelling(word)


def test_unreadable():
    assert unreadable_sw("Habari? Café, ng'ombe 123") == []
    assert unreadable_sw("Nairobi 東京") == list("東京")
