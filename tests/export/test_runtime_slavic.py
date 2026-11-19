"""Russian and Polish device front-ends (runtime/src/vtts_text_ru.c, vtts_re.c) against Python."""

import importlib.util
import math
import random
import subprocess
from pathlib import Path

import torch

from vtts.student.config import PRESETS
from vtts.student.model import Student

ROOT = Path(__file__).parents[2]
RUNTIME = ROOT / "runtime"


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ru_blob(path: Path) -> int:
    blob = _module(ROOT / "scripts" / "frontend" / "build_ru_blob.py", "build_ru_blob").build()
    path.write_bytes(blob)
    return len(blob)


def _check_fixture(fixture: Path, lang: str, hint: str) -> None:
    from vtts.frontend.text import text_to_ids

    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert mode == lang
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, hint


def test_c_russian_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_RU mode (token set ru-en, RLEX stress tables, the Python
    patterns as parse trees, VLEX for English words) gives exactly text_to_ids(text, "ru") on the
    fixture, and survives the ru fuzz run with and without the stress tables."""
    from vtts.frontend.en.vlex import build_vlex

    lex, ru = tmp_path / "lex_en.bin", tmp_path / "ru_lex.bin"
    lex.write_bytes(build_vlex())
    _ru_blob(ru)
    fixture = RUNTIME / "test" / "text_parity_ru.tsv"
    _check_fixture(fixture, "ru", "run: uv run python scripts/frontend/export_parity_ru_pl.py --lang ru --sentences "
                   "data/ru/sentences.jsonl data/ru/probe_src.jsonl --limit 3000 --out runtime/test/text_parity_ru.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), "--ru", str(ru), str(fixture)], check=False, capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    for extra in (["--ru", str(ru)], []):
        f = subprocess.run([exe, "--fuzz-ru", "--lex", str(lex), *extra], check=False, capture_output=True, text=True)
        assert f.returncode == 0 and "fuzz ru: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_russian_tables_current():
    """runtime/src/vtts_text_ru_tables.h holds the current Russian tables and patterns."""
    mod = _module(RUNTIME / "tools" / "gen_slavic_tables.py", "gen_slavic_tables")
    assert "\n".join(mod.russian_tables()) == (RUNTIME / "src" / "vtts_text_ru_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_slavic_tables.py")


def test_ru_blob_lookups(tmp_path):
    """The RLEX blob holds every entry of the Python stress tables (sampled) with its stress."""
    from vtts.frontend.lexicons import load_table

    mod = _module(ROOT / "scripts" / "frontend" / "build_ru_blob.py", "build_ru_blob")
    blob = mod.build()
    assert blob[:4] == b"RLEX" and len(blob) < 400_000
    words = load_table("ru", "stress")
    for k in random.Random(1).sample(sorted(words), 50):
        assert mod.word_value(k, words[k])[0] == words[k].index("+")


def test_c_text_to_audio_ru_en(tmp_path):
    """Full device path on the host for a ru-en model (tiny, random weights): the header's token set
    (code 16) picks the ru front-end, the RLEX blob gives the stress, ids above 106 reach the
    embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-ru-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "ru.vtts"
    write_model_int8(m, model, token_set="ru-en")
    assert token_set_of(read_model(model)[0]) == "ru-en"
    lex, ru = tmp_path / "lex_en.bin", tmp_path / "ru_lex.bin"
    lex.write_bytes(build_vlex())
    _ru_blob(ru)
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "Включить Wi-Fi? Сейчас 8:30, т. е. утро. Температура 26 °C."
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), "--ru", str(ru),
                        text], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set ru-en header mode ru lex 1") and lines[0].endswith("ru 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "ru")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "hi", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: ru" in bad.stderr


def test_c_polish_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_PL mode (token set pl-en, tables and the Python patterns
    compiled in, VLEX for English words) gives exactly text_to_ids(text, "pl") on the fixture, and
    survives the pl fuzz run."""
    from vtts.frontend.en.vlex import build_vlex

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_pl.tsv"
    _check_fixture(fixture, "pl", "run: uv run python scripts/frontend/export_parity_ru_pl.py --lang pl --sentences "
                   "data/pl/sentences.jsonl data/pl/probe_src.jsonl --limit 3500 --fuzz 3000 "
                   "--out runtime/test/text_parity_pl.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-pl", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz pl: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_polish_tables_current():
    """runtime/src/vtts_text_pl_tables.h holds the current Polish tables and patterns."""
    mod = _module(RUNTIME / "tools" / "gen_slavic_tables.py", "gen_slavic_tables")
    assert "\n".join(mod.polish_tables()) == (RUNTIME / "src" / "vtts_text_pl_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_slavic_tables.py")


def test_c_text_to_audio_pl_en(tmp_path):
    """Full device path on the host for a pl-en model (tiny, random weights): the header's token set
    (code 17) picks the pl front-end (no blob), ids above 106 reach the embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-pl-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "pl.vtts"
    write_model_int8(m, model, token_set="pl-en")
    assert token_set_of(read_model(model)[0]) == "pl-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "Włączyć Wi-Fi? Jest 8:30, np. rano. Temperatura 26 °C w domu."
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set pl-en header mode pl lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "pl")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "es", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: pl" in bad.stderr
