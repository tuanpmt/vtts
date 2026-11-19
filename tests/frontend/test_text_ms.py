"""text_to_ids(text, "ms"): Malay + English, token set ms-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_MSEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="ms"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("MS:") for t in flat(text))


def test_tagging_malay_and_english_words():
    assert tag_words("Tolong buka YouTube di laptop saya.", "ms") == [
        ("Tolong", "ms"), ("buka", "ms"), ("YouTube", "en"), ("di", "ms"), ("laptop", "en"),
        ("saya.", "ms")]
    assert tag_words("Wi-Fi di rumah perlahan.", "ms")[0] == ("Wi-Fi", "en")
    assert tag_words("KTM dan ESP32-P4", "ms") == [("KTM", "ms"), ("dan", "ms"), ("ESP32-P4", "neutral")]


@pytest.mark.parametrize("word, lang", [
    ("rumah", "ms"), ("Malaysia", "ms"), ("Terengganu", "ms"), ("teksi", "ms"), ("menu", "ms"),
    ("model", "ms"), ("film", "ms"), ("loghat", "ms"), ("majlis", "ms"),
    ("update", "en"), ("online", "en"), ("game", "en"), ("email", "en"), ("iPhone", "en"),
    ("weekend", "en"), ("Spotify", "en"), ("Facebook", "en"),
])
def test_word_lang(word, lang):
    assert word_lang(word, "ms") == lang


def test_malay_sentence():
    assert ph("Apa khabar?") == "a1 p a _ kh a1 b a r ?"
    assert "EN:" not in " ".join(flat("Saya makan nasi lemak di rumah nenek."))


def test_mixed_ms_en():
    toks = flat("Saya sudah update aplikasi itu.")
    assert "EN:AH" in toks and toks[-1] == "."
    assert flat("Dia suka main game online.").count(" ") == 4


def test_numbers_and_codes_in_malay():
    assert flat("Ada 8 orang.") == flat("Ada lapan orang.")
    assert flat("RM12.50") == flat("dua belas ringgit lima puluh sen")
    assert flat("ke-3") == flat("ketiga")


def test_ids_use_msen_set_and_english_ids_match_v2():
    ids = text_to_ids("Buka YouTube, ya.", "ms")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("ms-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_MSEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "ms")


def test_other_modes_unchanged_by_malay():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Apa khabar, rumah", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    idn = [t for ch in text_to_tokens("Apa khabar, universiti", "id") for t in ch]
    assert not any(t.startswith("MS:") for t in idn) and "ID:f" in idn
    assert word_lang("rumah", "en") == "en"


def test_long_malay_text_is_chunked():
    one = "budak budak bermain bola di padang dekat sekolah setiap petang hari"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "ms")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
