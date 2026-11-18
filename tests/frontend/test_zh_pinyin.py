"""Token set zh-en and numbered pinyin -> [ZI] ZF ZT tokens."""

import pytest

from vtts.frontend.phoneme_set import (
    TOKEN_SET_ZHEN,
    TOKEN_SETS,
    TOKENS_V2,
    TOKENS_ZHEN,
    VOCAB_SIZE_V2,
    VOCAB_SIZE_ZHEN,
    ZH_FINALS,
    ZH_INITIALS,
    token_to_id_v2,
    token_to_id_zhen,
)
from vtts.frontend.zh.pinyin import split_syllable, syllable_tokens


def test_v2_ids_unchanged():
    assert VOCAB_SIZE_V2 == 107
    assert TOKENS_ZHEN[:107] == TOKENS_V2
    assert all(token_to_id_zhen(t) == token_to_id_v2(t) for t in TOKENS_V2)


def test_mandarin_block():
    block = TOKENS_ZHEN[107:]
    assert len(block) == len(set(block)) == len(ZH_INITIALS) + len(ZH_FINALS) + 5
    assert len(set(TOKENS_ZHEN)) == VOCAB_SIZE_ZHEN <= 256
    assert block[0] == "ZI:b" and block[-1] == "ZT5"
    assert {"ZI:zh", "ZF:iang", "ZF:ii", "ZF:i0", "ZF:v", "ZT3"} <= set(block)
    assert TOKEN_SETS[TOKEN_SET_ZHEN] is TOKENS_ZHEN and TOKEN_SET_ZHEN == "zh-en"


@pytest.mark.parametrize("syl, parts", [
    # plain finals and nasal codas
    ("ba", ("b", "a")), ("bo", ("b", "o")), ("ge", ("g", "e")), ("lai", ("l", "ai")),
    ("mei", ("m", "ei")), ("hao", ("h", "ao")), ("dou", ("d", "ou")), ("kan", ("k", "an")),
    ("ren", ("r", "en")), ("tang", ("t", "ang")), ("deng", ("d", "eng")),
    ("zhong", ("zh", "ong")), ("er", ("", "er")), ("a", ("", "a")), ("ou", ("", "ou")),
    # i- finals
    ("ni", ("n", "i")), ("jia", ("j", "ia")), ("xie", ("x", "ie")), ("niao", ("n", "iao")),
    ("liu", ("l", "iou")), ("tian", ("t", "ian")), ("lin", ("l", "in")),
    ("liang", ("l", "iang")), ("ming", ("m", "ing")), ("xiong", ("x", "iong")),
    # u- finals
    ("lu", ("l", "u")), ("hua", ("h", "ua")), ("duo", ("d", "uo")), ("kuai", ("k", "uai")),
    ("gui", ("g", "uei")), ("suan", ("s", "uan")), ("lun", ("l", "uen")),
    ("guang", ("g", "uang")),
    # u-umlaut finals
    ("nv", ("n", "v")), ("lve", ("l", "ve")), ("ju", ("j", "v")), ("que", ("q", "ve")),
    ("xuan", ("x", "van")), ("jun", ("j", "vn")), ("lü", ("l", "v")),
    # apical vowels
    ("zhi", ("zh", "ii")), ("chi", ("ch", "ii")), ("shi", ("sh", "ii")), ("ri", ("r", "ii")),
    ("zi", ("z", "i0")), ("ci", ("c", "i0")), ("si", ("s", "i0")),
    # zero initial y / w
    ("yi", ("", "i")), ("ya", ("", "ia")), ("ye", ("", "ie")), ("yao", ("", "iao")),
    ("you", ("", "iou")), ("yan", ("", "ian")), ("yin", ("", "in")), ("yang", ("", "iang")),
    ("ying", ("", "ing")), ("yong", ("", "iong")), ("yu", ("", "v")), ("yue", ("", "ve")),
    ("yuan", ("", "van")), ("yun", ("", "vn")),
    ("wu", ("", "u")), ("wa", ("", "ua")), ("wo", ("", "uo")), ("wai", ("", "uai")),
    ("wei", ("", "uei")), ("wan", ("", "uan")), ("wen", ("", "uen")), ("wang", ("", "uang")),
    ("weng", ("", "ueng")),
    # interjections map to regular syllables
    ("n", ("", "en")), ("ng", ("", "eng")), ("m", ("m", "u")), ("hng", ("h", "eng")),
    ("ê", ("", "ei")),
])
def test_split_syllable(syl, parts):
    assert split_syllable(syl) == parts


@pytest.mark.parametrize("bad", ["", "jo", "zhv", "xa", "bx", "ii", "yii"])
def test_invalid_syllables(bad):
    assert split_syllable(bad) is None


def test_syllable_tokens():
    assert syllable_tokens("hang2") == ["ZI:h", "ZF:ang", "ZT2"]
    assert syllable_tokens("wei4") == ["ZF:uei", "ZT4"]
    assert syllable_tokens("de5") == ["ZI:d", "ZF:e", "ZT5"]
    assert syllable_tokens("hang") is None and syllable_tokens("hang6") is None
    every_final = {f"ZF:{f}" for f in ZH_FINALS}
    assert all(t in TOKENS_ZHEN for t in every_final)
