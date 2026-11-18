"""Japanese reading tables (lexicons/ja) and forward longest-match segmentation (ja/g2p_ja.py)."""

import pytest

from vtts.frontend.ja.g2p_ja import (
    Tables,
    ja_phonemes,
    ja_reading,
    ja_units,
    segment,
    tables,
    unreadable_ja,
)
from vtts.frontend.ja.kana import kana_phonemes, to_katakana
from vtts.frontend.lexicons import load_table


def reading(text):
    return " ".join(ja_phonemes(text))


T = Tables.make({"東京": "トーキョー", "東京都": "トーキョート", "京都": "キョート", "国": "クニ",
                 "は": "ワ", "はじめ": "ハジメ", "シー": "スィー", "後に": "ノチニ", "人": "ヒト"},
                {"kanji": {"国": "コク", "後": "ゴ"}, "katakana": {"人": "ジン"}},
                {"東": "トー", "京": "キョー", "都": "ト", "米": "ベー", "国": "コク", "人": "ジン"})


def segs(text, t=T):
    return [(s.surface, s.reading, s.kind) for s in segment(text, t)]


def test_longest_match_first():
    assert segs("東京都に") == [("東京都", "トーキョート", "word"), ("に", "に", "kana")]
    assert segs("東京に") == [("東京", "トーキョー", "word"), ("に", "に", "kana")]


def test_kanji_defaults_and_unknown_kanji():
    assert segs("都") == [("都", "ト", "kanji")]
    assert segs("鬱") == [("鬱", "", "unknown")]
    assert segs("都々") == [("都", "ト", "kanji"), ("々", "ト", "kanji")]
    assert segs("人々") == [("人", "ヒト", "word"), ("々", "ヒト", "kanji")]
    assert segs("東京々") == [("東京", "トーキョー", "word"), ("々", "キョー", "kanji")]


def test_context_tables_win_after_a_kanji_or_katakana():
    assert segs("の国") == [("の", "の", "kana"), ("国", "クニ", "word")]
    assert segs("米国") == [("米", "ベー", "kanji"), ("国", "コク", "word")]
    assert segs("アメリカ人") == [("アメリカ", "アメリカ", "kana"), ("人", "ジン", "word")]
    assert segs("その人") == [("その", "その", "kana"), ("人", "ヒト", "word")]
    # a longer words.tsv key wins only when it is longer by more than kana
    assert segs("後に") == [("後に", "ノチニ", "word")]
    assert segs("米後に") == [("米", "ベー", "kanji"), ("後", "ゴ", "word"), ("に", "に", "kana")]


def test_kana_entries_and_katakana_words_read_as_written():
    assert segs("はじめは") == [("はじめ", "ハジメ", "word"), ("は", "ワ", "word")]
    assert segs("シーズン") == [("シーズン", "シーズン", "kana")]   # no entry inside katakana
    assert segs("シー") == [("シー", "スィー", "word")]


def test_units_split_long_kana_runs():
    units = ja_units("あ" * 25)
    assert [len(u) for u in units] == [10, 10, 5]
    assert all(t.startswith("JA:") for u in units for t in u)


def test_tables_are_well_formed():
    words, after_kanji, after_kata, kanji = (
        load_table("ja", n) for n in ("words", "after_kanji", "after_katakana", "kanji"))
    assert 30000 <= len(words) + len(after_kanji) + len(after_kata) <= 60000
    assert 2900 <= len(kanji) <= 3100 and all(len(k) == 1 for k in kanji)
    for table in (words, after_kanji, after_kata, kanji):
        for key, value in table.items():
            assert value == to_katakana(value) and kana_phonemes(value), (key, value)


@pytest.mark.parametrize("text, phonemes", [
    ("東京", "t o o ky o o"),
    ("今日", "ky o o"),                       # overrides.tsv
    ("今日は", "ky o o w a"),                  # particle は read ワ
    ("学校へ行きます", "g a cl k o o e i k i m a s u"),
    ("ありがとうございます", "a r i g a t o o g o z a i m a s u"),
    ("日本語", "n i h o N g o"),
    ("一日中", "i ch i n i ch i j u u"),
    ("大人気", "d a i n i N k i"),
    ("お母さん", "o k a a s a N"),
    ("食べました", "t a b e m a sh i t a"),
    ("コンピューター", "k o N py u u t a a"),
])
def test_common_readings(text, phonemes):
    assert reading(text) == phonemes


def test_one_reading_per_key_is_documented_limit():
    # 一日 is いちにち ("one day"); ついたち (first of the month) comes only from the date
    # normalizer (11月1日). The tables keep one reading per key.
    assert reading("一日") == "i ch i n i ch i"


def test_unreadable_ja():
    assert unreadable_ja("Wi-Fiを設定してください。３個") == []
    assert "龘" not in tables().kanji and unreadable_ja("龘は") == ["龘"]
    assert unreadable_ja("한국어") == ["한", "국", "어"]
    assert ja_reading("東京") == "トーキョー"
