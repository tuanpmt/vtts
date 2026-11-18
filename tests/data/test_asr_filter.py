from vtts.data.asr_filter import accept, zh_cer


def test_zh_cer_ignores_punctuation_and_traditional():
    assert zh_cer("今天天气很好。", "今天天氣很好") == 0.0


def test_zh_cer_counts_character_errors():
    assert zh_cer("福建福清人", "福建福情人") == 1 / 5


def test_accept_keeps_homophone_slips():
    assert accept(cer=0.2, dur=5.0, n_units=20)


def test_reject_misread_or_truncated():
    assert not accept(cer=0.5, dur=5.0, n_units=20)
    assert not accept(cer=0.0, dur=0.8, n_units=20)  # 25 chars/s: cut short
    assert not accept(cer=0.0, dur=30.0, n_units=20)  # 0.7 chars/s: long silence or babble
