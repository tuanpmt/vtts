"""text_to_ids(text, "ja"): Japanese + English, token set ja-en."""

from vtts.frontend.lang import _script_class_ja, split_scripts, split_sentences_raw, tag_words
from vtts.frontend.phoneme_set import TOKENS_JAEN, VOCAB_SIZE_V2, token_to_id_jaen
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="ja"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join(t.removeprefix("JA:") for t in flat(text))


def test_script_boundaries_and_tagging():
    assert split_scripts("Wi-Fiを設定。", _script_class_ja) == "Wi-Fi を設定 。"
    assert tag_words("Wi-Fiを設定してください", "ja") == [("Wi-Fi", "en"), ("を設定してください", "ja")]
    assert tag_words("smart homeモード", "ja") == [("smart", "en"), ("home", "en"), ("モード", "ja")]
    assert tag_words("ESP32-P4は", "ja") == [("ESP32-P4", "neutral"), ("は", "ja")]
    assert tag_words("東京", "ja") == [("東京", "ja")]          # kanji are Japanese in mode ja


def test_sentences_split_after_japanese_marks_without_space():
    assert split_sentences_raw("おはよう！元気？はい。") == ["おはよう！", "元気？", "はい。"]


def test_japanese_run_has_no_space_and_marks_map():
    assert ph("今日は、いい天気。") == "ky o o w a , i i t e N k i ."
    assert " " not in flat("東京駅で会いましょう")
    assert ph("本当？") .endswith("?") and ph("すごい！").endswith("!")


def test_mixed_ja_en():
    toks = flat("Wi-Fiを設定してください。")
    i = toks.index("JA:o")
    assert toks[i - 1] == " " and toks[0] == "EN:W" and toks[-1] == "."
    toks = flat("smart homeモードをオンにして")
    assert toks.count(" ") == 2 and "EN:HH" in toks
    toks = flat("このBluetoothスピーカー")
    assert toks.count(" ") == 2                    # space only around the English word


def test_numbers_and_codes():
    toks = flat("ESP32-P4は2個です。")
    assert toks[:2] == ["EN:IY", "S1"]              # letters and digits in English
    assert "EN:TH" in toks
    assert ph("2個") == "n i k o"
    assert ph("9時30分") == "k u j i s a N j u cl p u N"
    assert flat("2026年11月18日") == flat("ニセンニジューロクネンジューイチガツジューハチニチ")


def test_ids_use_jaen_set_and_english_ids_match_v2():
    ids = text_to_ids("Wi-Fiを設定してください。", "ja")
    flat_ids = [i for ch in ids for i in ch]
    assert ids[0][0] == token_to_id_jaen("<bos>") and ids[0][-1] == token_to_id_jaen("<eos>")
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_JAEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "ja")


def test_other_modes_unchanged_by_japanese():
    for mode in ("vi", "en", "auto", "ko"):
        ids = [i for ch in text_to_ids("Xin chào こんにちは 東京 hello", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    zh = [i for ch in text_to_ids("你好こんにちは", "zh") for i in ch]
    assert zh == [i for ch in text_to_ids("你好", "zh") for i in ch]   # kana skipped as before


def test_long_japanese_text_is_chunked():
    one = "今日は天気がとても良かったので、公園まで散歩に行きました"
    text = "".join([one] * 20) + "。"
    chunks = text_to_tokens(text, "ja")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    assert sum(1 for c in chunks for t in c if t.startswith("JA:")) == \
        20 * sum(1 for t in flat(one) if t.startswith("JA:"))


def test_long_kana_run_chunk_limit():
    text = "あいうえおかきくけこさしすせそ" * 40 + "。"
    chunks = text_to_tokens(text, "ja")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    assert sum(len(c) for c in chunks) == 25 * 40 + 1   # 15 vowels + 10 consonants per repeat
