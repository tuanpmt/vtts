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
