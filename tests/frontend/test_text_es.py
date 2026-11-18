"""text_to_ids(text, "es"): Spanish + English, token set es-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.latin import latin_word_lang
from vtts.frontend.lexicons import load_words
from vtts.frontend.phoneme_set import TOKENS_ESEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="es"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("ES:") for t in flat(text))


def test_tagging_spanish_and_english_words():
    assert tag_words("¿Abriste Netflix en el iPhone?", "es") == [
        ("Abriste", "es"), ("Netflix", "en"), ("en", "es"), ("el", "es"), ("iPhone?", "en")]
    assert tag_words("Abre GitHub y busca el proyecto.", "es") == [
        ("Abre", "es"), ("GitHub", "en"), ("y", "es"), ("busca", "es"), ("el", "es"),
        ("proyecto.", "es")]
    assert tag_words("El smart home funciona", "es") == [
        ("El", "es"), ("smart", "en"), ("home", "en"), ("funciona", "es")]
    assert tag_words("ESP32-P4 con USB", "es") == [
        ("ESP32-P4", "neutral"), ("con", "es"), ("USB", "es")]


@pytest.mark.parametrize("word, lang", [
    # own letters
    ("canción", "es"), ("año", "es"), ("pingüino", "es"),
    # native list wins over the English list
    ("he", "es"), ("red", "es"), ("sale", "es"), ("come", "es"), ("internet", "es"),
    # English list
    ("update", "en"), ("online", "en"), ("router", "en"), ("google", "en"), ("the", "en"),
    # CamelCase, acronyms
    ("YouTube", "en"), ("macOS", "en"), ("USB", "es"), ("GPS", "es"),
    # units and abbreviations of the normalizer, single letters
    ("kWh", "es"), ("GHz", "es"), ("km", "es"), ("etc", "es"), ("m", "es"), ("x", "es"),
    # spelling
    ("casa", "es"), ("Barcelona", "es"), ("perro", "es"), ("weekend", "en"),
    ("Bluetooth", "en"), ("Wi-Fi", "en"), ("Spotify", "en"), ("franco-alemana", "es"),
])
def test_latin_word_lang(word, lang):
    assert latin_word_lang(word, "es") == lang
    assert word_lang(word, "es") == lang


def test_word_lists_are_consistent():
    native, english = load_words("es", "native"), load_words("latin", "english")
    assert native and english
    # the words of the English list that are Spanish words are listed in native.txt
    for w in ("he", "red", "sale", "come", "use", "sea"):
        assert w in english or w in native


def test_spanish_sentence():
    assert ph("Hola, ¿qué tal?") == "o1 l a , k e1 _ t a1 l ?"
    assert ph("La casa es grande.") == "l a _ k a1 s a _ e1 s _ g r a1 n d e ."
    assert "EN:" not in " ".join(flat("El niño come pan con queso y jamón."))


def test_mixed_es_en():
    toks = flat("Abre GitHub y busca el proyecto.")
    assert "EN:G" in toks and "ES:k" in toks and toks[-1] == "."
    i = toks.index("EN:G")
    assert toks[i - 1] == " "
    toks = flat("El smart home funciona con Alexa.")
    assert "EN:HH" in toks and "EN:AH" in toks


def test_numbers_and_codes_in_spanish():
    assert flat("Tengo 21 años.") == flat("Tengo veintiún años.")
    assert flat("ESP32-P4") == flat("é ese pe tres dos pe cuatro")
    assert flat("a las 7:30") == flat("a las siete y treinta")


def test_ids_use_esen_set_and_english_ids_match_v2():
    ids = text_to_ids("Abre GitHub, por favor.", "es")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("es-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_ESEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "es")


def test_other_modes_unchanged_by_spanish():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, ¿qué tal? canción niño hello", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    assert word_lang("canción", "vi") == "vi"      # non-ASCII letters stay Vietnamese in vi-en
    assert word_lang("casa", "en") == "en"


def test_long_spanish_text_is_chunked():
    one = "el perro de mi vecino corre por el parque todas las mañanas"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "es")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    assert all(sum(1 for t in c if t == " ") + 1 <= 40 for c in chunks)
