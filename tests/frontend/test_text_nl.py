"""text_to_ids(text, "nl"): Dutch + English, token set nl-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.latin import latin_word_lang
from vtts.frontend.phoneme_set import TOKENS_NLEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="nl"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def test_tagging_dutch_and_english_words():
    assert tag_words("Heb je Netflix op de iPhone geopend?", "nl") == [
        ("Heb", "nl"), ("je", "nl"), ("Netflix", "en"), ("op", "nl"), ("de", "nl"), ("iPhone", "en"),
        ("geopend?", "nl")]
    assert tag_words("Open GitHub en zoek het project.", "nl") == [
        ("Open", "nl"), ("GitHub", "en"), ("en", "nl"), ("zoek", "nl"), ("het", "nl"), ("project.", "nl")]


@pytest.mark.parametrize("word, lang", [
    ("België", "nl"), ("geïnstalleerd", "nl"),                     # own letters
    ("in", "nl"), ("is", "nl"), ("door", "nl"), ("was", "nl"),    # native list before the English list
    ("update", "en"), ("online", "en"), ("the", "en"), ("software", "en"), ("reminder", "en"),
    ("YouTube", "en"), ("USB", "nl"), ("km", "nl"), ("kWh", "nl"), ("bijv", "nl"),
    ("huis", "nl"), ("staatshoofd", "nl"), ("show", "en"), ("Bluetooth", "en"), ("Wi-Fi", "en"),
])
def test_latin_word_lang(word, lang):
    assert latin_word_lang(word, "nl") == lang
    assert word_lang(word, "nl") == lang


def test_dutch_sentence_ids():
    ids = text_to_ids("Hallo, hoe gaat het?", "nl")
    index = token_index("nl-en")
    assert len(ids) == 1 and ids[0][0] == index["<bos>"] and ids[0][-1] == index["<eos>"]
    assert all(i < len(TOKENS_NLEN) for i in ids[0])
    assert all(i >= VOCAB_SIZE_V2 or i < 8 for i in ids[0])  # no Vietnamese or English ids


def test_mixed_nl_en():
    toks = flat("Open GitHub en zoek het project.")
    assert "EN:G" in toks and "NL:z" in toks and toks[-1] == "."
    assert toks[toks.index("EN:G") - 1] == " "


def test_numbers_and_codes_in_dutch():
    assert flat("Ik ben 21 jaar.") == flat("Ik ben eenentwintig jaar.")
    assert flat("ESP32-P4") == flat("ee es pee drie twee pee vier")
    assert flat("om 7:30") == flat("om zeven uur dertig")
    assert flat("Het kost € 5,50.") == flat("Het kost vijf euro en vijftig cent.")
