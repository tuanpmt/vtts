import json
from pathlib import Path

from vtts.frontend.lang import sentence_lang, tag_words
from vtts.frontend.phoneme_set import TOKENS_V2, VOCAB_SIZE, token_to_id_v2
from vtts.frontend.text import text_to_ids, text_to_tokens

FIXTURE = Path(__file__).parents[1] / "fixtures" / "text_ids_v1.json"


def langs(text, mode="vi"):
    return [(w, l) for w, l in tag_words(text, mode) if l != "neutral"]


def test_tagging_in_vietnamese_mode():
    tags = dict(langs("Đã kết nối Bluetooth với AirPods."))
    assert tags["Bluetooth"] == "en" and tags["AirPods."] == "en"
    assert tags["Đã"] == "vi" and tags["kết"] == "vi" and tags["với"] == "vi"


def test_unaccented_vietnamese_stays_vietnamese():
    assert all(l == "vi" for _, l in langs("xin chao ban"))


def test_loanwords_and_acronyms_stay_vietnamese():
    tags = dict(langs("Bật wifi và cắm USB"))
    assert tags["wifi"] == "vi" and tags["USB"] == "vi"


def test_sentence_lang_auto():
    assert sentence_lang("Hôm nay trời đẹp quá.", "auto") == "vi"
    assert sentence_lang("The weather is nice today.", "auto") == "en"
    assert sentence_lang("Turn on the light.", "vi") == "vi"


def test_v1_path_unchanged():
    snap = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for text, ids in snap.items():
        assert text_to_ids(text) == ids, text


def test_vietnamese_sentence_same_ids_in_v2():
    s = "Hôm nay là ngày 16/11, nhiệt độ 28 độ."
    assert text_to_ids(s, "vi") == text_to_ids(s)


def test_english_words_with_punctuation_are_not_spelled():
    toks = [t for ch in text_to_tokens("Wi-Fi, Apple's state-of-the-art phone.", "en") for t in ch]
    assert "EN:AE" in toks and "," in toks and "." in toks
    assert not any(t.startswith(("O:", "N:", "T")) for t in toks)


def test_numbers_follow_sentence_language():
    vi = [t for ch in text_to_tokens("iPhone 15 có giá 20 triệu", "vi") for t in ch]
    en = [t for ch in text_to_tokens("iPhone 15 costs $799", "en") for t in ch]
    assert "EN:AY" in vi and "T3" in vi            # "i" English, "mười lăm" Vietnamese
    assert not any(t.startswith("T") and t[1:].isdigit() for t in en)


def test_mixed_sentence_ids_in_range():
    ids = text_to_ids("Đã kết nối Bluetooth với AirPods, pin còn 80%.", "vi")
    flat = [i for ch in ids for i in ch]
    assert any(i >= VOCAB_SIZE for i in flat) and max(flat) < len(TOKENS_V2)
    assert all(ch[0] == token_to_id_v2("<bos>") and ch[-1] == token_to_id_v2("<eos>") for ch in ids)


def test_long_english_run_is_chunked_without_loss():
    text = " ".join(["information"] * 400)
    chunks = text_to_tokens(text, "en")
    assert all(len(c) + 2 <= 320 for c in chunks)
    assert sum(c.count("EN:F") for c in chunks) == 400
