"""Token set pl-en and the Polish spelling rules (pl/g2p_pl.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.lexicons import load_table
from vtts.frontend.pl.g2p_pl import phonemes, unreadable_pl, valid_spelling, word_tokens_pl


def test_token_set_plen_extends_v2():
    assert ps.TOKENS_PLEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_PLEN[107:]
    assert all(t.startswith("PL:") for t in block)
    assert len(block) == len(set(block)) == 44 and ps.VOCAB_SIZE_PLEN == 151
    assert ps.TOKEN_SETS[ps.TOKEN_SET_PLEN] is ps.TOKENS_PLEN and ps.PAIR_MODES["pl"] == "pl-en"
    idx = ps.token_index("pl-en")
    assert idx["PL:a"] == 107 and idx["PL:a1"] == 115 and idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_PLEN[107:]}
    text = ("chrząszcz szczęście dziewczyna dżem dźwięk źle cześć dzień kiedy gitara piasek rzeka "
            "przy wódka prośba chleb róg żółw ręka będzie dąb kąt wziął idę są mąż wąs xero "
            "video jabłko mysz ucho ogień gęś ciąża")
    seen = set()
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w
        seen |= set(phonemes(w))
    assert len(seen) >= 36


@pytest.mark.parametrize("word, ph", [
    # penultimate stress; i after c s z n dz k g is softness only
    ("dom", "d o1 m"), ("ciasto", "c' a1 s t o"), ("siedem", "s' e1 d e m"),
    ("niebo", "n' e1 b o"), ("kiedy", "k j e1 d y"), ("gitara", "g i t a1 r a"),
    ("piasek", "p j a1 s e k"), ("dziecko", "dz' e1 ts k o"),
    # digraphs and diacritics
    ("cześć", "ch e1 s' c'"), ("źle", "z' l e1"), ("dzień", "dz' e1 n'"),
    ("chrząszcz", "x sh on1 sh ch"), ("szczęście", "sh ch en1 s' c' e"),
    ("rzeka", "zh e1 k a"), ("xero", "k s e1 r o"),
    # nasal vowels: homorganic nasal before stops, oral before l ł, final ę oral
    ("ręka", "r e1 n k a"), ("będzie", "b e1 n' dz' e"), ("dąb", "d o1 m p"), ("kąt", "k o1 n t"),
    ("wziął", "v z' o1 w"), ("zaczęli", "z a ch e1 l i"), ("idę", "i1 d e"), ("są", "s on1"),
    ("mąż", "m on1 sh"),
    # voicing: regressive, final devoicing, w and rz after a voiceless consonant
    ("wódka", "v u1 t k a"), ("prośba", "p r o1 z' b a"), ("chleb", "x l e1 p"),
    ("róg", "r u1 k"), ("żółw", "zh u1 w f"), ("twój", "t f u1 j"), ("trzy", "t sh y1"),
    ("krzesło", "k sh e1 s w o"),
    ("także", "t a1 g zh e"), ("historii", "x i s t o1 r j i"), ("linii", "l i1 n' i"),
    # au eu
    ("autor", "a1 w t o r"), ("europa", "e w r o1 p a"), ("nauka", "n a u1 k a"),
    ("muzeum", "m u z e1 u m"),
    # stress exceptions (antepenult.txt stems, past plural)
    ("muzyce", "m u1 z y ts e"), ("języka", "j en z y1 k a"), ("matematyka", "m a t e m a1 t y k a"), ("byliśmy", "b y1 l i s' m y"),
    ("zrobilibyśmy", "z r o b i1 l i b y s' m y"),
    # clitics: unstressed, w / z joined to the next word by the normalizer
    ("nie", "n' e"), ("przy", "p sh y"), ("w-domu", "v d o1 m u"), ("w-polsce", "f p o1 l s ts e"),
    ("z-tobą", "s t o1 b on"), ("w-muzyce", "v m u1 z y ts e"), ("w-to", "f t o"),
])
def test_word_phonemes(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_overrides_differ_from_the_rules():
    from vtts.frontend.pl import g2p_pl

    for key, reading in load_table("pl", "overrides").items():
        assert reading != key, key
    assert "muzyki" in g2p_pl.antepenult_words() and "języka" not in g2p_pl.antepenult_words()


@pytest.mark.parametrize("word, ok", [
    ("dom", True), ("warszawa", True), ("niemiecki", True), ("prawo", True), ("szkoła", False),
    ("update", True), ("smartphone", False), ("streaming", False), ("weekend", False),
    ("facebook", False), ("thanks", False), ("happy", False), ("video", False),
])
def test_valid_spelling(word, ok):
    assert valid_spelling(word) == ok


def test_word_tokens():
    assert word_tokens_pl("pkp") == [t for n in ("pe", "ka", "pe") for t in word_tokens_pl(n)]
    assert word_tokens_pl("w") == ["PL:f"]
    assert unreadable_pl("Cześć Москва") and not unreadable_pl("Cześć, François, Škoda")
