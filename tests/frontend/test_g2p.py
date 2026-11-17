import pytest

from vtts.frontend.g2p import encode, g2p


def test_sentence_tokens():
    assert g2p("xin chào , việt nam !") == [
        "O:x", "N:i", "C:n", "T1", " ", "O:ch", "N:a", "C:w", "T2", ",",
        "O:v", "N:iê", "C:t", "T6", " ", "O:n", "N:a", "C:m", "T1", "!"]


def test_dialect_distinctions_preserved():
    first = lambda w: g2p(w)[0]
    assert len({first("tra"), first("cha")}) == 2
    assert len({first("sa"), first("xa")}) == 2
    assert len({first("ra"), first("da"), first("gia")}) == 3


def test_encode_wraps_bos_eos():
    out = encode(g2p("ba"))
    assert out[0] == 1 and out[-1] == 2 and len(out) == 5


def test_invalid_syllable_raises():
    with pytest.raises(ValueError):
        g2p("wifi")


def test_glide_token_emitted():
    assert g2p("quốc") == ["O:k", "G:w", "N:ô", "C:c", "T3"]
