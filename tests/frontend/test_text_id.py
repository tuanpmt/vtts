"""text_to_ids(text, "id"): Indonesian + English, token set id-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_IDEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="id"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("ID:") for t in flat(text))


def test_tagging_indonesian_and_english_words():
    assert tag_words("Tolong buka YouTube di laptop saya.", "id") == [
        ("Tolong", "id"), ("buka", "id"), ("YouTube", "en"), ("di", "id"), ("laptop", "en"),
        ("saya.", "id")]
    assert tag_words("Wi-Fi di rumah lambat.", "id")[0] == ("Wi-Fi", "en")
    assert tag_words("KTP dan ESP32-P4", "id") == [
        ("KTP", "id"), ("dan", "id"), ("ESP32-P4", "neutral")]


@pytest.mark.parametrize("word, lang", [
    ("rumah", "id"), ("Jakarta", "id"), ("Gojek", "id"), ("Tokopedia", "id"), ("internet", "id"),
    ("menu", "id"), ("model", "id"), ("film", "id"), ("taksi", "id"),
    ("update", "en"), ("online", "en"), ("game", "en"), ("email", "en"), ("manager", "en"),
    ("iPhone", "en"), ("weekend", "en"), ("Spotify", "en"), ("Facebook", "en"),
])
def test_word_lang(word, lang):
    assert word_lang(word, "id") == lang


def test_indonesian_sentence():
    assert ph("Apa kabar?") == "a1 p a _ k a1 b a r ?"
    assert "EN:" not in " ".join(flat("Saya makan nasi goreng di rumah nenek."))


def test_mixed_id_en():
    toks = flat("Saya sudah update aplikasi itu.")
    assert "EN:AH" in toks and "ID:@" not in toks[:2] and toks[-1] == "."
    assert flat("Dia suka main game online.").count(" ") == 4


def test_numbers_and_codes_in_indonesian():
    assert flat("Ada 21 orang.") == flat("Ada dua puluh satu orang.")
    assert flat("Rp50.000") == flat("lima puluh ribu rupiah")
    assert flat("ke-3") == flat("ketiga")


def test_ids_use_iden_set_and_english_ids_match_v2():
    ids = text_to_ids("Buka YouTube, ya.", "id")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("id-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_IDEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "id")


def test_other_modes_unchanged_by_indonesian():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Apa kabar, rumah", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    es = [t for ch in text_to_tokens("Apa kabar, rumah", "es") for t in ch]
    assert not any(t.startswith("ID:") for t in es)
    assert word_lang("rumah", "en") == "en"


def test_long_indonesian_text_is_chunked():
    one = "anak anak bermain bola di lapangan dekat sekolah setiap sore hari"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "id")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
