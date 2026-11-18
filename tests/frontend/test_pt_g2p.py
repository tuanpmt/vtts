"""Token set pt-en and Brazilian Portuguese spelling-to-phoneme rules (pt/g2p_pt.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.lexicons import load_table
from vtts.frontend.pt.g2p_pt import phonemes, unreadable_pt, valid_spelling, word_tokens_pt


def test_token_set_pten_extends_v2():
    assert ps.TOKENS_PTEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_PTEN[107:]
    assert all(t.startswith("PT:") for t in block)
    assert len(block) == len(set(block)) == 43 and ps.VOCAB_SIZE_PTEN == 150
    assert ps.TOKEN_SETS[ps.TOKEN_SET_PTEN] is ps.TOKENS_PTEN and ps.TOKEN_SET_PTEN == "pt-en"
    assert ps.PAIR_MODES["pt"] == "pt-en"
    idx = ps.token_index("pt-en")
    assert idx["PT:a"] == 107 and idx["PT:a1"] == 112 and idx["PT:an"] == 119 and idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_PTEN[107:]}
    text = ("casa carro canção mãe limões também falam ponte mundo muito chave filho banho gente "
            "guerra quando cinquenta exemplo caixa táxi luz janela papel sol avó ruim inglês "
            "jovem vida")
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w


@pytest.mark.parametrize("word, ph", [
    # consonants
    ("casa", "k a1 z a"), ("chave", "sh a1 v i"), ("filho", "f i1 lh u"), ("banho", "b a1 nh u"),
    ("gente", "zh en1 t i"), ("gato", "g a1 t u"), ("guerra", "g E1 rr a"), ("quero", "k E1 r u"),
    ("quando", "k w an d u"), ("qual", "k w a1 l"), ("cinquenta", "s in k w en1 t a"),
    ("nascer", "n a s e1 rr"), ("exceção", "e s e s an1 w"), ("luz", "l u1 s"),
    # r: tap between vowels, strong elsewhere
    ("caro", "k a1 r u"), ("carro", "k a1 rr u"), ("rio", "rr i1 u"), ("honra", "on1 rr a"),
    ("mar", "m a1 rr"), ("porta", "p O1 rr t a"), ("brasil", "b r a z i1 l"),
    # x
    ("xícara", "sh i1 k a r a"), ("exemplo", "e z en1 p l u"), ("texto", "t e1 s t u"),
    ("caixa", "k a1 j sh a"), ("lixo", "l i1 sh u"), ("táxi", "t a1 k s i"),
    # nasal vowels and nasal diphthongs
    ("canção", "k an s an1 w"), ("mão", "m an1 w"), ("mãe", "m an1 j"),
    ("limões", "l i m on1 j s"), ("bem", "b en1 j"), ("também", "t an b en1 j"),
    ("homens", "o1 m en j s"), ("falam", "f a1 l an w"), ("campo", "k an1 p u"),
    ("ponte", "p on1 t i"), ("mundo", "m un1 d u"), ("irmã", "i rr m an1"), ("ruim", "rr u in1"),
    # glides and hiatus
    ("pai", "p a1 j"), ("muito", "m u1 j t u"), ("partiu", "p a rr t i1 w"),
    ("ainda", "a in1 d a"), ("rainha", "rr a i1 nh a"), ("cair", "k a i1 rr"),
    ("raul", "rr a u1 l"), ("país", "p a i1 s"), ("dia", "d i1 a"), ("rua", "rr u1 a"),
    # stress and vowel quality
    ("café", "k a f E1"), ("avó", "a v O1"), ("você", "v o s e1"), ("pôr", "p o1 rr"),
    ("útil", "u1 t i l"), ("computador", "k on p u t a d o1 rr"), ("janela", "zh a n E1 l a"),
    ("papel", "p a p E1 l"), ("sol", "s O1 l"), ("famosa", "f a m O1 z a"),
    ("famoso", "f a m o1 z u"), ("órfão", "O1 rr f an w"),
    # final unstressed e/o -> i/u; function words
    ("leite", "l e1 j t i"), ("cidade", "s i d a1 d i"), ("de", "d i"), ("que", "k i"),
    ("o", "u"), ("os", "u s"), ("e", "i"),
])
def test_phonemes(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_overrides():
    table = load_table("pt", "overrides")
    assert table["ela"] == "éla" and " ".join(phonemes("ela")) == "E1 l a"
    assert " ".join(phonemes("hora")) == "O1 r a"
    assert " ".join(phonemes("próximo")) == "p r O1 s i m u"
    assert " ".join(phonemes("frequente")) == "f r e k w en1 t i"
    for key, reading in table.items():
        assert phonemes(reading), key


def test_word_without_vowel_is_spelled():
    assert word_tokens_pt("pq") == word_tokens_pt("pê") + word_tokens_pt("quê")


@pytest.mark.parametrize("word", ["casa", "carro", "chuva", "mulher", "trabalho", "exemplo",
                                  "texto", "bairro", "voo", "nascer", "advogado", "obstante",
                                  "psicologia", "atleta", "pneu", "quando"])
def test_valid_portuguese_spelling(word):
    assert valid_spelling(word)


@pytest.mark.parametrize("word", ["smart", "weekend", "facebook", "bluetooth", "spotify",
                                  "streaming", "check", "playlist", "download", "shopping",
                                  "party", "laptop", "chat", "show", "web", "coffee", "stop"])
def test_english_looking_spelling(word):
    assert not valid_spelling(word)


def test_unreadable():
    assert unreadable_pt("Olá, tudo bem? François, ação 123") == []
    assert unreadable_pt("São Paulo 東京") == list("東京")
