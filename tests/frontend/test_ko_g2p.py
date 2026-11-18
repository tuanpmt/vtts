"""Token set ko-en, Hangul decomposition and the standard pronunciation rules (표준 발음법)."""

import pytest

from vtts.frontend.ko.g2p_ko import (
    apply_overrides,
    pronounce,
    pronounce_text,
    syllable_tokens,
    word_tokens_ko,
)
from vtts.frontend.ko.hangul import compose, decompose, is_hangul_syllable
from vtts.frontend.lexicons import load_table
from vtts.frontend.phoneme_set import (
    KO_CODAS,
    KO_ONSETS,
    KO_VOWELS,
    TOKEN_SET_KOEN,
    TOKEN_SETS,
    TOKENS_KOEN,
    TOKENS_V2,
    TOKENS_ZHEN,
    VOCAB_SIZE_KOEN,
    token_to_id_koen,
    token_to_id_v2,
)

# ---------------- token set ----------------


def test_v2_ids_unchanged():
    assert TOKENS_KOEN[:107] == TOKENS_V2
    assert all(token_to_id_koen(t) == token_to_id_v2(t) for t in TOKENS_V2)


def test_korean_block():
    block = TOKENS_KOEN[107:]
    assert len(KO_ONSETS) == 18 and len(KO_VOWELS) == 21 and len(KO_CODAS) == 7
    assert len(block) == len(set(block)) == 46 and VOCAB_SIZE_KOEN == 153
    assert len(set(TOKENS_KOEN)) == VOCAB_SIZE_KOEN <= 256
    assert block[0] == "KO:I:g" and block[-1] == "KO:C:ng"
    assert {"KO:I:kk", "KO:V:ya", "KO:V:ui", "KO:C:l"} <= set(block)
    assert all(t.isascii() for t in block)
    assert TOKEN_SETS[TOKEN_SET_KOEN] is TOKENS_KOEN and TOKEN_SET_KOEN == "ko-en"
    assert not set(block) & set(TOKENS_ZHEN)


# ---------------- decomposition ----------------


@pytest.mark.parametrize("ch, parts", [
    ("가", ("ㄱ", "ㅏ", "")), ("한", ("ㅎ", "ㅏ", "ㄴ")), ("닭", ("ㄷ", "ㅏ", "ㄺ")),
    ("아", ("ㅇ", "ㅏ", "")), ("힣", ("ㅎ", "ㅣ", "ㅎ")), ("넋", ("ㄴ", "ㅓ", "ㄳ")), ("꽤", ("ㄲ", "ㅙ", "")),
    ("의", ("ㅇ", "ㅢ", "")), ("값", ("ㄱ", "ㅏ", "ㅄ")),
])
def test_decompose(ch, parts):
    assert decompose(ch) == parts
    assert compose(*parts) == ch


def test_every_syllable_round_trips():
    for code in range(0xAC00, 0xD7A4):
        ch = chr(code)
        assert is_hangul_syllable(ch) and compose(*decompose(ch)) == ch
    assert not is_hangul_syllable("a") and not is_hangul_syllable("ㄱ")


def test_syllable_tokens():
    assert syllable_tokens(("ㅎ", "ㅏ", "ㄱ")) == ["KO:I:h", "KO:V:a", "KO:C:k"]
    assert syllable_tokens(("ㅇ", "ㅘ", "ㅇ")) == ["KO:V:wa", "KO:C:ng"]   # silent ㅇ omitted
    assert syllable_tokens(("ㄲ", "ㅢ", "")) == ["KO:I:kk", "KO:V:ui"]


# ---------------- pronunciation rules (at least 3 standard examples each) ----------------

