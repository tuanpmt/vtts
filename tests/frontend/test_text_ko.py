"""text_to_ids(text, "ko"): Korean + English, token set ko-en."""

from vtts.frontend.lang import split_sentences_raw, tag_words
from vtts.frontend.phoneme_set import TOKENS_KOEN, VOCAB_SIZE_V2, token_to_id_koen
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="ko"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def test_tagging():
    assert tag_words("Wi-Fi를 켜 주세요", "ko") == [("Wi-Fi를", "ko"), ("켜", "ko"), ("주세요", "ko")]
    assert tag_words("smart home 모드", "ko") == [("smart", "en"), ("home", "en"), ("모드", "ko")]
    assert tag_words("ESP32-P4 보드", "ko") == [("ESP32-P4", "neutral"), ("보드", "ko")]


def test_words_are_separated_by_space_and_rules_apply_inside():
    assert flat("국물 좋아.") == ["KO:I:g", "KO:V:u", "KO:C:ng", "KO:I:m", "KO:V:u", "KO:C:l", " ",
                                "KO:I:j", "KO:V:o", "KO:V:a", "."]
    assert split_sentences_raw("안녕하세요. 반갑습니다!") == ["안녕하세요.", "반갑습니다!"]


def test_mixed_ko_en():
    toks = flat("스마트폰에서 Bluetooth를 켜세요.")
    assert "EN:B" in toks and "EN:TH" in toks
    i = toks.index("EN:B")
    assert toks[i - 1] == " " and toks[-1] == "."
    assert flat("Wi-Fi를")[-4:] == [" ", "KO:I:r", "KO:V:eu", "KO:C:l"]
    toks = flat("turn on the light 해 주세요")
    assert toks.count(" ") == 5 and toks[0].startswith("EN:")


def test_numbers_and_codes():
    toks = flat("ESP32-P4는 코어가 2개입니다.")
    assert toks[:2] == ["EN:IY", "S1"]                        # letters spelled in English
    assert "EN:TH" in toks                                    # "three" in English
    assert ["KO:I:d", "KO:V:u"] == toks[toks.index("KO:I:d"):][:2]  # 두 개
    assert flat("9시 30분") == flat("아홉 시 삼십 분")
    assert flat("2026년 6월 10일") == flat("이천이십육년 유월 십일")


def test_ids_use_koen_set_and_english_ids_match_v2():
    ids = text_to_ids("Wi-Fi를 켜 주세요.", "ko")
    flat_ids = [i for ch in ids for i in ch]
    assert ids[0][0] == token_to_id_koen("<bos>") and ids[0][-1] == token_to_id_koen("<eos>")
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_KOEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "ko")


def test_other_modes_ignore_hangul_as_before():
    for mode in ("vi", "en", "auto", "zh"):
        ids = [i for ch in text_to_ids("Xin chào 안녕하세요 hello", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2


def test_long_korean_text_is_chunked():
    text = " ".join(["오늘은 날씨가 정말 좋아서 공원에 산책하러 갔습니다"] * 30) + "."
    chunks = text_to_tokens(text, "ko")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    assert all(c.count(" ") + 1 <= 40 for c in chunks)
    one = len(flat("오늘은 날씨가 정말 좋아서 공원에 산책하러 갔습니다"))
    assert sum(len(c) - c.count(" ") for c in chunks) == 30 * (one - 6) + 1  # + final "."


def test_long_word_chunk_limit():
    text = "가나다라마바사아자차카타파하" * 40 + "."
    chunks = text_to_tokens(text, "ko")
    assert all(len(c) + 2 <= 320 for c in chunks)
