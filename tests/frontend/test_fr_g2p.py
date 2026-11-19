"""Token set fr-en and French spelling-to-phoneme rules (fr/g2p_fr.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.fr.g2p_fr import (
    PHONEMES,
    phonemes,
    unreadable_fr,
    valid_spelling,
    word_tokens_fr,
)
from vtts.frontend.lexicons import load_table, load_words


def test_token_set_fren_extends_v2():
    assert ps.TOKENS_FREN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_FREN[107:]
    assert all(t.startswith("FR:") for t in block)
    assert len(block) == len(set(block)) == 36 and ps.VOCAB_SIZE_FREN == 143
    assert ps.TOKEN_SETS[ps.TOKEN_SET_FREN] is ps.TOKENS_FREN and ps.TOKEN_SET_FREN == "fr-en"
    assert ps.PAIR_MODES["fr"] == "fr-en"
    idx = ps.token_index("fr-en")
    assert idx["FR:i"] == 107 and idx["FR:an"] == 118 and idx["FR:p"] == 125 and idx["EN:AA"] == 65
    assert {t[3:] for t in block} == PHONEMES


@pytest.mark.parametrize("word, ph", [
    # silent letters, plural, -ent of verbs and nouns
    ("enfants", "an f an"), ("parlent", "p a r l"), ("moment", "m O m an"),
    ("souvent", "s u v an"), ("client", "k l i j an"), ("aiment", "E m"), ("vient", "v j in"),
    ("argent", "a r zh an"), ("cent", "s an"), ("temps", "t an"), ("corps", "k O r"),
    ("grand", "g r an"), ("doigt", "d w a"), ("vingt", "v in"), ("blanc", "b l an"),
    ("tabac", "t a b a"), ("avec", "a v E k"), ("sud", "s y d"), ("bus", "b y s"), ("net", "n E t"),
    # -er, -ez, -et, -ed
    ("parler", "p a r l e"), ("premier", "p r @ m j e"), ("mer", "m E r"), ("hiver", "i v E r"),
    ("nez", "n e"), ("effet", "E f E"), ("pied", "p j e"), ("divers", "d i v E r"),
    # vowels, nasal vowels, glides
    ("maison", "m E z on"), ("beau", "b o"), ("oui", "w i"), ("nuit", "n H i"),
    ("jouer", "zh w e"), ("moi", "m w a"), ("loin", "l w in"), ("bien", "b j in"),
    ("pain", "p in"), ("plein", "p l in"), ("un", "un"), ("brun", "b r un"), ("parfum", "p a r f un"),
    ("album", "a l b O m"), ("science", "s j an s"), ("moyen", "m w a j in"),
    ("voyage", "v w a j a zh"), ("crier", "k r i j e"), ("cruel", "k r y E l"),
    # ill, il, gn, ch, g, c, s, t, x
    ("fille", "f i j"), ("ville", "v i l"), ("famille", "f a m i j"), ("travail", "t r a v a j"),
    ("soleil", "s O l E j"), ("feuille", "f oe j"), ("accueil", "a k oe j"), ("million", "m i l j on"),
    ("montagne", "m on t a gn"), ("chat", "sh a"), ("technique", "t E k n i k"),
    ("guerre", "g E r"), ("mangeons", "m an zh on"), ("cœur", "k oe r"), ("rose", "r o z"),
    ("nation", "n a s j on"), ("question", "k E s t j on"), ("partie", "p a r t i"),
    ("démocratie", "d e m O k r a s i"), ("exemple", "E g z an p l"), ("taxi", "t a k s i"),
    ("deuxième", "d eu z j E m"), ("soixante", "s w a s an t"), ("compter", "k on t e"),
    ("longtemps", "l on t an"), ("acquérir", "a k e r i r"), ("tandem", "t an d E m"),
    # mid vowels by position
    ("porte", "p O r t"), ("mot", "m o"), ("feu", "f eu"), ("peur", "p oe r"),
    ("heureux", "eu r eu"), ("heureuse", "eu r eu z"), ("neuf", "n oe f"),
    ("neuvième", "n eu v j E m"),
    # e muet
    ("samedi", "s a m d i"), ("maintenant", "m in t n an"), ("boulangerie", "b u l an zh r i"),
    ("petit", "p @ t i"), ("appartement", "a p a r t @ m an"), ("vendredi", "v an d r @ d i"),
    ("seulement", "s oe l m an"), ("remerciement", "r @ m E r s i m an"), ("secret", "s @ k r E"),
    ("ressembler", "r @ s an b l e"), ("le", "l @"),
    # elision and liaison prefixes, table
    ("l'école", "l e k O l"), ("qu'il", "k i l"), ("jusqu'à", "zh y s k a"), ("z'amis", "z a m i"),
    ("l'", "l"), ("aujourd'hui", "o zh u r d H i"), ("monsieur", "m @ s j eu"), ("femme", "f a m"),
    ("femmes", "f a m"), ("les", "l e"), ("et", "e"), ("est", "E"), ("six", "s i s"),
    ("sept", "s E t"), ("respect", "r E s p E"),
])
def test_phonemes(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_every_phoneme_is_a_token_and_tables_are_valid():
    for key, reading in load_table("fr", "overrides").items():
        assert set(phonemes(key)) <= PHONEMES, key
        if " " in reading:
            assert set(reading.split()) <= PHONEMES, key
    for name in ("final", "ent", "er", "ment_verbs", "c_silent", "l_silent", "f_silent", "native"):
        for w in load_words("fr", name):
            assert set(phonemes(w)) <= PHONEMES, (name, w)


def test_word_tokens_and_letters():
    assert word_tokens_fr("chat") == ["FR:sh", "FR:a"]
    assert word_tokens_fr("km") == word_tokens_fr("ka") + word_tokens_fr("èm")
    assert word_tokens_fr("Ñandú") and word_tokens_fr("Øresund")  # folded letters


@pytest.mark.parametrize("word, ok", [
    ("maison", True), ("chateau", True), ("parle", True), ("temps", True), ("vingt", True),
    ("jean", True), ("bonjour", True), ("enfants", True),
    ("weekend", False), ("chat", True), ("happy", False), ("update", True), ("smartwatch", False),
    ("facebook", False), ("parking", False), ("bluetooth", False),
])
def test_valid_spelling(word, ok):
    assert valid_spelling(word) == ok


def test_unreadable():
    assert unreadable_fr("Bonjour Москва") == list("Москва")
    assert unreadable_fr("Ça va, Muñoz? Œuvre, Øresund.") == []
