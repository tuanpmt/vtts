import pytest

from vtts.eval.cer import cer, corpus_cer, prep_for_cer, wer


def test_cer_tone_sensitive():
    assert cer("ma", "mà") == 0.5


def test_cer_ignores_case_punct_and_digits():
    assert cer("Hai mươi mốt.", "hai mươi mốt") == 0.0
    assert cer("21", "hai mươi mốt") == 0.0


def test_corpus_cer():
    # 0 errors in "ba" (2 chars) + 1 error in "cơm" (3 chars) -> 1/5, not the mean of clip CERs
    assert corpus_cer([("ba", "ba"), ("cơm", "cờm")]) == pytest.approx(1 / 5)


def test_wer_counts_words():
    assert wer("xin chào bạn", "xin chao bạn") == pytest.approx(1 / 3)


def test_prep_keeps_tones():
    assert prep_for_cer("Việt Nam!") == "việt nam"


def test_cer_ignores_tone_placement_style():
    assert cer("hoà bình", "hòa bình") == 0.0
    assert cer("thuỷ", "thủy") == 0.0


def test_english_normalization_matches_spoken_forms():
    from vtts.eval.cer import cer, prep_for_cer
    assert prep_for_cer("Battery level is at 15 percent.", "en") == "battery level is at fifteen percent"
    assert cer("The meeting starts at 9:30.", "the meeting starts at nine thirty", "en") == 0.0


def test_mixed_keeps_english_words_and_reads_numbers():
    from vtts.eval.cer import prep_for_cer, wer
    assert prep_for_cer("Pin AirPods còn 20%, nhớ sạc nhé.", "mixed") == "pin airpods còn hai mươi phần trăm nhớ sạc nhé"
    assert wer("Mở Spotify và play playlist.", "mở spotify và play playlist", "mixed") == 0.0


def test_vietnamese_default_unchanged():
    from vtts.eval.cer import prep_for_cer
    assert prep_for_cer("Pin còn 15%.") == prep_for_cer("Pin còn 15%.", "vi") == "pin còn mười lăm phần trăm"
