"""text_to_ids(text, "pt"): Brazilian Portuguese + English, token set pt-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_PTEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="pt"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("PT:") for t in flat(text))


def test_tagging_portuguese_and_english_words():
    assert tag_words("Abra o GitHub e procure o projeto.", "pt") == [
        ("Abra", "pt"), ("o", "pt"), ("GitHub", "en"), ("e", "pt"), ("procure", "pt"),
        ("o", "pt"), ("projeto.", "pt")]
    assert tag_words("O smart home funciona", "pt")[1:3] == [("smart", "en"), ("home", "en")]
    assert tag_words("ESP32-P4 com USB", "pt") == [
        ("ESP32-P4", "neutral"), ("com", "pt"), ("USB", "pt")]


@pytest.mark.parametrize("word, lang", [
    ("ação", "pt"), ("você", "pt"), ("São", "pt"),
    ("do", "pt"), ("as", "pt"), ("time", "pt"), ("come", "pt"), ("internet", "pt"),
    ("casa", "pt"), ("trabalho", "pt"), ("Recife", "pt"),
    ("update", "en"), ("online", "en"), ("game", "en"), ("the", "en"), ("laptop", "en"),
    ("YouTube", "en"), ("weekend", "en"), ("Spotify", "en"), ("Wi-Fi", "en"), ("chat", "en"),
])
def test_word_lang(word, lang):
    assert word_lang(word, "pt") == lang


def test_portuguese_sentence():
    assert ph("Olá, tudo bem?") == "o l a1 , t u1 d u _ b en1 j ?"
    assert "EN:" not in " ".join(flat("A menina comeu o bolo de chocolate na casa da avó."))


def test_mixed_pt_en():
    toks = flat("Vou fazer o update do software.")
    assert "EN:AH" in toks and "PT:d" in toks and toks[-1] == "."
    assert flat("O laptop está lento.").count(" ") == 3


def test_numbers_and_codes_in_portuguese():
    assert flat("Tenho 21 anos.") == flat("Tenho vinte e um anos.")
    assert flat("às 14h30") == flat("às quatorze e trinta")
    assert flat("ESP32") == flat("é ésse pê três dois")


def test_ids_use_pten_set_and_english_ids_match_v2():
    ids = text_to_ids("Abra o YouTube, por favor.", "pt")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("pt-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_PTEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "pt")


def test_other_modes_unchanged_by_portuguese():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Olá, ação, coração e você", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    assert word_lang("ação", "es") == "neutral"  # ç and ã are not Spanish letters: read in es
    assert word_lang("ação", "vi") == "vi"


def test_long_portuguese_text_is_chunked():
    one = "o cachorro do meu vizinho corre pelo parque todas as manhãs de domingo"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "pt")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
