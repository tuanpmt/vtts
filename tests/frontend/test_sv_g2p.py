import random

import pytest

from vtts.frontend.phoneme_set import TOKENS_SVEN, VOCAB_SIZE_SVEN
from vtts.frontend.sv.g2p_sv import phonemes, valid_spelling, word_tokens_sv


def ph(word):
    return " ".join(phonemes(word))


@pytest.mark.parametrize("word, out", [
    # complementary length, tones
    ("bil", "b i: '1 l"), ("bilen", "b i: '1 l @ n"), ("gata", "g A: '2 t a"), ("vatten", "v a '1 t @ n"),
    ("flicka", "f l I '2 k a"), ("flickan", "f l I '2 k a n"), ("hus", "h }: '1 s"), ("huset", "h }: '1 s @ t"),
    # sj-ljud, tj-ljud, soft k g sk
    ("sjuk", "S }: '1 k"), ("stjärna", "S {: '2 n` a"), ("kyrka", "C Y '2 r k a"), ("tjugo", "C }: '2 g U"),
    ("göra", "j 9: '2 r a"), ("skicka", "S I '2 k a"), ("ljus", "j }: '1 s"), ("hjärta", "j { '2 t` a"),
    # retroflex consonants
    ("bord", "b u: '1 d`"), ("kort", "k O '1 t`"), ("barn", "b A: '1 n`"), ("fors", "f O '1 s`"),
    ("första", "f 9 '2 s` t` a"),
    # g after l r, -ig, ng gn
    ("älg", "E '1 l j"), ("rolig", "r u: '2 l I"), ("roligt", "r u: '2 l I t"), ("regn", "r e '1 N n"),
    # stressed endings, prefixes, secondary stress
    ("station", "s t a S u: '1 n"), ("musik", "m 8 s i: '1 k"), ("studera", "s t 8 d e: '2 r a"),
    ("politiker", "p O l i: '2 t I k @ r"), ("förstå", "f 9 s` t` o: '1"), ("betala", "b @ t A: '1 l a"),
    ("frihet", "f r i: '2 h e , t"), ("kärlek", "C {: '2 l` e , k"),
    # number words: morph by morph, tone of the last morph
    ("tjugotvå", "C }: g U t v o: '1"), ("tvåtusentjugosex", "t v o: t }: s @ n C }: g U s e '1 k s"),
    # function words and overrides
    ("och", "O k"), ("på", "p o:"), ("jag", "j A:"),
])
def test_phonemes(word, out):
    assert ph(word) == out


def test_word_tokens_and_spelling():
    assert word_tokens_sv("Bil") == ["SV:b", "SV:i:", "SV:'1", "SV:l"]
    assert word_tokens_sv("km") == word_tokens_sv("kå") + word_tokens_sv("em")


@pytest.mark.parametrize("word, ok", [
    ("hus", True), ("flicka", True), ("cykel", True), ("lindqvist", True), ("myndigheter", True),
    ("lutherska", True), ("show", False), ("weekend", False), ("light", False), ("shop", False),
    ("thriller", False), ("software", False),
])
def test_valid_spelling(word, ok):
    assert valid_spelling(word) == ok


def test_random_words_stay_in_the_token_set():
    names = set(TOKENS_SVEN[107:])
    letters = "abcdefghijklmnopqrstuvwxyzåäöé'"
    rng = random.Random(0)
    for _ in range(3000):
        w = "".join(rng.choice(letters) for _ in range(rng.randint(1, 12)))
        assert set(word_tokens_sv(w)) <= names, w
    assert VOCAB_SIZE_SVEN == 155
