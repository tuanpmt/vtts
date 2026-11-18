"""text_to_ids(text, "hi"): Hindi + English, token set hi-en."""

from pathlib import Path

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_HIEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens

TEMPLATES = Path(__file__).resolve().parents[2] / "scripts" / "data" / "bilingual" / "templates_hi.txt"


def flat(text, lang="hi"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("HI:") for t in flat(text))


def test_tagging_devanagari_and_latin_words():
    assert tag_words("मुझे YouTube पर वीडियो देखना है।", "hi") == [
        ("मुझे", "hi"), ("YouTube", "en"), ("पर", "hi"), ("वीडियो", "hi"), ("देखना", "hi"),
        ("है।", "hi")]
    assert word_lang("Wi-Fi", "hi") == "en" and word_lang("ESP32", "hi") == "neutral"
    assert word_lang("km", "hi") == "hi" and word_lang("GB", "hi") == "hi"  # units of the normalizer


def test_hindi_sentence():
    assert ph("नमस्ते, आप कैसे हैं?") == "n a m a s t e , aa p _ k ai s e _ h ai ~ ?"
    assert "EN:" not in " ".join(flat("मैं कल सुबह बाज़ार जाऊँगा और सब्ज़ी लाऊँगा।"))


def test_danda_ends_a_sentence():
    assert split_sentences_raw("मैं घर जा रहा हूँ। तुम कहाँ हो॥ ठीक है") == [
        "मैं घर जा रहा हूँ।", "तुम कहाँ हो॥", "ठीक है"]
    chunks = text_to_tokens("मैं घर जा रहा हूँ। तुम कहाँ हो?", "hi")
    assert len(chunks) == 2 and chunks[0][-1] == "." and chunks[1][-1] == "?"


def test_mixed_hi_en():
    toks = flat("मैंने laptop पर software update कर दिया।")
    assert "EN:AE" in toks and "HI:m" in toks and toks[-1] == "."
    assert flat("Wi-Fi को चालू करो।")[:len(flat("Wi-Fi", "en"))] == flat("Wi-Fi", "en")
    assert flat("मेरा फ़ोन 5G है") == flat("मेरा फ़ोन पाँच जी है")


def test_numbers_in_hindi():
    assert flat("मेरी उम्र 21 साल है।") == flat("मेरी उम्र इक्कीस साल है।")
    assert flat("मेरी उम्र २१ साल है।") == flat("मेरी उम्र इक्कीस साल है।")
    assert flat("7:30 पर मिलते हैं") == flat("सात बजकर तीस मिनट पर मिलते हैं")


def test_ids_use_hien_set_and_english_ids_match_v2():
    ids = text_to_ids("YouTube खोलो, please.", "hi")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("hi-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_HIEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "hi")


def test_other_modes_unchanged_by_hindi():
    for mode in ("vi", "en", "auto", "es", "pt"):
        assert word_lang("नमस्ते", mode) != "hi"
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, नमस्ते", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2


def test_templates_are_readable():
    from vtts.data.train_list import unreadable

    for line in TEMPLATES.read_text(encoding="utf-8").splitlines():
        text = line.replace("{T}", "Bluetooth")
        assert not unreadable(text, "hi"), text
        toks = flat(text)
        assert any(t.startswith("HI:") for t in toks) and "EN:UW" in toks, text


def test_long_hindi_text_is_chunked():
    one = "हम हर रविवार को पार्क में घूमने जाते हैं और वहाँ बच्चों के साथ खेलते हैं"
    text = " ".join([one] * 12) + "।"
    chunks = text_to_tokens(text, "hi")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    words = [sum(1 for t in c if t == " ") + 1 for c in chunks]
    assert all(w <= 40 for w in words)
