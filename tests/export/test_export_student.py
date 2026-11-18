"""scripts/student/export_student.py records the token set in the model header."""

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import torch

from vtts.export.format import read_model, token_set_of
from vtts.student.config import PRESETS
from vtts.student.model import Student

SCRIPT = Path(__file__).parents[2] / "scripts" / "student" / "export_student.py"


def _load():
    spec = importlib.util.spec_from_file_location("export_student", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ckpt(tmp_path, cfg, **extra):
    torch.manual_seed(0)
    st = {"student": Student(cfg).state_dict(), "config": dict(cfg.__dict__), **extra}
    path = tmp_path / "front.pt"
    torch.save(st, path)
    return path


def _run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["export_student.py", *map(str, args)])
    _load().main()


@pytest.mark.parametrize("int8", [False, True])
def test_export_derives_token_set_from_vocab(tmp_path, monkeypatch, int8):
    ck = _ckpt(tmp_path, PRESETS["S-vocos-p-zh-en"])
    out = tmp_path / "m.vtts"
    _run(monkeypatch, "--front", ck, "--dec", ck, "--out", out, *(["--int8"] if int8 else []))
    assert token_set_of(read_model(out)[0]) == "zh-en"


def test_export_token_set_argument_and_checkpoint(tmp_path, monkeypatch):
    cfg = replace(PRESETS["S-vocos"], vocab=180)  # spare rows: the vocab names no set
    ck = _ckpt(tmp_path, cfg)
    out = tmp_path / "m.vtts"
    with pytest.raises(SystemExit):
        _run(monkeypatch, "--front", ck, "--dec", ck, "--out", out)
    _run(monkeypatch, "--front", ck, "--dec", ck, "--out", out, "--token-set", "ja-en")
    assert token_set_of(read_model(out)[0]) == "ja-en"
    ck2 = _ckpt(tmp_path, cfg, token_set="ko-en")
    _run(monkeypatch, "--front", ck2, "--dec", ck2, "--out", out)
    assert token_set_of(read_model(out)[0]) == "ko-en"
