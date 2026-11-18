"""Mandarin reading tables (lexicons/zh) and forward maximum matching."""

import pytest

from vtts.frontend.lexicons import load_table
from vtts.frontend.zh.g2p_zh import char_table, is_han, phrase_table, read_han, unknown_han
from vtts.frontend.zh.pinyin import syllable_tokens


@pytest.mark.parametrize("text, reading", [
    ("银行", "yin2 hang2"),
    ("行走", "xing2 zou3"),
    ("行", "xing2"),
    ("重要", "zhong4 yao4"),
    ("重新", "chong2 xin1"),
    ("东西", "dong1 xi1"),          # pypinyin's data has no neutral-tone entry for 东西
    ("我们的", "wo3 men5 de5"),
    ("长大", "zhang3 da4"),
    ("音乐", "yin1 yue4"),
    ("快乐", "kuai4 le4"),
    ("了解", "liao3 jie3"),
    ("银行行长", "yin2 hang2 hang2 zhang3"),
    ("一个", "yi1 ge4"),             # citation tones: no sandhi in version 1
    ("不对", "bu4 dui4"),
])
def test_readings(text, reading):
    assert " ".join(read_han(text)) == reading


def test_forward_maximum_matching_prefers_longest_phrase():
    chars = {"a": "a1", "b": "b1", "c": "c1"}
    phrases = {"ab": ("x1", "y1"), "abc": ("p1", "q1", "r1")}
    assert read_han("abcab", chars, phrases) == ["p1", "q1", "r1", "x1", "y1"]
    assert read_han("cxa", chars, phrases) == ["c1", "a1"]   # unknown characters are skipped


def test_unknown_han():
    assert unknown_han("你好abc") == []
    assert unknown_han("込む") == ["込"]


def test_tables_load_and_readings_are_valid():
    chars = char_table()
    phrases = phrase_table()
    assert 6763 <= len(chars) <= 9000 and 1000 <= len(phrases) <= 20000
    for ch, syl in chars.items():
        assert len(ch) == 1 and is_han(ch), ch
        assert syllable_tokens(syl), f"chars.tsv: {ch} -> {syl}"
    for phrase, syls in phrases.items():
        assert 2 <= len(phrase) <= 4 and len(syls) == len(phrase), phrase
        assert all(ch in chars for ch in phrase), phrase
        assert all(syllable_tokens(s) for s in syls), phrase


def test_phrase_table_holds_only_needed_entries():
    """Every entry changes the reading of its own phrase (dropping it would change the output)."""
    chars, phrases = char_table(), phrase_table()
    for phrase, syls in list(phrases.items())[::50]:
        without = {k: v for k, v in phrases.items() if k != phrase}
        assert tuple(read_han(phrase, chars, without)) != syls, phrase


def test_overrides_are_valid():
    for key, reading in load_table("zh", "overrides").items():
        assert len(reading.split()) == len(key) and all(map(syllable_tokens, reading.split()))
