"""Token set fi-en and Finnish spelling-to-phoneme rules (fi/g2p_fi.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.fi.g2p_fi import (
    number_parts,
    override_table,
    phonemes,
    unreadable_fi,
    valid_spelling,
    word_tokens_fi,
)


def p(word):
    return " ".join(phonemes(word))


def test_token_set_layout():
    toks = ps.TOKENS_FIEN
    assert toks[:ps.VOCAB_SIZE_V2] == ps.TOKENS_V2
    assert toks[107] == "FI:a" and len(toks) == ps.VOCAB_SIZE_FIEN == 142
    assert len(set(toks)) == len(toks)
    assert ps.PAIR_MODES["fi"] == "fi-en" and ps.TOKEN_SETS["fi-en"] == toks


@pytest.mark.parametrize("word, out", [
    ("talo", "t a1 l o"),
    ("saari", "s a1 : r i"),
    ("kukka", "k u1 k : a"),
    ("tuuli", "t u1 : l i"),
    ("kenkä", "k e1 ng k ae"),
    ("kengät", "k e1 ng : ae t"),
    ("Helsinki", "h e1 l s i ng k i"),
    ("yö", "y1 oe"),
    ("öljy", "oe1 l j y"),
    ("tyttö", "t y1 t : oe"),
    ("kansanpuolue", "k a1 n s a m p u o l u e"),
    ("hengityshäiriö", "h e1 ng : i t y s h ae i r i oe"),
    ("zeta", "t s e1 t a"),
    ("pizza", "p i1 t : s a"),
    ("taxi", "t a1 k s i"),
    ("cirkus", "s i1 r k u s"),
    ("show", "sh o1 u"),
    ("shakki", "sh a1 k : i"),
    ("Åbo", "o1 b o"),
    ("ja", "j a"),
])
def test_word_phonemes(word, out):
    assert p(word) == out


def test_number_words_have_stress_on_each_part():
    assert number_parts("kaksisataakolme") == ["kaksi", "sataa", "kolme"]
    assert number_parts("toista") is None and number_parts("kuusikko") is None
    assert p("kaksikymmentä") == "k a1 k s i k y1 m : e n t ae"
    assert number_parts("kahdestakymmenestä") == ["kahdesta", "kymmenestä"]


def test_tokens_and_vowelless_words():
    toks = word_tokens_fi("kissa")
    assert toks == ["FI:k", "FI:i1", "FI:s", "FI::", "FI:a"]
    assert all(t in ps.TOKENS_FIEN for t in toks)
    assert word_tokens_fi("km") == word_tokens_fi("koo") + word_tokens_fi("äm")


def test_overrides_differ_from_rules():
    for key, value in override_table().items():
        assert key != value


@pytest.mark.parametrize("word, ok", [
    ("talo", True), ("kissa", True), ("presidentti", True), ("stadion", True), ("helsinki", True),
    ("yliopisto", True), ("kokonaishinta", True),
    ("weekend", False), ("smart", False), ("play", False), ("boy", False), ("facebook", False),
    ("ping", False), ("today", False), ("bluetooth", False), ("show", False),
])
def test_valid_spelling(word, ok):
    assert valid_spelling(word) == ok


def test_unreadable():
    assert unreadable_fi("Hei Москва") and not unreadable_fi("Hyvää päivää, François ja Zürich")
