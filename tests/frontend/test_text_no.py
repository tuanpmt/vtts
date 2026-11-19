"""text_to_ids(text, "no"): Norwegian (Bokmål) + English, token set no-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.latin import latin_word_lang
from vtts.frontend.phoneme_set import TOKENS_NOEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="no"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def test_tagging_norwegian_and_english_words():
    assert tag_words("Har du åpnet Netflix på din iPhone?", "no") == [
        ("Har", "no"), ("du", "no"), ("åpnet", "no"), ("Netflix", "en"), ("på", "no"), ("din", "no"),
        ("iPhone?", "en")]


@pytest.mark.parametrize("word, lang", [
    ("Tromsø", "no"), ("for", "no"), ("at", "no"), ("store", "no"), ("time", "no"),
    ("update", "en"), ("the", "en"), ("software", "en"), ("YouTube", "en"), ("USB", "no"), ("km", "no"),
    ("hus", "no"), ("Akershus", "no"), ("show", "en"), ("Bluetooth", "en"), ("Wi-Fi", "en"),
])
def test_latin_word_lang(word, lang):
    assert latin_word_lang(word, "no") == lang
    assert word_lang(word, "no") == lang


def test_norwegian_sentence_ids():
    ids = text_to_ids("Hei, hvordan går det?", "no")
    index = token_index("no-en")
    assert len(ids) == 1 and ids[0][0] == index["<bos>"] and ids[0][-1] == index["<eos>"]
    assert all(i < len(TOKENS_NOEN) for i in ids[0])
    assert all(i >= VOCAB_SIZE_V2 or i < 8 for i in ids[0])


def test_mixed_no_en():
    toks = flat("Åpne GitHub og søk etter prosjektet.")
    assert "EN:G" in toks and "NO:k" in toks and toks[-1] == "."
    assert toks[toks.index("EN:G") - 1] == " "


def test_numbers_and_codes_in_norwegian():
    assert flat("Jeg er 21 år.") == flat("Jeg er tjueen år.")
    assert flat("ESP32-P4") == flat("e ess pe tre to pe fire")
    assert flat("klokka 7:30") == flat("klokka sju tretti")
    assert flat("Det koster 12,50 kr.") == flat("Det koster tolv kroner og femti øre.")
    assert len(text_to_ids("Den 17. mai er det fest.", "no")) == 1
