import random

import pytest

from vtts.frontend.no.g2p_no import phonemes, valid_spelling, word_tokens_no
from vtts.frontend.phoneme_set import TOKENS_NOEN, VOCAB_SIZE_NOEN


def ph(word):
    return " ".join(phonemes(word))


@pytest.mark.parametrize("word, out", [
    # complementary length, tonem 1 and 2
    ("bil", "b i: '1 l"), ("bilen", "b i: '1 l @ n"), ("biler", "b i: '2 l @ r"), ("hus", "h }: '1 s"),
    ("sykkel", "s Y '1 k @ l"), ("hjelpe", "j E '2 l p @"),
    # kj-lyd, sj-lyd, soft k g sk, hv
    ("kjøre", "C 2: '2 r @"), ("kirke", "C I '2 r k @"), ("skjære", "S {: '2 r @"), ("sjø", "S 2: '1"),
    ("gi", "j i: '1"), ("hvem", "v E m"),
    # silent letters
    ("god", "g u: '1"), ("land", "l A '1 n"), ("gård", "g o: '1 r"), ("holde", "h O '2 l @"),
    ("viktig", "v I '2 k t I"), ("huset", "h }: '1 s @"), ("rundt", "r } '1 n t"),
    # retroflex consonants, e before r
    ("barn", "b A: '1 n`"), ("kort", "k O '1 t`"), ("norsk", "n O '1 s` k"), ("første", "f 9 '2 s` t` @"),
    ("verden", "v {: '1 d` @ n"), ("studere", "s t } d e: '2 r @"),
    # diphthongs, stressed endings, prefixes, secondary stress
    ("nei", "n {I '1"), ("øy", "9Y '1"), ("stasjon", "s t A S u: '1 n"), ("musikk", "m } s I '1 k"),
    ("forstå", "f O s` t` o: '1"), ("betale", "b E t A: '1 l @"), ("frihet", "f r i: '2 h E , t"),
    # number words
    ("tjueen", "C }: @ e: '1 n"),
    # function words and overrides
    ("og", "O"), ("jeg", "j {I"), ("ikke", "I '2 k @"),
])
def test_phonemes(word, out):
    assert ph(word) == out


def test_word_tokens_and_spelling():
    assert word_tokens_no("Bil") == ["NO:b", "NO:i:", "NO:'1", "NO:l"]
    assert word_tokens_no("km") == word_tokens_no("kå") + word_tokens_no("em")


@pytest.mark.parametrize("word, ok", [
    ("hus", True), ("akershus", True), ("opphav", True), ("fotoutstilling", True), ("show", False),
    ("weekend", False), ("light", False), ("thriller", False), ("software", False), ("check", False),
])
def test_valid_spelling(word, ok):
    assert valid_spelling(word) == ok


def test_random_words_stay_in_the_token_set():
    names = set(TOKENS_NOEN[107:])
    letters = "abcdefghijklmnopqrstuvwxyzæøåé'"
    rng = random.Random(0)
    for _ in range(3000):
        w = "".join(rng.choice(letters) for _ in range(rng.randint(1, 12)))
        assert set(word_tokens_no(w)) <= names, w
    assert VOCAB_SIZE_NOEN == 156


@pytest.mark.parametrize("lang", ["sv", "no"])
def test_tables_use_tokens_of_the_set(lang):
    import importlib

    from vtts.frontend.phoneme_set import token_index

    g = importlib.import_module(f"vtts.frontend.{lang}.g2p_{lang}")
    index = token_index(f"{lang}-en")
    for word, ph in list(g.override_table().items()) + list(g.NUMBER_MORPHS.items()):
        assert all(f"{lang.upper()}:{p}" in index for p in ph), word
