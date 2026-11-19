"""text_to_ids(text, "tl"): Tagalog + English (Taglish), token set tl-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_TLEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="tl"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("TL:") for t in flat(text))


def test_tagging_tagalog_and_english_words():
    assert tag_words("Pakibuksan ang YouTube sa laptop ko.", "tl") == [
        ("Pakibuksan", "tl"), ("ang", "tl"), ("YouTube", "en"), ("sa", "tl"), ("laptop", "en"),
        ("ko.", "tl")]
    assert tag_words("Mahina ang Wi-Fi.", "tl")[2] == ("Wi-Fi.", "en")
    assert tag_words("DOH at ESP32-P4", "tl") == [("DOH", "tl"), ("at", "tl"), ("ESP32-P4", "neutral")]


@pytest.mark.parametrize("word, lang", [
    ("bahay", "tl"), ("Pilipinas", "tl"), ("Quezon", "tl"), ("Cebu", "tl"), ("mag-aral", "tl"),
    ("dalawampu't", "tl"), ("pamilya", "tl"), ("Jose", "tl"), ("kompyuter", "tl"),
    ("update", "en"), ("online", "en"), ("meeting", "en"), ("email", "en"), ("iPhone", "en"),
    ("weekend", "en"), ("Spotify", "en"), ("Facebook", "en"), ("computer", "en"),
])
def test_word_lang(word, lang):
    assert word_lang(word, "tl") == lang


def test_tagalog_sentence():
    assert ph("Salamat po.") == "s a l a1 m a t _ p o ."
    assert ph("Ang bata ng mga tao.") == "a ng _ b a1 t a ? _ n a ng _ m a ng a _ t a1 ? o ."
    assert "EN:" not in " ".join(flat("Kumain kami ng adobo sa bahay ni lola."))


def test_taglish():
    toks = flat("Na-update ko na ang app.")
    assert "EN:AH" in toks and toks[-1] == "."
    assert flat("Mag-meeting tayo mamaya.") and "EN:M" in flat("Mag-meeting tayo mamaya.")


def test_numbers_and_codes_in_tagalog():
    assert flat("May 3 aso.") == flat("May tatlong aso.")
    assert flat("₱50") == flat("singkuwenta pesos")
    assert flat("ika-3") == flat("ikatlo")


def test_ids_use_tlen_set_and_english_ids_match_v2():
    ids = text_to_ids("Buksan mo ang YouTube.", "tl")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("tl-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_TLEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "tl")


def test_other_modes_unchanged_by_tagalog():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Salamat, bahay", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    assert word_lang("bahay", "en") == "en"


def test_long_tagalog_text_is_chunked():
    one = "naglalaro ang mga bata ng basketbol sa plasa malapit sa paaralan tuwing hapon"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "tl")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
