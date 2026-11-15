import numpy as np
import pytest
import soundfile as sf

from vtts.eval.cer import corpus_cer
from vtts.eval.run_eval import evaluate

SENTS = [{"id": "a", "text": "xin chào", "group": "g"},
         {"id": "b", "text": "tạm biệt", "group": "g"},
         {"id": "c", "text": "cảm ơn bạn", "group": "g"}]


def _write(tmp_path, ids):
    t = np.arange(22050) / 22050
    for i in ids:
        sf.write(tmp_path / f"{i}.wav", 0.3 * np.sin(2 * np.pi * 300 * t), 22050)


def test_evaluate_with_fake_asr(tmp_path):
    _write(tmp_path, "abc")
    hyps = {"a": "xin chào", "b": "tạm biệt", "c": "cảm ơn bàn"}
    fake = lambda paths: [hyps[p.stem] for p in paths]  # noqa: E731
    rep = evaluate("sys", "set", tmp_path, SENTS, asr=fake, mos=False)
    expected = corpus_cer([(s["text"], hyps[s["id"]]) for s in SENTS])
    assert rep.corpus_cer == pytest.approx(expected) and expected > 0
    assert [c.id for c in rep.clips] == ["a", "b", "c"]
    assert rep.mean_utmos is None


def test_missing_audio_lists_ids(tmp_path):
    _write(tmp_path, "ab")
    with pytest.raises(FileNotFoundError, match="c"):
        evaluate("sys", "set", tmp_path, SENTS, asr=lambda p: ["x"] * len(p), mos=False)
