"""text_to_ids(text, "it"): Italian + English, token set it-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.latin import latin_word_lang
from vtts.frontend.lexicons import load_words
from vtts.frontend.phoneme_set import TOKENS_ITEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="it"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("IT:") for t in flat(text))


def test_tagging_italian_and_english_words():
    assert tag_words("Hai aperto Netflix sull'iPhone?", "it") == [
        ("Hai", "it"), ("aperto", "it"), ("Netflix", "en"), ("sull'", "it"), ("iPhone?", "en")]
    assert tag_words("Apri l’app di YouTube.", "it") == [
        ("Apri", "it"), ("l'", "it"), ("app", "en"), ("di", "it"), ("YouTube.", "en")]
    assert tag_words("L'acqua è fredda", "it") == [("L'acqua", "it"), ("è", "it"), ("fredda", "it")]
    assert tag_words("ESP32-P4 con USB", "it") == [
        ("ESP32-P4", "neutral"), ("con", "it"), ("USB", "it")]


@pytest.mark.parametrize("word, lang", [
    ("perché", "it"), ("città", "it"),                               # own letters
    ("come", "it"), ("in", "it"), ("fine", "it"), ("nord", "it"),    # native list
    ("update", "en"), ("online", "en"), ("the", "en"), ("google", "en"),
    ("YouTube", "en"), ("macOS", "en"), ("USB", "it"), ("GPS", "it"),
    ("kWh", "it"), ("km", "it"), ("ecc", "it"), ("m", "it"),
    ("casa", "it"), ("Milano", "it"), ("squadra", "it"), ("weekend", "en"),
    ("Bluetooth", "en"), ("Wi-Fi", "en"), ("Spotify", "en"), ("sud-ovest", "it"),
    ("dell'arte", "it"), ("l'acqua", "it"),
])
def test_latin_word_lang(word, lang):
    assert latin_word_lang(word, "it") == lang
    assert word_lang(word, "it") == lang


def test_word_lists_are_consistent():
    native, english = load_words("it", "native"), load_words("latin", "english")
    assert native and english
    for w in ("come", "in", "fine", "case"):
        assert w in english and w in native


def test_italian_sentence():
    assert ph("Ciao, come stai?") == "ch a1 o , k o1 m e _ s t a1 j ?"
    assert ph("La casa è grande.") == "l a _ k a1 z a _ E1 _ g r a1 n d e ."
    assert "EN:" not in " ".join(flat("Il bambino mangia la pizza con gli amici."))


def test_mixed_it_en():
    toks = flat("Apri GitHub e cerca il progetto.")
    assert "EN:G" in toks and "IT:k" in toks and toks[-1] == "."
    toks = flat("Apri l'app di Spotify.")
    assert toks[:6] == ["IT:a1", "IT:p", "IT:r", "IT:i", " ", "IT:l"] and "EN:AE" in toks


def test_numbers_and_codes_in_italian():
    assert flat("Ho 21 anni.") == flat("Ho ventun anni.")
    assert flat("ESP32-P4") == flat("e esse pi tre due pi quattro")
    assert flat("alle 7:30") == flat("alle sette e trenta")


def test_ids_use_iten_set_and_english_ids_match_v2():
    ids = text_to_ids("Apri GitHub, per favore.", "it")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("it-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_ITEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "it")


def test_other_modes_unchanged_by_italian():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, perché città hello", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    assert word_lang("città", "vi") == "vi"
    assert word_lang("casa", "en") == "en"
    assert tag_words("¿Abriste l'app?", "es")[1] == ("l'app?", "en")  # es: no elision rule


def test_long_italian_text_is_chunked():
    one = "il cane del mio vicino corre nel parco tutte le mattine"
    chunks = text_to_tokens(" ".join([one] * 12) + ".", "it")
    assert len(chunks) > 1 and all(len(c) <= 318 for c in chunks)
