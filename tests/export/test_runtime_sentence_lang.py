import importlib.util
from pathlib import Path

RUNTIME = Path(__file__).parents[2] / "runtime"


def test_c_sentence_tables_current():
    """runtime/src/vtts_text_sent_tables.h holds the current word lists of the sentence-language rule
    (lexicons/latin/function_en.txt, common_en.txt, english.txt, <lang>/function.txt, native.txt)."""
    script = RUNTIME / "tools" / "gen_sent_tables.py"
    spec = importlib.util.spec_from_file_location("gen_sent_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    header = (RUNTIME / "src" / "vtts_text_sent_tables.h").read_text(encoding="utf-8")
    assert header == mod.header(), "run: uv run python runtime/tools/gen_sent_tables.py"
