import pytest

from vtts.frontend.da.g2p_da import (
    fold,
    known_words,
    lexicon,
    rules,
    split_compound,
    unreadable_da,
    valid_spelling,
    word_tokens_da,
    word_tokens_names,
)
from vtts.frontend.phoneme_set import TOKENS_DAEN


def names(word):
    return " ".join(word_tokens_names(word))


@pytest.mark.parametrize("word, toks", [
    ("hus", 'h u: " ? s'), ("huse", 'h u: " s @'), ("kat", 'k a " d'), ("gade", 'g a: " D @'),
    ("mand", 'm a " n ?'), ("hunden", 'h O " n ? @ n'), ("vej", 'v A " j~ ?'), ("bog", 'b O " w ?'),
    ("skrive", 's g R i: " v @'), ("ikke", 'e " g @'), ("nation", 'n a s\' o: " ? n'),
    ("høre", 'h 2: " 6'), ("år", 'Q: " ?'), ("betale", 'b e t a: " ? l @'),
])
def test_rules(word, toks):
    assert " ".join(rules(word)) == toks


def test_lexicon_entries_are_tokens():
    valid = {t.removeprefix("DA:") for t in TOKENS_DAEN if t.startswith("DA:")}
    assert len(lexicon()) > 10000 and len(known_words()) > len(lexicon())
    for w, toks in list(lexicon().items())[:3000]:
        assert set(toks) <= valid, w
        assert toks.count('"') <= 1, w


def test_lexicon_words():
    assert names("det") == "d e"  # function word: NST reading, no stress
    assert names("københavn") == 'k 2 b @ n h A " w ? n'


def test_compounds():
    assert split_compound("fodboldspiller") == [("fodbold", ""), ("spiller", "")]
    toks = word_tokens_names("fodboldspiller").split() if False else word_tokens_names("fodboldspiller")
    assert toks.count('"') == 1 and toks.count("%") >= 1
    assert split_compound("xyzq") is None


def test_spelled_consonant_clusters():
    assert names("pst") == names("pe") + " " + names("es") + " " + names("te")


def test_fold_and_valid_spelling():
    assert fold("Müller") == "myller" and fold("Ångström") == "ångstrøm"
    assert valid_spelling("hus") and valid_spelling("fotoudstillingen")
    assert not valid_spelling("smartwatch") and not valid_spelling("youtube")


def test_word_tokens_prefix_and_unreadable():
    assert all(t.startswith("DA:") for t in word_tokens_da("hus"))
    assert word_tokens_da("") == []
    assert unreadable_da("Hej Ærø éé ü") == [] and unreadable_da("Привет") == list("Привет")
