"""text_to_ids(text, "sv"): Swedish + English, token set sv-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.latin import latin_word_lang
from vtts.frontend.phoneme_set import TOKENS_SVEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="sv"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def test_tagging_swedish_and_english_words():
    assert tag_words("Har du öppnat Netflix på din iPhone?", "sv") == [
        ("Har", "sv"), ("du", "sv"), ("öppnat", "sv"), ("Netflix", "en"), ("på", "sv"), ("din", "sv"),
        ("iPhone?", "en")]


@pytest.mark.parametrize("word, lang", [
    ("Göteborg", "sv"), ("och", "sv"), ("man", "sv"), ("in", "sv"),
    ("update", "en"), ("the", "en"), ("software", "en"), ("YouTube", "en"), ("USB", "sv"), ("km", "sv"),
    ("hus", "sv"), ("Lindqvist", "sv"), ("show", "en"), ("Bluetooth", "en"), ("Wi-Fi", "en"),
])
def test_latin_word_lang(word, lang):
    assert latin_word_lang(word, "sv") == lang
    assert word_lang(word, "sv") == lang


def test_swedish_sentence_ids():
    ids = text_to_ids("Hej, hur mår du?", "sv")
    index = token_index("sv-en")
    assert len(ids) == 1 and ids[0][0] == index["<bos>"] and ids[0][-1] == index["<eos>"]
    assert all(i < len(TOKENS_SVEN) for i in ids[0])
    assert all(i >= VOCAB_SIZE_V2 or i < 8 for i in ids[0])


def test_mixed_sv_en():
    toks = flat("Öppna GitHub och sök efter projektet.")
    assert "EN:G" in toks and "SV:k" in toks and toks[-1] == "."
    assert toks[toks.index("EN:G") - 1] == " "


def test_numbers_and_codes_in_swedish():
    assert flat("Jag är 21 år.") == flat("Jag är tjugoett år.")
    assert flat("ESP32-P4") == flat("e ess pe tre två pe fyra")
    assert flat("klockan 7:30") == flat("klockan sju trettio")
    assert flat("Det kostar 12,50 kr.") == flat("Det kostar tolv kronor och femtio öre.")
