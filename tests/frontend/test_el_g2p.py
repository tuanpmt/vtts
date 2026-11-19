"""Token set el-en and Greek spelling-to-phoneme rules (el/g2p_el.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.el.g2p_el import lower, override_table, phonemes, unreadable_el, word_tokens_el


def p(word):
    return " ".join(phonemes(word))


def test_token_set_layout():
    toks = ps.TOKENS_ELEN
    assert toks[:ps.VOCAB_SIZE_V2] == ps.TOKENS_V2
    assert toks[107] == "EL:a" and len(toks) == ps.VOCAB_SIZE_ELEN == 139
    assert len(set(toks)) == len(toks)
    assert ps.PAIR_MODES["el"] == "el-en" and ps.TOKEN_SETS["el-en"] == toks


def test_lower_case_final_sigma_and_accented_capitals():
    assert lower("ΟΔΟΣ") == "οδος" and lower("ΣΑΣ") == "σας" and lower("Άρης") == "άρης"
    assert lower("ΆΈΉΊΌΎΏ") == "άέήίόύώ"


@pytest.mark.parametrize("word, out", [
    ("Αθήνα", "a th i1 n a"),
    ("είναι", "i1 n e"),
    ("ούτε", "u1 t e"),
    ("παιδιά", "p e dh j a1"),
    ("χωριό", "x o r j o1"),
    ("ήλιος", "i1 l j o s"),
    ("δημιουργία", "dh i m i u r gh i1 a"),
    ("για", "gh j a"),
    ("γιατί", "gh j a t i1"),
    ("ποιος", "p j o1 s"),
    ("μπαμπάς", "b a b a1 s"),
    ("ντομάτα", "d o m a1 t a"),
    ("πέντε", "p e1 d e"),
    ("γκρίζος", "g r i1 z o s"),
    ("άγκυρα", "a1 ng g i r a"),
    ("άγγελος", "a1 ng g e l o s"),
    ("άγχος", "a1 ng x o s"),
    ("αύριο", "a1 v r i o"),
    ("ευχαριστώ", "e f x a r i s t o1"),
    ("αυτοκίνητο", "a f t o k i1 n i t o"),
    ("λαϊκός", "l a i k o1 s"),
    ("τσάι", "ts a1 i"),
    ("τζάμι", "dz a1 m i"),
    ("κόσμος", "k o1 z m o s"),
    ("Έλληνας", "e1 l i n a s"),
    ("ψάρι", "p s a1 r i"),
    ("ξένος", "k s e1 n o s"),
    ("άνθρωπός", "a1 n th r o p o1 s"),
    ("ΑΘΗΝΑ", "a th i1 n a"),
    ("και", "k e"),
    ("φως", "f o1 s"),
])
def test_word_phonemes(word, out):
    assert p(word) == out


def test_tokens():
    toks = word_tokens_el("γάτα")
    assert toks == ["EL:gh", "EL:a1", "EL:t", "EL:a"]
    assert all(t in ps.TOKENS_ELEN for t in word_tokens_el("ευχαριστώ πολύ"))


def test_overrides_are_tokens_and_differ_from_rules():
    from vtts.frontend.el import g2p_el

    table = dict(override_table())
    try:
        override_table().clear()
        g2p_el.phonemes.cache_clear()
        for key, value in table.items():
            assert all(f"EL:{t}" in ps.TOKENS_ELEN for t in value.split()), key
            assert " ".join(g2p_el.phonemes(key)) != value, key
    finally:
        override_table().update(table)
        g2p_el.phonemes.cache_clear()


def test_unreadable():
    assert unreadable_el("Γεια Москва") and not unreadable_el("Γεια σου, François και Wi-Fi")
