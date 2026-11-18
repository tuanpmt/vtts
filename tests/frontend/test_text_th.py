"""text_to_ids(text, "th"): Thai + English, token set th-en."""

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_THEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="th"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def test_tagging_thai_and_english():
    assert tag_words("ช่วยเปิดWi-Fiให้หน่อย", "th") == [
        ("ช่วยเปิด", "th"), ("Wi-Fi", "en"), ("ให้หน่อย", "th")]
    assert tag_words("เปิด Netflix 2 ชั่วโมง", "th") == [
        ("เปิด", "th"), ("Netflix", "en"), ("2", "neutral"), ("ชั่วโมง", "th")]
    assert word_lang("สวัสดี", "th") == "th" and word_lang("hello", "th") == "en"


def test_other_modes_unchanged_by_thai():
    assert word_lang("สวัสดี", "vi") == "vi"  # as before: any non-ASCII letter
    assert word_lang("สวัสดี", "zh") == "neutral"
    assert tag_words("打开Wi-Fi设置", "zh") == [("打开", "zh"), ("Wi-Fi", "en"), ("设置", "zh")]
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, สวัสดี", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2


def test_thai_run_has_no_space_between_syllables():
    toks = flat("สวัสดีครับ")
    assert " " not in toks and toks.count("TH:T2") == 2
    assert toks[:3] == ["TH:I:s", "TH:V:a", "TH:T2"]


def test_space_between_thai_clauses_is_a_pause():
    toks = flat("ไม่ตอบสนองเลย ช่วยดูให้หน่อย")
    assert toks.count(",") == 1 and " " not in toks


def test_mixed_th_en():
    toks = flat("ช่วยเปิด Wi-Fi ให้หน่อย")
    assert "EN:W" in toks and toks.count(" ") == 3 and toks[-1] == "TH:T2"
    assert flat("ช่วยเปิดWi-Fiให้หน่อย") == toks


def test_numbers_in_thai():
    assert flat("มี 21 คน") == flat("มียี่สิบเอ็ดคน")
    assert flat("๑๐๑") == flat("หนึ่งร้อยเอ็ด")
    assert flat("เวลา 14:30 น.") == flat("เวลาสิบสี่นาฬิกาสามสิบนาที")


def test_abbreviation_dot_does_not_end_a_sentence():
    assert split_sentences_raw("ปี พ.ศ. 2567 ครับ") == ["ปี พ.ศ. 2567 ครับ"]
    assert split_sentences_raw("Hello there. Bye.") == ["Hello there.", "Bye."]


def test_ids_use_then_set_and_english_ids_match_v2():
    ids = text_to_ids("เปิด YouTube ให้หน่อย", "th")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("th-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_THEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "th")


def test_long_thai_text_is_chunked():
    one = "เมื่อวานนี้ฉันไปเที่ยวทะเลกับครอบครัวและเพื่อนสนิทหลายคน"
    chunks = text_to_tokens(" ".join([one] * 6), "th")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    long = one * 6  # no space at all: cut by the syllable limit
    chunks = text_to_tokens(long, "th")
    assert len(chunks) > 1 and all(sum(t.startswith("TH:T") for t in c) <= 40 for c in chunks)
