"""Token set it-en and Italian spelling-to-phoneme rules (it/g2p_it.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.it.g2p_it import (
    _read,
    fold,
    phonemes,
    unreadable_it,
    valid_spelling,
    word_tokens_it,
)
from vtts.frontend.lexicons import load_table


def test_token_set_iten_extends_v2():
    assert ps.TOKENS_ITEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_ITEN[107:]
    assert all(t.startswith("IT:") for t in block)
    assert len(block) == len(set(block)) == 35 and ps.VOCAB_SIZE_ITEN == 142
    assert ps.TOKEN_SETS[ps.TOKEN_SET_ITEN] is ps.TOKENS_ITEN and ps.TOKEN_SET_ITEN == "it-en"
    assert ps.PAIR_MODES["it"] == "it-en"
    idx = ps.token_index("it-en")
    assert idx["IT:a"] == 107 and idx["IT:a1"] == 112 and idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_ITEN[107:]}
    text = ("casa cielo gioco chiesa ghiro figlio gnocchi scena schiena pizza zero azione città "
            "perché però buono piede guida quando acqua xilofono jazz kiwi yogurt whisky l'acqua "
            "c'è sbaglio")
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w


@pytest.mark.parametrize("word, ph", [
    # c, g, sc, gl, gn, qu, h
    ("casa", "k a1 z a"), ("cena", "ch e1 n a"), ("ciao", "ch a1 o"), ("chiesa", "k j E1 z a"),
    ("gioco", "dj o1 k o"), ("gelato", "dj e l a1 t o"), ("ghiro", "g i1 r o"),
    ("scena", "sh e1 n a"), ("sciarpa", "sh a1 r p a"), ("pesce", "p e1 sh sh e"), ("schiena", "s k j E1 n a"),
    ("figlio", "f i1 ly ly o"), ("gli", "ly i"), ("gnocchi", "ny o1 k k i"),
    ("quando", "k w a1 n d o"), ("acqua", "a1 k k w a"), ("hotel", "o t e1 l"),
    # s and z
    ("rosa", "r o1 z a"), ("sbaglio", "z b a1 ly ly o"), ("sole", "s o1 l e"),
    ("rosso", "r o1 s s o"), ("zero", "dz e1 r o"), ("pizza", "p i1 ts ts a"),
    ("azione", "a ts ts j o1 n e"), ("organizzare", "o r g a n i dz dz a1 r e"),
    # gemination
    ("fatto", "f a1 t t o"), ("mamma", "m a1 m m a"),
    ("faccia", "f a1 ch ch a"), ("oggi", "O1 dj dj i"),
    # glides and hiatus
    ("piano", "p j a1 n o"), ("buono", "b w O1 n o"), ("piede", "p j E1 d e"),
    ("guida", "g w i1 d a"), ("aiuto", "a j u1 t o"), ("mio", "m i1 o"), ("due", "d u1 e"),
    ("mai", "m a1 j"), ("più", "p j u1"),
    # stress: accents, default, suffixes, overrides
    ("città", "ch i t t a1"), ("perché", "p e r k e1"), ("però", "p e r O1"),
    ("è", "E1"), ("e", "e"), ("sport", "s p o1 r t"),
    ("possibile", "p o s s i1 b i l e"), ("bellissimo", "b e l l i1 s s i m o"),
    ("politico", "p o l i1 t i k o"), ("telefono", "t e l E1 f o n o"),
    ("piccolo", "p i1 k k o l o"), ("immagine", "i m m a1 dj i n e"), ("essere", "E1 s s e r e"),
    ("avere", "a v e1 r e"), ("prendono", "p r E1 n d o n o"), ("parlavano", "p a r l a1 v a n o"),
    ("galleria", "g a l l e r i1 a"), ("geografia", "dj e o g r a f i1 a"),
    ("amico", "a m i1 k o"), ("numero", "n u1 m e r o"), ("ventitré", "v e n t i t r e1"),
    ("ventisei", "v e n t i s E1 j"),
    # open/closed e and o
    ("medico", "m E1 d i k o"), ("presidente", "p r e z i d E1 n t e"),
    ("velocemente", "v e l o ch e m e1 n t e"), ("territorio", "t e r r i t O1 r j o"),
    ("famoso", "f a m o1 z o"), ("quello", "k w e1 l l o"),
    # elision and unstressed words
    ("l'acqua", "l a1 k k w a"), ("c'è", "ch E1"), ("dell'anno", "d e l l a1 n n o"),
    ("dell'epoca", "d e l l E1 p o k a"), ("l'unico", "l u1 n i k o"),
    ("della", "d e l l a"), ("il", "i l"),
])
def test_word(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_word_tokens_prefix_spelling_and_elision_mark():
    assert word_tokens_it("casa") == ["IT:k", "IT:a1", "IT:z", "IT:a"]
    assert word_tokens_it("km") == word_tokens_it("cappa") + word_tokens_it("emme")
    assert word_tokens_it("sullʼ") == ["IT:s", "IT:u", "IT:l", "IT:l"]  # unstressed
    assert word_tokens_it("lʼ") == ["IT:l"]
    assert word_tokens_it("poʼ") == ["IT:p", "IT:o1"]


def test_fold_and_unreadable():
    assert fold("Città") == "città" and fold("Ñandú") == "nandú" and fold("Straße") == "strase"
    assert unreadable_it("Москва") and not unreadable_it("Perché François è qui?")


def test_overrides_differ_from_rules():
    table = load_table("it", "overrides")
    assert len(table) > 100
    for key, respelling in table.items():
        assert key == key.lower() and " " not in respelling
        assert tuple(_read(key)) != phonemes(key), key


@pytest.mark.parametrize("word, ok", [
    ("casa", True), ("strada", True), ("scuola", True), ("gnocchi", True), ("figlio", True),
    ("acqua", True), ("per", True), ("il", True), ("squadra", True), ("croazia", True),
    ("weekend", False), ("smart", False), ("the", False), ("facebook", False),
    ("check", False), ("shop", False), ("night", False),
])
def test_valid_spelling(word, ok):
    assert valid_spelling(word) == ok
