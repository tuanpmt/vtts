"""text_to_ids(text, "zh"): Mandarin + English, token set zh-en."""

from vtts.frontend.lang import split_scripts, split_sentences_raw, tag_words
from vtts.frontend.phoneme_set import TOKENS_ZHEN, VOCAB_SIZE_V2, token_to_id_zhen
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="zh"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def test_script_boundaries():
    assert split_scripts("打开Wi-Fi设置。") == "打开 Wi-Fi 设置 。"
    tags = [(w, l) for w, l in tag_words("打开Wi-Fi设置", "zh")]
    assert tags == [("打开", "zh"), ("Wi-Fi", "en"), ("设置", "zh")]


def test_sentences_split_after_chinese_marks_without_space():
    assert split_sentences_raw("你好！今天好吗？好。") == ["你好！", "今天好吗？", "好。"]
    assert split_sentences_raw("Xin chào. Bạn khỏe không?") == ["Xin chào.", "Bạn khỏe không?"]


def test_chinese_run_has_no_space_between_syllables():
    assert flat("银行") == ["ZF:in", "ZT2", "ZI:h", "ZF:ang", "ZT2"]
    assert flat("你好，世界。") == ["ZI:n", "ZF:i", "ZT3", "ZI:h", "ZF:ao", "ZT3", ",",
                                "ZI:sh", "ZF:ii", "ZT4", "ZI:j", "ZF:ie", "ZT4", "."]


def test_mixed_zh_en():
    toks = flat("打开Wi-Fi设置")
    i = toks.index("EN:W")
    assert toks[:i] == ["ZI:d", "ZF:a", "ZT3", "ZI:k", "ZF:ai", "ZT1", " "]
    assert toks[-7:] == [" ", "ZI:sh", "ZF:e", "ZT4", "ZI:zh", "ZF:ii", "ZT4"]
    toks = flat("请发 email 给我")
    assert toks.count(" ") == 2 and "EN:M" in toks
    toks = flat("打开 Wi-Fi，然后重启。")      # the comma after the English word is kept
    assert toks[toks.index("EN:AY") + 2] == "," and toks[-1] == "."
    assert flat("，你好")[0] == "ZI:n"            # a mark that follows nothing is dropped


def test_english_words_are_separated_by_space():
    toks = flat("打开 smart home 模式")
    assert toks.count(" ") == 3


def test_numbers_and_codes_in_chinese():
    toks = flat("ESP32-P4有2个核")
    assert toks[:2] == ["EN:IY", "S1"]                     # letters spelled in English
    assert ["ZI:s", "ZF:an", "ZT1", "ZF:er", "ZT4"] == toks[toks.index("ZI:s"):][:5]  # 三二


def test_ids_use_zhen_set_and_english_ids_match_v2():
    ids = text_to_ids("打开Wi-Fi设置。", "zh")
    flat_ids = [i for ch in ids for i in ch]
    assert ids[0][0] == token_to_id_zhen("<bos>") and ids[0][-1] == token_to_id_zhen("<eos>")
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_ZHEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "zh")


def test_vi_mode_ignores_han_as_before():
    """Han text in a vi-en mode is handled as before (no zh-en tokens)."""
    ids = [i for ch in text_to_ids("Xin chào 你好", "vi") for i in ch]
    assert max(ids) < VOCAB_SIZE_V2


def test_long_chinese_text_is_chunked():
    text = "我们今天去公园散步然后回家吃饭" * 30 + "。"
    chunks = text_to_tokens(text, "zh")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    assert all(sum(t.startswith("ZT") for t in c) <= 40 for c in chunks)
    assert sum(t.startswith("ZT") for c in chunks for t in c) == 15 * 30
    assert all(" " not in c for c in chunks)
