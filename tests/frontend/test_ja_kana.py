"""Kana -> Japanese phonemes (ja/kana.py) and the ja-en token set."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.ja.kana import PAIRS, SINGLE, kana_phonemes, mora_count, to_hiragana


def ph(text: str) -> str:
    return " ".join(kana_phonemes(text))


def test_token_set_jaen_extends_v2():
    assert ps.TOKENS_JAEN[:107] == ps.TOKENS_V2
    assert len(set(ps.TOKENS_JAEN)) == len(ps.TOKENS_JAEN) == ps.VOCAB_SIZE_JAEN == 144
    assert all(t.startswith("JA:") for t in ps.TOKENS_JAEN[107:])
    assert ps.token_to_id_jaen("JA:a") == 107 and ps.token_to_id_jaen("EN:AA") == 65
    assert ps.token_to_id_jaen("JA:N") == 142 and ps.token_to_id_jaen("JA:cl") == 143
    assert ps.TOKEN_SETS[ps.TOKEN_SET_JAEN] is ps.TOKENS_JAEN
    with pytest.raises(KeyError):
        ps.token_to_id_jaen("ZF:a")


def test_every_kana_maps_into_the_inventory():
    inventory = {t[3:] for t in ps.TOKENS_JAEN[107:]}
    for phonemes in [*SINGLE.values(), *PAIRS.values()]:
        assert set(phonemes) <= inventory, phonemes


@pytest.mark.parametrize("kana, phonemes", [
    ("かきくけこ", "k a k i k u k e k o"),
    ("さしすせそ", "s a sh i s u s e s o"),
    ("たちつてと", "t a ch i ts u t e t o"),
    ("はひふへほ", "h a h i f u h e h o"),
    ("じぢずづ", "j i j i z u z u"),
    ("をん", "o N"),
    ("アイウエオ", "a i u e o"),                    # katakana = hiragana
    ("ゔ", "v u"),
])
def test_basic_kana(kana, phonemes):
    assert ph(kana) == phonemes


@pytest.mark.parametrize("kana, phonemes", [
    ("きゃきゅきょ", "ky a ky u ky o"),
    ("しゃしゅしょ", "sh a sh u sh o"),
    ("ちゃ じゃ にゃ ひゃ びゃ ぴゃ みゃ りゃ ぎゃ", "ch a j a ny a hy a by a py a my a ry a gy a"),
    ("ぁ", "a"),                                       # small kana alone
])
def test_small_kana_combinations(kana, phonemes):
    assert ph(kana) == phonemes


def test_sokuon_and_moraic_nasal():
    assert ph("がっこう") == "g a cl k o u"
    assert ph("きって") == "k i cl t e"
    assert ph("さんぽ") == "s a N p o"           # N stays one token before p/b/m ...
    assert ph("しんぶん") == "sh i N b u N"
    assert ph("さんま") == "s a N m a"
    assert ph("てんき") == "t e N k i"


def test_long_vowels():
    assert ph("コーヒー") == "k o o h i i"      # ー repeats the vowel
    assert ph("ラーメン") == "r a a m e N"
    assert ph("とう") == "t o u"                # a written vowel is read as spelled
    assert ph("ー") == ""                         # nothing to lengthen
    assert kana_phonemes("ー", "o") == ["o"]      # continues the previous segment's vowel


@pytest.mark.parametrize("kana, phonemes", [
    ("ティー", "t i i"), ("ディスク", "d i s u k u"), ("ファイル", "f a i r u"),
    ("フィルム", "f i r u m u"), ("フォーク", "f o o k u"), ("ウィンドウ", "w i N d o u"),
    ("ウェブ", "w e b u"), ("ウォーター", "w o o t a a"), ("ヴァイオリン", "v a i o r i N"),
    ("ツァー", "ts a a"), ("シェア", "sh e a"), ("チェック", "ch e cl k u"),
    ("ジェット", "j e cl t o"), ("デュエット", "dy u e cl t o"), ("トゥ", "t u"),
    ("クァ", "k w a"), ("イェ", "y e"),
])
def test_loanword_kana(kana, phonemes):
    assert ph(kana) == phonemes


def test_iteration_marks_and_other_characters():
    assert ph("いすゞ") == "i s u z u"
    assert ph("こゝろ") == "k o k o r o"
    assert ph("abc漢字。") == ""


def test_helpers():
    assert to_hiragana("カタカナ・ー") == "かたかな・ー"
    assert mora_count(kana_phonemes("がっこう")) == 4
    assert mora_count(kana_phonemes("きゃんぷ")) == 3
