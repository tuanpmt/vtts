import json
from pathlib import Path

from vtts.frontend.phoneme_set import PHONEME_SET_VERSION
from vtts.frontend.text import text_to_ids

GOLDEN = Path(__file__).parents[1] / "fixtures" / "frontend_golden.jsonl"


def test_golden_stable():
    rows = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines()]
    assert len(rows) >= 100
    for row in rows:
        assert row["phoneme_set_version"] == PHONEME_SET_VERSION
        assert text_to_ids(row["text"]) == row["ids"], row["text"]
