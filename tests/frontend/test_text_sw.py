"""text_to_ids(text, "sw"): Swahili + English, token set sw-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_SWEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="sw"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("SW:") for t in flat(text))


def test_tagging_swahili_and_english_words():
    assert tag_words("Tafadhali fungua YouTube kwenye laptop yangu.", "sw") == [
        ("Tafadhali", "sw"), ("fungua", "sw"), ("YouTube", "en"), ("kwenye", "sw"),
        ("laptop", "en"), ("yangu.", "sw")]
    assert tag_words("Wi-Fi ni dhaifu.", "sw")[0] == ("Wi-Fi", "en")
    assert tag_words("CCM na ESP32-P4", "sw") == [("CCM", "sw"), ("na", "sw"), ("ESP32-P4", "neutral")]


@pytest.mark.parametrize("word, lang", [
    ("nyumba", "sw"), ("Tanzania", "sw"), ("Nairobi", "sw"), ("ng'ombe", "sw"), ("mtoto", "sw"),
    ("Kenya", "sw"), ("Mombasa", "sw"), ("Mohamed", "sw"),
    ("update", "en"), ("online", "en"), ("meeting", "en"), ("email", "en"), ("iPhone", "en"),
    ("weekend", "en"), ("Spotify", "en"), ("Facebook", "en"), ("smartphone", "en"),
])
def test_word_lang(word, lang):
    assert word_lang(word, "sw") == lang


def test_swahili_sentence():
    assert ph("Habari yako?") == "h a b a1 r i _ y a1 k o ?"
    assert "EN:" not in " ".join(flat("Mtoto anakula chakula nyumbani kwa bibi."))


def test_mixed_sw_en():
    toks = flat("Nimefanya update ya app.")
    assert "EN:AH" in toks and toks[-1] == "."


def test_numbers_and_codes_in_swahili():
    assert flat("Watu 3.") == flat("Watu tatu.")
    assert flat("TSh 5,000") == flat("shilingi elfu tano")
    assert flat("saa 14:30") == flat("saa kumi na nne na nusu")


def test_ids_use_swen_set_and_english_ids_match_v2():
    ids = text_to_ids("Fungua YouTube, tafadhali.", "sw")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("sw-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_SWEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "sw")


def test_other_modes_unchanged_by_swahili():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Habari, nyumba", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    assert word_lang("nyumba", "en") == "en"


def test_long_swahili_text_is_chunked():
    one = "watoto wanacheza mpira uwanjani karibu na shule kila siku jioni baada ya masomo"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "sw")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
