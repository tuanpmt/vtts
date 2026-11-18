"""Token set es-en and Spanish spelling-to-phoneme rules (es/g2p_es.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.es.g2p_es import phonemes, unreadable_es, valid_spelling, word_tokens_es
from vtts.frontend.lexicons import load_table


def test_token_set_esen_extends_v2():
    assert ps.TOKENS_ESEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_ESEN[107:]
    assert all(t.startswith("ES:") for t in block)
    assert len(block) == len(set(block)) == 31 and ps.VOCAB_SIZE_ESEN == 138
    assert ps.TOKEN_SETS[ps.TOKEN_SET_ESEN] is ps.TOKENS_ESEN and ps.TOKEN_SET_ESEN == "es-en"
    assert ps.PAIR_MODES["es"] == "es-en"
    idx = ps.token_index("es-en")
    assert idx["ES:a"] == 107 and idx["ES:a1"] == 112 and idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_ESEN[107:]}
    text = ("casa cielo zapato perro rosa chico llave yo muy hoy niño queso guitarra pingüino "
            "gente jamón examen xilófono ciudad cuidado bueno canción árbol reloj vino fútbol "
            "whisky kilo")
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w


@pytest.mark.parametrize("word, ph", [
    # consonants
    ("casa", "k a1 s a"), ("cielo", "th j e1 l o"), ("zapato", "th a p a1 t o"),
    ("acción", "a k th j o1 n"), ("chico", "ch i1 k o"), ("queso", "k e1 s o"),
    ("kilo", "k i1 l o"), ("gente", "x e1 n t e"), ("jamón", "x a m o1 n"),
    ("guitarra", "g i t a1 rr a"), ("pingüino", "p i n g w i1 n o"), ("gato", "g a1 t o"),
    ("hola", "o1 l a"), ("llave", "ll a1 b e"), ("niño", "n i1 ny o"), ("vino", "b i1 n o"),
    ("examen", "e k s a1 m e n"), ("xilófono", "s i l o1 f o n o"),
    # r and rr
    ("perro", "p e1 rr o"), ("caro", "k a1 r o"), ("rosa", "rr o1 s a"),
    ("honrado", "o n rr a1 d o"), ("alrededor", "a l rr e d e d o1 r"),
    # y: consonant before a vowel, else the vowel i
    ("yo", "y o1"), ("mayo", "m a1 y o"), ("hoy", "o1 j"), ("rey", "rr e1 j"), ("y", "i"),
    # diphthongs and hiatus
    ("ciudad", "th j u d a1 d"), ("cuidado", "k w i d a1 d o"), ("muy", "m w i1"),
    ("bueno", "b w e1 n o"), ("aire", "a1 j r e"), ("país", "p a i1 s"), ("día", "d i1 a"),
    ("poeta", "p o e1 t a"), ("reír", "rr e i1 r"), ("huevo", "w e1 b o"),
    # stress: written accent, else penultimate after a vowel, n or s, else last
    ("canción", "k a n th j o1 n"), ("árbol", "a1 r b o l"), ("reloj", "rr e l o1 x"),
    ("madrid", "m a d r i1 d"), ("cantan", "k a1 n t a n"), ("lunes", "l u1 n e s"),
    ("fútbol", "f u1 t b o l"), ("sol", "s o1 l"),
    # unstressed function words
    ("el", "e l"), ("pero", "p e r o"), ("de", "d e"), ("que", "k e"), ("qué", "k e1"),
    # other Latin letters folded
    ("françois", "f r a1 n s o j s"), ("ørsted", "o r s t e1 d"),
])
def test_phonemes(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_overrides():
    assert load_table("es", "overrides")["méxico"] == "méjico"
    assert " ".join(phonemes("méxico")) == "m e1 x i k o"
    assert " ".join(phonemes("ok")) == "o k e1 j"
    for key, reading in load_table("es", "overrides").items():
        assert phonemes(reading), key


def test_word_without_vowel_is_spelled():
    assert word_tokens_es("pst") == word_tokens_es("pe") + word_tokens_es("ese") + word_tokens_es("té")
    assert word_tokens_es("casa") == ["ES:k", "ES:a1", "ES:s", "ES:a"]


@pytest.mark.parametrize("word", ["casa", "perro", "cooperar", "examen", "estacion", "tren",
                                  "deshacer", "psicologia", "instituto", "construir", "abstracto",
                                  "septiembre", "transporte", "perspectiva", "paraguay", "texto",
                                  "adquirir", "atleta", "llave", "chocolate", "kilo"])
def test_valid_spanish_spelling(word):
    assert valid_spelling(word)


@pytest.mark.parametrize("word", ["smart", "weekend", "facebook", "bluetooth", "spotify",
                                  "streaming", "check", "playlist", "download", "shopping",
                                  "laptop", "tablet", "modem", "web", "think", "apple", "iraq",
                                  "coffee", "street", "school", "google's", "x"])
def test_english_looking_spelling(word):
    assert not valid_spelling(word)


def test_unreadable():
    assert unreadable_es("Hola, ¿qué tal? François, Ørsted 123") == []
    assert unreadable_es("Москва и 東京") == list("Москваи東京")
