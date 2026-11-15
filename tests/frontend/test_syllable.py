import unicodedata

import pytest

from vtts.frontend.syllable import Syllable as S
from vtts.frontend.syllable import parse_syllable

CASES = [
    ("ba", S("b", False, "a", None, 1)),
    ("mà", S("m", False, "a", None, 2)),
    ("quốc", S("k", True, "ô", "c", 3)),
    ("nghiêng", S("ng", False, "iê", "ng", 1)),
    ("gì", S("gi", False, "i", None, 2)),
    ("giếng", S("gi", False, "iê", "ng", 3)),
    ("gia", S("gi", False, "a", None, 1)),
    ("trường", S("tr", False, "ươ", "ng", 2)),
    ("chuyện", S("ch", True, "iê", "n", 6)),
    ("khuya", S("kh", True, "iê", None, 1)),
    ("mua", S("m", False, "uô", None, 1)),
    ("mưa", S("m", False, "ươ", None, 1)),
    ("hòa", S("h", True, "a", None, 2)),
    ("tay", S("t", False, "ă", "j", 1)),
    ("tai", S("t", False, "a", "j", 1)),
    ("sáu", S("s", False, "ă", "w", 3)),
    ("sao", S("s", False, "a", "w", 1)),
    ("ăn", S(None, False, "ă", "n", 1)),
    ("yêu", S(None, False, "iê", "w", 1)),
    ("ý", S(None, False, "i", None, 3)),
    ("đã", S("đ", False, "a", None, 5)),
    ("nặng", S("n", False, "ă", "ng", 6)),
    ("xoong", S("x", False, "oo", "ng", 1)),
    ("rồi", S("r", False, "ô", "j", 2)),
    ("dạ", S("d", False, "a", None, 6)),
    ("kê", S("k", False, "ê", None, 1)),
    ("ghế", S("g", False, "ê", None, 3)),
    ("khuỷu", S("kh", True, "i", "w", 4)),
]


@pytest.mark.parametrize("word,expected", CASES, ids=[c[0] for c in CASES])
def test_syllable_cases(word, expected):
    assert parse_syllable(word) == expected


def test_tone_placement_and_case_insensitive():
    ref = parse_syllable("hòa")
    assert ref is not None
    assert parse_syllable("hoà") == ref
    assert parse_syllable("HÒA") == ref
    assert parse_syllable(unicodedata.normalize("NFD", "hòa")) == ref


@pytest.mark.parametrize("word", ["wifi", "email", "abc", "xyz", "", "b"])
def test_rejects_non_vietnamese(word):
    assert parse_syllable(word) is None


def test_tone_marks_ignore_order():
    # "ấ" written as a + acute + circumflex (tone before quality mark)
    odd = "l" + "a" + "́" + "̂" + "y"
    assert parse_syllable(odd) == parse_syllable("lấy")