RULES = {
    "liaison": [("한국어", "한구거"), ("옷을", "오슬"), ("밖에", "바께"), ("있어", "이써"),
                ("꽃이", "꼬치"), ("음악", "으막")],
    "double_coda_liaison": [("앉아", "안자"), ("닭이", "달기"), ("젊어", "절머"), ("값을", "갑쓸"),
                            ("넋이", "넉씨"), ("핥아", "할타"), ("읊어", "을퍼")],
    "coda_neutralization": [("부엌", "부억"), ("옷", "옫"), ("낮", "낟"), ("꽃", "꼳"),
                            ("앞", "압"), ("밖", "박"), ("있다", "읻따")],
    "double_coda": [("닭", "닥"), ("값", "갑"), ("앉다", "안따"), ("넓다", "널따"), ("읽다", "익따"),
                    ("젊다", "점따"), ("읽고", "일꼬"), ("맑게", "말께"), ("없다", "업따")],
    "nasalization": [("국물", "궁물"), ("십만", "심만"), ("닫는", "단는"), ("밥물", "밤물"),
                     ("옷만", "온만"), ("읽는", "잉는"), ("없는", "엄는"),
                     ("감사합니다", "감사함니다")],
    "l_to_n": [("담력", "담녁"), ("종로", "종노"), ("강릉", "강능"), ("독립", "동닙"),
               ("법률", "범뉼"), ("백리", "뱅니")],
    "liquidization": [("신라", "실라"), ("난로", "날로"), ("천리", "철리"), ("칼날", "칼랄"),
                      ("설날", "설랄"), ("물난리", "물랄리")],
    "aspiration": [("축하", "추카"), ("좋다", "조타"), ("입학", "이팍"), ("많고", "만코"),
                   ("못하다", "모타다"), ("싫지", "실치"), ("밝히다", "발키다"), ("앉히다", "안치다")],
    "h_deletion": [("좋아", "조아"), ("많아", "마나"), ("싫어", "시러"), ("놓은", "노은")],
    "h_other": [("닿소", "다쏘"), ("놓는", "논는"), ("않네", "안네"), ("뚫는", "뚤른")],
    "tensification": [("학교", "학꾜"), ("국밥", "국빱"), ("꽃다발", "꼳따발"), ("있던", "읻떤"),
                      ("옆집", "엽찝"), ("입구", "입꾸"), ("있습니다", "읻씀니다")],
    "palatalization": [("같이", "가치"), ("굳이", "구지"), ("해돋이", "해도지"), ("밭이", "바치"),
                       ("닫히다", "다치다"), ("핥이다", "할치다")],
    "vowels": [("희망", "히망"), ("무늬", "무니"), ("가져", "가저"), ("다쳐", "다처"),
               ("의사", "의사")],
}
CASES = [(rule, w, p) for rule, pairs in RULES.items() for w, p in pairs]


@pytest.mark.parametrize("rule, word, pron", CASES, ids=[f"{r}-{w}" for r, w, _ in CASES])
def test_rule(rule, word, pron):
    assert pronounce_text(word) == pron


def test_rules_stay_inside_a_word():
    assert pronounce_text("옷 안") == "옫 안"          # no liaison across the space
    assert pronounce_text("국 물") == "국 물"


# ---------------- exceptions (lexicons/ko/overrides.tsv) ----------------


@pytest.mark.parametrize("word, pron", [
    ("신라의", "실라의"),                  # rule, no entry
    ("의견란", "의견난"),                  # ㄴ+ㄹ read ㄴㄴ (exception to liquidization)
    ("생산량", "생산냥"),
    ("갈등", "갈뜽"), ("발전", "발쩐"),     # Sino-Korean ㄹ + ㄷㅅㅈ tensified
    ("김밥", "김빱"), ("물고기", "물꼬기"),  # 사잇소리
    ("솜이불", "솜니불"), ("색연필", "생년필"),  # ㄴ insertion
    ("맛없다", "마덥따"),                  # coda neutralized before a real morpheme
    ("닭고기", "닥꼬기"), ("밟다", "밥따"), ("밟아", "발바"),
    ("물고기를", "물꼬기를"), ("총생산량", "총생산냥"),  # entries match inside longer words
])
def test_overrides(word, pron):
    assert pronounce_text(word) == pron


def test_override_entries_are_hangul_and_spelled_as_pronounced():
    table = load_table("ko", "overrides")
    assert len(table) >= 40
    for key, reading in table.items():
        assert len(key) >= 2 and all(is_hangul_syllable(c) for c in key + reading), key
        # a reading is written as pronounced: the rules leave it unchanged
        assert pronounce_text(reading) == reading, (key, reading)


def test_apply_overrides_longest_match():
    table = {"ab": "XY", "abc": "QRS"}
    assert apply_overrides("abcd", table) == "QRSd"
    assert apply_overrides("zab", table) == "zXY"


def test_word_tokens():
    assert word_tokens_ko("학교") == ["KO:I:h", "KO:V:a", "KO:C:k", "KO:I:kk", "KO:V:yo"]
    assert word_tokens_ko("안녕") == ["KO:V:a", "KO:C:n", "KO:I:n", "KO:V:yeo", "KO:C:ng"]
    assert word_tokens_ko("abc") == []
    assert len(pronounce("한국어")) == 3


def test_unreadable_ko():
    from vtts.frontend.ko.g2p_ko import unreadable_ko

    assert unreadable_ko("Wi-Fi를 켜 주세요, 3개.") == []
    assert unreadable_ko("한강(漢江) ㅋㅋ") == ["漢", "江", "ㅋ", "ㅋ"]
