"""Token set tr-en and Turkish spelling-to-phoneme rules (tr/g2p_tr.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.lexicons import load_table
from vtts.frontend.tr.g2p_tr import (
    _read,
    fold,
    phonemes,
    tr_lower,
    unreadable_tr,
    valid_spelling,
    word_tokens_tr,
)


def test_token_set_tren_extends_v2():
    assert ps.TOKENS_TREN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_TREN[107:]
    assert all(t.startswith("TR:") for t in block)
    assert len(block) == len(set(block)) == 39 and ps.VOCAB_SIZE_TREN == 146
    assert ps.TOKEN_SETS[ps.TOKEN_SET_TREN] is ps.TOKENS_TREN and ps.TOKEN_SET_TREN == "tr-en"
    assert ps.PAIR_MODES["tr"] == "tr-en"
    idx = ps.token_index("tr-en")
    assert idx["TR:a"] == 107 and idx["TR:a1"] == 115 and idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_TREN[107:]}
    text = ("çocuk şeker ığdır öğretmen üzüm jaguar cam yağmur dağ değil hâlâ kâr rüzgâr millî "
            "mahkûm quiz wifi taksi xenon istanbul'da")
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w


def test_turkish_lower_case():
    assert tr_lower("IŞIK") == "ışık" and tr_lower("İSTANBUL") == "istanbul"
    assert tr_lower("İzmir") == "izmir" and fold("ILIK") == "ılık"


@pytest.mark.parametrize("word, ph", [
    # letters
    ("çocuk", "ch o c u1 k"), ("şeker", "sh e k e1 r"), ("ılık", "I l I1 k"),
    ("üzüm", "ue z ue1 m"), ("göz", "g oe1 z"), ("jandarma", "zh a n d a r m a1"),
    ("yol", "y o1 l"), ("anne", "a n n e1"), ("dikkat", "d i k k a1 t"),
    # ğ and long vowels
    ("dağ", "d a1 long"), ("yağmur", "y a long m u1 r"), ("öğretmen", "oe long r e t m e1 n"),
    ("değil", "d e y i1 l"), ("ağaç", "a1 long ch"), ("soğuk", "s o long u1 k"),
    ("hâlâ", "h a long l a1 long"), ("kâr", "ky a1 long r"), ("rüzgâr", "r ue z gy a1 long r"),
    # stress: default final, overrides with suffixes, apostrophe, pre-stressing suffixes, clitics
    ("kitaplarımızdan", "k i t a p l a r I m I z d a1 n"),
    ("ankara", "a1 n k a r a"), ("ankara'da", "a1 n k a r a d a"), ("ankarada", "a1 n k a r a d a"),
    ("istanbul'dan", "i s t a1 n b u l d a n"), ("ahmet'in", "a h m e1 t i n"),
    ("masalar", "m a1 s a l a r"), ("şimdi", "sh i1 m d i"),
    ("geliyor", "g e l i1 y o r"), ("gelmiyor", "g e1 l m i y o r"), ("gelmedi", "g e1 l m e d i"),
    ("mi", "m i"), ("misiniz", "m i s i n i z"), ("de", "d e"), ("ve", "v e"),
    ("dört'üncü", "d oe1 r d ue n c ue"),
])
def test_word(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_word_tokens_prefix_and_spelling():
    assert word_tokens_tr("ev") == ["TR:e1", "TR:v"]
    assert word_tokens_tr("km") == word_tokens_tr("ke") + word_tokens_tr("me")


def test_fold_and_unreadable():
    assert fold("Café") == "cafe" and fold("Ärger") == "erger"
    assert unreadable_tr("Москва") and not unreadable_tr("Çok güzel, François!")


def test_overrides_differ_from_rules_and_mark_stress():
    table = load_table("tr", "overrides")
    assert len(table) > 80
    for key, respelling in table.items():
        assert respelling.count("ˈ") == 1 and respelling.replace("ˈ", "") == key, key
        assert tuple(_read(key)) != phonemes(key), key


@pytest.mark.parametrize("word, ok", [
    ("masa", True), ("kitap", True), ("tren", True), ("spor", True), ("kurt", True),
    ("saat", True), ("ben", True), ("sen", True),
    ("weekend", False), ("smart", False), ("the", False), ("facebook", False), ("band", False),
    ("check", False), ("shop", False), ("night", False), ("good", False), ("ring", False),
])
def test_valid_spelling(word, ok):
    assert valid_spelling(word) == ok
