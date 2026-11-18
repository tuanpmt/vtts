from vtts.eval.mos import eval_threads


def test_eval_threads_from_environment(monkeypatch):
    monkeypatch.setenv("VTTS_EVAL_THREADS", "8")
    assert eval_threads(None) == 8
    assert eval_threads(2) == 2  # an explicit value wins


def test_eval_threads_default_is_unlimited(monkeypatch):
    monkeypatch.delenv("VTTS_EVAL_THREADS", raising=False)
    assert eval_threads(None) is None
