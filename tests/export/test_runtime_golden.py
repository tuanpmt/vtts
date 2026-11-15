import math
import subprocess
from pathlib import Path

import pytest
import torch

from vtts.export.format import write_model
from vtts.export.golden import write_golden
from vtts.student.config import PRESETS
from vtts.student.model import Student

RUNTIME = Path(__file__).parents[2] / "runtime"
TEXTS = ["Xin chào Việt Nam.", "Có.", "Hôm nay trời đẹp, chúng ta đi chơi công viên nhé!"]


@pytest.fixture(scope="module")
def golden_bin():
    subprocess.run(["make", "-s", "build/golden_test"], cwd=RUNTIME, check=True)
    return RUNTIME / "build" / "golden_test"


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_c_runtime_matches_pytorch_fp32(tmp_path, golden_bin, name):
    torch.manual_seed(0)
    m = Student(PRESETS[name]).eval()
    if PRESETS[name].prosody:
        m.expressiveness = 1.3  # the C side reads it from the model file's default
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))  # realistic 2-6 frame durations
    write_model(m, tmp_path / "m.vtts")
    write_golden(m, TEXTS, tmp_path / "g.bin")
    r = subprocess.run([str(golden_bin), str(tmp_path / "m.vtts"), str(tmp_path / "g.bin")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_c_runtime_int8_close_to_pytorch(tmp_path, golden_bin, name):
    from vtts.export.quant import write_model_int8

    torch.manual_seed(0)
    m = Student(PRESETS[name]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    write_model_int8(m, tmp_path / "m8.vtts")
    write_golden(m, TEXTS, tmp_path / "g.bin")
    r = subprocess.run([str(golden_bin), str(tmp_path / "m8.vtts"), str(tmp_path / "g.bin"), "0.98"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "m8.vtts").stat().st_size < 0.5 * 4 * sum(p.numel() for p in m.parameters())


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_streaming_equals_whole(tmp_path, name):
    subprocess.run(["make", "-s", "build/stream_test"], cwd=RUNTIME, check=True)
    torch.manual_seed(0)
    m = Student(PRESETS[name]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    from vtts.export.quant import write_model_int8

    write_model_int8(m, tmp_path / "m8.vtts")
    write_golden(m, TEXTS, tmp_path / "g.bin")
    limit = {"S-vocos": 460_000, "M-vocos": 600_000}.get(name, 10**9)
    r = subprocess.run([str(RUNTIME / "build" / "stream_test"), str(tmp_path / "m8.vtts"),
                        str(tmp_path / "g.bin"), str(limit)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_c_text_frontend_parity():
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    r = subprocess.run([str(RUNTIME / "build" / "text_test"), str(RUNTIME / "test" / "text_parity.tsv")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([str(RUNTIME / "build" / "text_test"), "--fuzz"], capture_output=True, text=True)
    assert f.returncode == 0, f.stdout + f.stderr[-2000:]
