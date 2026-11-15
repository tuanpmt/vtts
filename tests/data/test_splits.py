import random

from vtts.data.filter import Row
from vtts.data.report import dataset_report
from vtts.data.splits import make_splits


def _rows(n=500):
    rnd = random.Random(0)
    return [Row(f"r{i:04d}", "xin chào bạn", rnd.uniform(1.0, 12.0)) for i in range(n)]


def test_splits_deterministic_and_disjoint():
    a, b = make_splits(_rows()), make_splits(_rows())
    assert {k: [r.id for r in v] for k, v in a.items()} == {k: [r.id for r in v] for k, v in b.items()}
    ids = [set(r.id for r in a[k]) for k in ("train", "val", "heldout")]
    assert not (ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2])
    assert sum(map(len, ids)) == 500
    assert len(a["heldout"]) == 50
    assert all(3.0 <= r.duration_s <= 10.0 for r in a["heldout"])


def test_report_tone_distribution_sums():
    splits = make_splits(_rows())
    rep = dataset_report(splits)
    assert sum(rep["tones"].values()) == 3 * len(splits["train"])
    assert rep["train"]["count"] == len(splits["train"])
