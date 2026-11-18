import re
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from vtts.export.format import read_model, write_model
from vtts.student.config import PRESETS
from vtts.student.model import Student


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_roundtrip(tmp_path, name):
    torch.manual_seed(0)
    m = Student(PRESETS[name])
    path = tmp_path / "m.vtts"
    write_model(m, path)
    dims, tensors = read_model(path)
    assert dims["decoder"] == {"hifigan": 0, "istft": 1, "vocos": 2}[PRESETS[name].decoder]
    sd = m.state_dict()
    for k, v in sd.items():
        assert np.array_equal(tensors[k], v.numpy()), k
    assert path.read_bytes()[:4] == b"VTTS"


def test_offsets_aligned(tmp_path):
    write_model(Student(PRESETS["S-vocos"]), tmp_path / "m.vtts")
    from vtts.export.format import read_table

    for row in read_table(tmp_path / "m.vtts"):
        assert row["offset"] % 16 == 0


@pytest.mark.parametrize("vocab,name", [(65, "v1"), (107, "vi-en"), (171, "zh-en"), (153, "ko-en"),
                                        (144, "ja-en"), (138, "es-en"), (141, "id-en")])
def test_token_set_derived_from_vocab(tmp_path, vocab, name):
    from vtts.export.format import TOKEN_SET_CODES, token_set_of

    m = Student(replace(PRESETS["S-vocos"], vocab=vocab))
    write_model(m, tmp_path / "m.vtts")
    dims, _ = read_model(tmp_path / "m.vtts")
    assert dims["token_set"] == TOKEN_SET_CODES[name]
    assert token_set_of(dims) == name


def test_token_set_explicit_and_int8(tmp_path):
    from vtts.export.format import token_set_of
    from vtts.export.quant import write_model_int8

    m = Student(replace(PRESETS["S-vocos"], vocab=180))  # spare rows: not derivable from vocab
    write_model(m, tmp_path / "a.vtts")
    assert "token_set" not in read_model(tmp_path / "a.vtts")[0]
    write_model_int8(m, tmp_path / "b.vtts", token_set="zh-en")
    assert token_set_of(read_model(tmp_path / "b.vtts")[0]) == "zh-en"
    with pytest.raises(ValueError):
        write_model(m, tmp_path / "c.vtts", token_set="xx-en")
    with pytest.raises(ValueError):  # embedding smaller than the token set
        write_model(Student(PRESETS["S-vocos"]), tmp_path / "d.vtts", token_set="vi-en")


def test_token_set_old_files_by_vocab(tmp_path):
    """Files written before the dim existed map by vocab like the C runtime."""
    from vtts.export.format import token_set_of, write_tensors

    assert token_set_of({"vocab": 65}) == "v1"
    assert token_set_of({"vocab": 107}) == "vi-en"
    assert token_set_of({"vocab": 171}) == "zh-en"
    assert token_set_of({"vocab": 100}) == "vi-en"  # old firmware rule: > 65 is v2
    assert token_set_of({"vocab": 40}) == "v1"
    assert token_set_of({"vocab": 171, "token_set": 0}) == "zh-en"
    assert token_set_of({"vocab": 300, "token_set": 99}) == "unknown"
    write_tensors(tmp_path / "old.vtts", {"vocab": 107}, {"x": (np.zeros(4, np.float32), None)})
    assert token_set_of(read_model(tmp_path / "old.vtts")[0]) == "vi-en"


def test_token_set_codes_match_c_header():
    """Every code of the C header is the Python one; codes the runtime does not know yet (token
    sets with a Python front-end only) come after them, so the runtime loads them as unknown."""
    from vtts.export.format import TOKEN_SET_CODES, TOKEN_SET_SIZES

    h = (Path(__file__).parents[2] / "runtime" / "include" / "vtts.h").read_text()
    in_c = {m.group(1).lower().replace("_", "-"): int(m.group(2))
            for m in re.finditer(r"VTTS_TOKSET_(\w+) = (\d+)", h) if m.group(1) != "UNKNOWN"}
    assert len(in_c) >= 5 and all(TOKEN_SET_CODES[name] == code for name, code in in_c.items())
    assert all(c > max(in_c.values()) for n, c in TOKEN_SET_CODES.items() if n not in in_c)
    assert len(set(TOKEN_SET_CODES.values())) == len(TOKEN_SET_CODES)
    assert len(set(TOKEN_SET_SIZES.values())) == len(TOKEN_SET_SIZES)  # vocab -> set unambiguous


def test_token_set_sizes_match_frontend():
    from vtts.export.format import TOKEN_SET_SIZES
    from vtts.frontend.phoneme_set import TOKEN_SETS, VOCAB_SIZE

    assert TOKEN_SET_SIZES["v1"] == VOCAB_SIZE
    for name, toks in TOKEN_SETS.items():
        assert TOKEN_SET_SIZES[name] == len(toks)
