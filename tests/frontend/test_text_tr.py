"""text_to_ids(text, "tr"): Turkish + English, token set tr-en."""

import pytest

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.latin import latin_word_lang
from vtts.frontend.lexicons import load_words
from vtts.frontend.phoneme_set import TOKENS_TREN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="tr"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("TR:") for t in flat(text))


def test_tagging_turkish_and_english_words():
    assert tag_words("Netflix'i iPhone'da açtın mı?", "tr") == [
        ("Netflix", "en"), ("'i", "tr"), ("iPhone", "en"), ("'da", "tr"), ("açtın", "tr"), ("mı?", "tr")]
    assert tag_words("İstanbul'da YouTube’dan izledim.", "tr") == [
        ("İstanbul'da", "tr"), ("YouTube", "en"), ("'dan", "tr"), ("izledim.", "tr")]
    assert tag_words("ESP32-P4 ile USB", "tr") == [("ESP32-P4", "neutral"), ("ile", "tr"), ("USB", "tr")]


@pytest.mark.parametrize("word, lang", [
    ("çok", "tr"), ("güzel", "tr"), ("ışık", "tr"),                  # own letters
    ("her", "tr"), ("on", "tr"), ("model", "tr"),                     # native list
    ("update", "en"), ("online", "en"), ("the", "en"), ("google", "en"),
    ("YouTube", "en"), ("macOS", "en"), ("USB", "tr"), ("THY", "tr"),
    ("kWh", "tr"), ("km", "tr"), ("vb", "tr"), ("m", "tr"),
    ("masa", "tr"), ("Ankara", "tr"), ("kendi", "tr"), ("weekend", "en"),
    ("Bluetooth", "en"), ("Wi-Fi", "en"), ("Spotify", "en"), ("Ankara'da", "tr"),
])
def test_latin_word_lang(word, lang):
    assert latin_word_lang(word, "tr") == lang
    assert word_lang(word, "tr") == lang


def test_word_lists_are_consistent():
    native, english = load_words("tr", "native"), load_words("latin", "english")
    for w in ("her", "on", "model"):
        assert w in english and w in native


def test_ordinal_dot_does_not_end_a_sentence_in_tr():
    assert split_sentences_raw("Yarışta 2. olduk. Sonra 3. Ve bitti.", "tr") == [
        "Yarışta 2. olduk.", "Sonra 3.", "Ve bitti."]
    assert split_sentences_raw("Yarışta 2. olduk.") == ["Yarışta 2.", "olduk."]


def test_turkish_sentence():
    assert ph("Merhaba, nasılsın?") == "m e1 r h a b a , n a1 s I l s I n ?"
    assert ph("Ev çok güzel.") == "e1 v _ ch o1 k _ g ue z e1 l ."
    assert "EN:" not in " ".join(flat("Çocuklar bahçede top oynuyor."))


def test_mixed_tr_en():
    toks = flat("GitHub'ı aç ve projeyi bul.")
    assert "EN:G" in toks and "TR:ch" in toks and toks[-1] == "."
    i = toks.index("TR:I")
    assert toks[i - 1] == " "  # the suffix after the English word is its own Turkish word


def test_numbers_and_codes_in_turkish():
    assert flat("21 yaşındayım.") == flat("yirmi bir yaşındayım.")
    assert flat("ESP32-P4") == flat("e se pe üç iki pe dört")
    assert flat("saat 7:30'da") == flat("saat yedi otuzda")


def test_ids_use_tren_set_and_english_ids_match_v2():
    ids = text_to_ids("GitHub'ı aç, lütfen.", "tr")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("tr-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_TREN)
    assert text_to_ids("Close the door.", "en") == text_to_ids("Close the door.", "tr")


def test_other_modes_unchanged_by_turkish():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, çok güzel hello", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    assert word_lang("güzel", "vi") == "vi"
    assert tag_words("Abre l'app", "es")[1] == ("l'app", "en")


def test_long_turkish_text_is_chunked():
    one = "komşumun köpeği her sabah parkta koşuyor ve çok mutlu görünüyor"
    chunks = text_to_tokens(" ".join([one] * 12) + ".", "tr")
    assert len(chunks) > 1 and all(len(c) <= 318 for c in chunks)
