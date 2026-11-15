import pytest

from vtts.frontend.phoneme_set import PUNCTUATION, VOCAB_SIZE
from vtts.frontend.text import split_sentences, text_to_ids


@pytest.mark.parametrize("text", ["", "   ", "...", "😀"])
def test_empty_inputs(text):
    assert text_to_ids(text) == []


def _syllables(chunks):
    return [w for c in chunks for w in c.split() if w not in PUNCTUATION]


def test_long_paragraph_chunked():
    clause = "hôm nay trời đẹp lắm và chúng tôi đi chơi công viên"  # 12 syllables
    text = ", ".join([clause] * 12) + " ."  # 144 syllables, one sentence
    chunks = split_sentences(text)
    assert len(chunks) > 1
    assert all(len(_syllables([c])) <= 40 for c in chunks)
    assert _syllables(chunks) == clause.split() * 12


def test_hard_cut_without_commas():
    text = " ".join(["ba"] * 95)
    chunks = split_sentences(text)
    assert [len(_syllables([c])) for c in chunks] == [40, 40, 15]


def test_sentence_split_on_terminators():
    chunks = split_sentences("Chào bạn. Bạn khoẻ không? Tốt!")
    assert chunks == ["chào bạn .", "bạn khoẻ không ?", "tốt !"]


HARD = ["Hello world", "https://example.com/a?b=1", "iPhone15 Pro Max", "A4", "COVID-19",
        "x² + y² = z²", "1.000.000.000.000.000.000", "3,14159", "#hashtag @user",
        "C++ và C#", "Tel: 0912.345.678", "50kg/m²", "~~~", "a\tb\nc", "Ω≈ç√∫",
        "ngày 31/12", "12/25/2026", "25:99", "QUẢNG NINH", "Phở 24h", "100$", "$100",
        "2024-11-14", "v.v.", "TP. Hồ Chí Minh", "Q.1, P.Bến Nghé", "e-mail", "ok", "😀😀😀",
        "ʕ•ᴥ•ʔ"]


@pytest.mark.parametrize("text", HARD)
def test_never_emits_unknown_ids(text):
    for ids in text_to_ids(text):
        assert all(0 <= i < VOCAB_SIZE for i in ids)
