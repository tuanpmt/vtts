"""text_to_ids(text, "da"): Danish + English, token set da-en."""

import pytest

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_DAEN, VOCAB_SIZE_DAEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="da"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("DA:") for t in flat(text))


def test_token_set_size():
    assert VOCAB_SIZE_DAEN == len(TOKENS_DAEN) == 158
    assert TOKENS_DAEN[:VOCAB_SIZE_V2] == tuple(token_index("vi-en"))


def test_tagging_danish_and_english_words():
    assert tag_words("Åbn YouTube på min laptop.", "da") == [
        ("Åbn", "da"), ("YouTube", "en"), ("på", "da"), ("min", "da"), ("laptop.", "en")]
    assert tag_words("Wi-Fi er langsomt", "da")[0] == ("Wi-Fi", "en")
    assert tag_words("USB og ESP32-P4", "da") == [("USB", "da"), ("og", "da"), ("ESP32-P4", "neutral")]


@pytest.mark.parametrize("word, lang", [
    ("hus", "da"), ("København", "da"), ("for", "da"), ("time", "da"), ("store", "da"),
    ("fodboldspiller", "da"), ("fotoudstillingen", "da"), ("Aarhus", "da"), ("to", "da"),
    ("update", "en"), ("online", "en"), ("meeting", "en"), ("iPhone", "en"), ("weekend", "en"),
    ("Spotify", "en"), ("Facebook", "en"), ("download", "en"),
])
def test_word_lang(word, lang):
    assert word_lang(word, "da") == lang


def test_danish_words():
    assert ph("hus") == 'h u: " ? s'
    assert ph("huset") == 'h u: " ? s @ D'
    assert ph("og") == "V w"  # function word: no stress mark
    assert "DA:?" in flat("hund") and "DA:\"" in flat("hund")


def test_dot_before_lower_case_does_not_end_a_sentence_in_da():
    assert split_sentences_raw("Den 5. marts kl. 9. Så går vi.", "da") == ["Den 5. marts kl. 9.", "Så går vi."]
    assert split_sentences_raw("Den 5. marts.", "es") == ["Den 5.", "marts."]
    assert flat("den 5. marts") == flat("den femte marts")
    assert flat("kl. 14.30") == flat("klokken fjorten tredive")


def test_mixed_sentence():
    toks = flat("Jeg har købt en ny iPhone.")
    assert "EN:F" in toks and "DA:k" in toks and toks[-1] == "."


def test_numbers_and_money():
    assert flat("21") == flat("enogtyve")
    assert flat("12,50 kr.") == flat("tolv kroner og halvtreds øre") + ["."]
    assert flat("1984") == flat("nitten hundrede og fireogfirs")


def test_ids_use_daen_set_and_english_ids_match_v2():
    ids = text_to_ids("Åbn YouTube.", "da")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("da-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_DAEN)
    assert text_to_ids("Download the update.", "en") == text_to_ids("Download the update.", "da")


def test_other_modes_unchanged_by_danish():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Tak, hus", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    assert word_lang("hus", "en") == "en"


def test_long_danish_text_is_chunked():
    one = "børnene spillede fodbold i gården hver eftermiddag efter skole sammen med deres venner"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "da")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
