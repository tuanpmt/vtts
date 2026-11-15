import pytest

from vtts.frontend import phoneme_set as ps


def test_vocab_layout():
    assert ps.VOCAB_SIZE == 65 == len(ps.TOKENS) == len(set(ps.TOKENS))
    assert ps.token_to_id("<pad>") == 0 and ps.token_to_id("<bos>") == 1
    assert ps.token_to_id("<eos>") == 2 and ps.token_to_id(" ") == 3
    assert ps.id_to_token(ps.token_to_id("N:ươ")) == "N:ươ"
    assert ps.TOKENS[-6:] == ("T1", "T2", "T3", "T4", "T5", "T6")
    assert ps.PHONEME_SET_VERSION == "1"


def test_unknown_token_raises():
    with pytest.raises(KeyError):
        ps.token_to_id("O:zz")
