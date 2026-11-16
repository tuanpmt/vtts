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


def test_v2_extends_v1():
    assert ps.TOKENS_V2[: ps.VOCAB_SIZE] == ps.TOKENS and ps.VOCAB_SIZE_V2 == 107
    assert len(set(ps.TOKENS_V2)) == 107 and len(ps.ARPABET) == 39
    assert ps.token_to_id_v2("EN:AA") == 65 and ps.token_to_id_v2("EN:ZH") == 103
    assert [ps.token_to_id_v2(f"S{i}") for i in range(3)] == [104, 105, 106]
    assert ps.token_to_id_v2("T6") == ps.token_to_id("T6")
    assert ps.PHONEME_SET_VERSION_V2 == "2"
