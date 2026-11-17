"""Pronunciation data files (src/vtts/frontend/lexicons/<lang>/*.tsv) are well formed."""

import pytest

from vtts.frontend.lexicons import ROOT, load_table
from vtts.frontend.syllable import parse_syllable

VI_TABLES = sorted(p.stem for p in (ROOT / "vi").glob("*.tsv"))


@pytest.mark.parametrize("name", VI_TABLES)
def test_vi_readings_are_vietnamese_syllables(name):
    for key, reading in load_table("vi", name).items():
        for syl in reading.split():
            assert parse_syllable(syl) is not None, f"vi/{name}.tsv: {key!r} -> {syl!r}"


def test_loader_rejects_bad_lines(tmp_path, monkeypatch):
    import vtts.frontend.lexicons as lex
    (tmp_path / "xx").mkdir()
    (tmp_path / "xx" / "bad.tsv").write_text("# comment\nkey without tab\n", encoding="utf-8")
    monkeypatch.setattr(lex, "ROOT", tmp_path)
    load_table.cache_clear()
    with pytest.raises(ValueError, match="bad.tsv:2"):
        lex.load_table("xx", "bad")
    load_table.cache_clear()
