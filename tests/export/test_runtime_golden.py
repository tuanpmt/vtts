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
                       check=False, capture_output=True, text=True)
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
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "m8.vtts").stat().st_size < 0.5 * 4 * sum(p.numel() for p in m.parameters())


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_streaming_equals_whole(tmp_path, name):
    subprocess.run(["make", "-s", "build/stream_test"], cwd=RUNTIME, check=True)
    torch.manual_seed(0)
    m = Student(PRESETS[name]).eval()
    with torch.no_grad():  # 6 frames per id for every preset: frame counts (132, 36, 324) do not
        # depend on the random init (which shifts with the vocab size) and stay clear of the C
        # test's 200-frame threshold for the arena check
        m.duration.out.weight.zero_()
        m.duration.out.bias.fill_(math.log(6.0))
    from vtts.export.quant import write_model_int8

    write_model_int8(m, tmp_path / "m8.vtts")
    write_golden(m, TEXTS, tmp_path / "g.bin")
    limit = {"S-vocos": 460_000, "M-vocos": 600_000}.get(name, 10**9)
    r = subprocess.run([str(RUNTIME / "build" / "stream_test"), str(tmp_path / "m8.vtts"),
                        str(tmp_path / "g.bin"), str(limit)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_c_text_frontend_parity():
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    r = subprocess.run([str(RUNTIME / "build" / "text_test"), str(RUNTIME / "test" / "text_parity.tsv")],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([str(RUNTIME / "build" / "text_test"), "--fuzz"], check=False, capture_output=True, text=True)
    assert f.returncode == 0, f.stdout + f.stderr[-2000:]


def test_c_lexicon_parity(tmp_path):
    """The C VLEX reader gives the same lexicon lookups and letter-to-sound ids as Python."""
    from vtts.frontend.en.vlex import build_vlex

    blob = tmp_path / "lex_en.bin"
    blob.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/lex_test"], cwd=RUNTIME, check=True)
    r = subprocess.run([str(RUNTIME / "build" / "lex_test"), str(blob), str(RUNTIME / "test" / "lex_expect.tsv")],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]


def test_c_english_normalizer_parity():
    """vtts_en_normalize gives exactly normalize_en (sentences, edge cases, regex fuzz)."""
    subprocess.run(["make", "-s", "build/en_norm_test"], cwd=RUNTIME, check=True)
    r = subprocess.run([str(RUNTIME / "build" / "en_norm_test"), str(RUNTIME / "test" / "en_norm.tsv")],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]


def test_c_bilingual_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex (phoneme set v2) gives exactly text_to_ids(text, mode) for vi, en and
    auto mode, and survives the fuzz run in every mode."""
    from vtts.frontend.en.vlex import build_vlex

    blob = tmp_path / "lex_en.bin"
    blob.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(blob), str(RUNTIME / "test" / "text_parity_v2.tsv")],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz", "--lex", str(blob)], check=False, capture_output=True, text=True)
    assert f.returncode == 0, f.stdout + f.stderr[-2000:]


def _zh_blob(path):
    import importlib.util

    script = Path(__file__).parents[2] / "scripts" / "frontend" / "build_zh_blob.py"
    spec = importlib.util.spec_from_file_location("build_zh_blob", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    blob = mod.build_zlex()
    mod._check(blob)
    path.write_bytes(blob)
    return len(blob)


def test_c_mandarin_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_ZH mode (token set zh-en, ZLEX + VLEX blobs) gives exactly
    text_to_ids(text, "zh"), and survives the fuzz run (mixed Han, ASCII, digits, random bytes)."""
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex, zh = tmp_path / "lex_en.bin", tmp_path / "zh_lex.bin"
    lex.write_bytes(build_vlex())
    assert _zh_blob(zh) < 300_000
    fixture = RUNTIME / "test" / "text_parity_zh.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --zh --sentences data/zh/sentences.jsonl "
            "--limit 2500 --out runtime/test/text_parity_zh.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), "--zh", str(zh), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz", "--lex", str(lex), "--zh", str(zh)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "with zh" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_korean_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_KO mode (token set ko-en, rules and exception table compiled
    in, VLEX for English words) gives exactly text_to_ids(text, "ko"), and survives the fuzz run
    (Hangul, jamo, ASCII, numbers with counters, punctuation, random bytes, long words)."""
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_ko.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --ko --sentences data/ko/sentences.jsonl "
            "--limit 3000 --out runtime/test/text_parity_ko.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "with ko" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_korean_tables_current():
    """runtime/src/vtts_text_tables.h holds the current Korean tables (overrides.tsv included)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    want = "\n".join(mod.korean_tables())
    assert want in (RUNTIME / "src" / "vtts_text_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_hindi_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_HI mode (token set hi-en, letter rules and exception table
    compiled in, VLEX for English words) gives exactly text_to_ids(text, "hi"), and survives the fuzz
    run (Devanagari, nukta forms, signs, digits, dandas, ASCII, numbers, money, random bytes)."""
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_hi.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --hi --sentences data/hi/sentences.jsonl "
            "data/hi/probe_src.jsonl --limit 3000 --out runtime/test/text_parity_hi.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "with hi" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_hindi_tables_current():
    """runtime/src/vtts_text_tables.h holds the current Hindi tables (overrides.tsv, numbers.tsv)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    want = "\n".join(mod.hindi_tables())
    assert want in (RUNTIME / "src" / "vtts_text_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def _ja_blob(path):
    import importlib.util

    script = Path(__file__).parents[2] / "scripts" / "frontend" / "build_ja_blob.py"
    spec = importlib.util.spec_from_file_location("build_ja_blob", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    blob = mod.build_jlex()
    mod._check(blob)
    path.write_bytes(blob)
    return len(blob)


def test_c_japanese_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_JA mode (token set ja-en, JLEX + VLEX blobs) gives exactly
    text_to_ids(text, "ja"), the JLEX NFKC equals unicodedata's, and the fuzz run survives (kanji,
    kana, half-width forms, numbers with counters, ASCII, punctuation, random bytes, long runs)."""
    import random
    import unicodedata

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex, ja = tmp_path / "lex_en.bin", tmp_path / "ja_lex.bin"
    lex.write_bytes(build_vlex())
    assert _ja_blob(ja) < 2_000_000
    fixture = RUNTIME / "test" / "text_parity_ja.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --ja --sentences data/ja/sentences.jsonl "
            "--limit 3000 --out runtime/test/text_parity_ja.tsv --nfkc-out runtime/test/ja_nfkc.tsv")
    nfkc = RUNTIME / "test" / "ja_nfkc.tsv"
    for line in random.Random(1).sample(nfkc.read_text(encoding="utf-8").splitlines(), 300):
        src, want = (("".join(chr(int(h, 16)) for h in part.split())) for part in line.split("\t"))
        assert unicodedata.normalize("NFKC", src) == want, "NFKC fixture is stale (Python's Unicode version changed)"
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    n = subprocess.run([exe, "--ja", str(ja), "--nfkc", str(nfkc)], check=False, capture_output=True, text=True)
    assert n.returncode == 0, n.stdout[-3000:] + n.stderr[-2000:]
    r = subprocess.run([exe, "--lex", str(lex), "--ja", str(ja), str(fixture)], check=False, capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz", "--lex", str(lex), "--ja", str(ja)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "with ja" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_japanese_tables_current():
    """runtime/src/vtts_text_tables.h holds the current Japanese tables (kana, counters, normalizer)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    want = "\n".join(mod.japanese_tables())
    assert want in (RUNTIME / "src" / "vtts_text_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_text_to_audio_ja_en(tmp_path):
    """Full device path on the host for a ja-en model (tiny, random weights): the header's token set
    picks the ja front-end with the JLEX blob, ids above 106 reach the embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-ja-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "ja.vtts"
    write_model_int8(m, model, token_set="ja-en")
    assert token_set_of(read_model(model)[0]) == "ja-en"
    lex, ja = tmp_path / "lex_en.bin", tmp_path / "ja_lex.bin"
    lex.write_bytes(build_vlex())
    _ja_blob(ja)
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "Wi-Fiをオンにしますか？今は8:30で、気温は26度です。"
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), "--ja", str(ja),
                        text], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set ja-en header mode ja lex 1 zh 0 ja 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "ja")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "ko", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: ja" in bad.stderr


@pytest.mark.parametrize("lang", ["es", "id", "pt", "ms"])
def test_c_latin_frontend_parity(tmp_path, lang):
    """vtts_text_to_ids_ex in VTTS_LANG_ES|ID|PT mode (token sets es-en, id-en, pt-en; tables compiled
    in, VLEX for English words) gives exactly text_to_ids(text, lang)."""
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / f"text_parity_{lang}.tsv"
    lines = fixture.read_text(encoding="utf-8").split("\n")[:-1]
    assert len(lines) > 10000
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert mode == lang
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            f"run: uv run python scripts/frontend/export_text_parity.py --lt {lang} "
            f"--sentences data/{lang}/sentences.jsonl --limit 3000 --out runtime/test/text_parity_{lang}.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    r = subprocess.run([str(RUNTIME / "build" / "text_test"), "--lex", str(lex), str(fixture)],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]


def test_c_latin_frontend_fuzz(tmp_path):
    """The es, id and pt modes survive the fuzz run (letters of the languages, numbers, dates, money,
    units, abbreviations, English words, other scripts, random bytes, long words) and stay inside
    their token sets."""
    from vtts.frontend.en.vlex import build_vlex

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    f = subprocess.run([str(RUNTIME / "build" / "text_test"), "--fuzz-lt", "--lex", str(lex)],
                       check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz lt: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_latin_tables_current():
    """runtime/src/vtts_text_tables.h holds the current es/id/pt tables (lexicons included) and the
    Unicode classes."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    header = (RUNTIME / "src" / "vtts_text_tables.h").read_text(encoding="utf-8")
    for part in (mod.latin_tables(), mod.unicode_tables()):
        assert "\n".join(part) in header, "run: uv run python runtime/tools/gen_text_tables.py"


@pytest.mark.parametrize("lang", ["it", "tr"])
def test_c_it_tr_frontend_parity(tmp_path, lang):
    """vtts_text_to_ids_ex in VTTS_LANG_IT|TR mode (token sets it-en, tr-en; tables compiled in, VLEX for
    English words) gives exactly text_to_ids(text, lang); the fuzz run of both modes stays inside the
    token sets."""
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / f"text_parity_{lang}.tsv"
    lines = fixture.read_text(encoding="utf-8").split("\n")[:-1]
    assert len(lines) > 10000
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert mode == lang
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            f"run: uv run python scripts/frontend/export_text_parity.py --lt {lang} "
            f"--sentences data/{lang}/sentences.jsonl --limit 3000 --out runtime/test/text_parity_{lang}.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    r = subprocess.run([str(RUNTIME / "build" / "text_test"), "--lex", str(lex), str(fixture)],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([str(RUNTIME / "build" / "text_test"), "--fuzz-it-tr", "--lex", str(lex)],
                       check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz it/tr: ok (2 modes" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_it_tr_tables_current():
    """runtime/src/vtts_text_it_tables.h and vtts_text_tr_tables.h hold the current tables."""
    import importlib.util
    import sys

    sys.path.insert(0, str(RUNTIME / "tools"))
    try:
        spec = importlib.util.spec_from_file_location("gen_lt_tables_it_tr", RUNTIME / "tools" / "gen_lt_tables_it_tr.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    for name, fn in (("vtts_text_it_tables.h", mod.italian_tables), ("vtts_text_tr_tables.h", mod.turkish_tables)):
        assert (RUNTIME / "src" / name).read_text(encoding="utf-8") == "\n".join(fn()), (
            "run: uv run python runtime/tools/gen_text_tables.py")


@pytest.mark.parametrize("lang, text", [
    ("es", "¿Enciendo el Wi-Fi? Son las 8:30 y hace 26 °C, el iPhone tiene 21 apps."),
    ("id", "Nyalakan Wi-Fi sekarang? Pukul 08.30, suhu 26 °C, harganya Rp50.000."),
    ("pt", "Ligo o Wi-Fi? São 8h30, faz 26 °C e o iPhone custa R$ 1.250,50."),
    ("it", "Accendo il Wi-Fi? Sono le 8:30, ci sono 26 °C e l'iPhone costa 1.250,50 €."),
    ("tr", "Wi-Fi'ı açayım mı? Saat 8:30, hava 26 °C ve iPhone'un fiyatı 1.250,50 TL."),
    ("ms", "Hidupkan Wi-Fi sekarang? Pukul 8.30 pagi, suhu 26 °C, harganya RM12.50 pada 19 Nov 2026."),
])
def test_c_text_to_audio_latin(tmp_path, lang, text):
    """Full device path on the host for an es-en, id-en or pt-en model (tiny, random weights): the
    header's token set picks the front-end (no extra blob), ids above 106 reach the embedding."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    pair = f"{lang}-en"
    m = Student(PRESETS[f"S-vocos-p-{pair}"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / f"{lang}.vtts"
    write_model_int8(m, model, token_set=pair)
    assert token_set_of(read_model(model)[0]) == pair
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith(f"token_set {pair} header mode {lang} lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, lang)
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "ko", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and f"modes: {lang}" in bad.stderr


def test_c_malay_frontend_fuzz(tmp_path):
    """The ms mode survives its fuzz run (Malay digraphs, months with re.IGNORECASE look-alikes, day
    parts, ringgit and sen, random bytes) and stays inside ms-en; with VTTS_ENABLE_MS=0 the mode is
    unsupported and the other Latin modes are unchanged."""
    from vtts.frontend.en.vlex import build_vlex

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    f = subprocess.run([str(RUNTIME / "build" / "text_test"), "--fuzz-ms", "--lex", str(lex)],
                       check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz ms: ok" in f.stdout, f.stdout + f.stderr[-2000:]
    src = _text_sources()
    off = tmp_path / "text_test_off"
    subprocess.run(["cc", "-std=c99", "-O1", "-Wall", "-Wextra", "-Werror", "-Iinclude", "-Isrc", "-DVTTS_ENABLE_MS=0",
                    *src, "test/text_test.c", "-o", str(off)], cwd=RUNTIME, check=True)
    r = subprocess.run([str(off), "--lex", str(lex), str(RUNTIME / "test" / "text_parity_id.tsv")],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]
    case = tmp_path / "ms.tsv"
    case.write_text("ms\tSaya suka makan.\t1 2\n", encoding="utf-8")
    r = subprocess.run([str(off), "--lex", str(lex), str(case)], check=False, capture_output=True, text=True)
    assert r.returncode == 1 and "(rc -1)" in r.stdout, r.stdout


def test_c_malay_tables_current():
    """runtime/src/vtts_text_ms_tables.h holds the current Malay tables (lexicons included)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    header = (RUNTIME / "src" / "vtts_text_ms_tables.h").read_text(encoding="utf-8")
    assert header == "\n".join(mod.malay_tables()), "run: uv run python runtime/tools/gen_text_tables.py"


def test_c_tagalog_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_TL mode (token set tl-en; tables compiled in, VLEX for English
    words) gives exactly text_to_ids(text, "tl"); the fuzz run stays inside tl-en."""
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_tl.tsv"
    lines = fixture.read_text(encoding="utf-8").split("\n")[:-1]
    assert len(lines) > 10000
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert mode == "tl"
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --tl --sentences data/tl/sentences.jsonl "
            "data/tl/mixed.jsonl --limit 3000 --out runtime/test/text_parity_tl.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    r = subprocess.run([str(RUNTIME / "build" / "text_test"), "--lex", str(lex), str(fixture)],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([str(RUNTIME / "build" / "text_test"), "--fuzz-tl", "--lex", str(lex)],
                       check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz tl: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def _text_sources() -> list[str]:
    """The C sources of the text front-end (every language module; vtts_langs.h switches them)."""
    return sorted(str(p.relative_to(RUNTIME)) for p in (RUNTIME / "src").glob("*.c")
                  if p.name not in ("vtts_model.c", "vtts_synth.c", "vtts_kernels_ref.c"))


def _langs_test_without(tmp_path, *langs: str) -> subprocess.CompletedProcess:
    """runtime/test/langs_test.c built with the given languages switched off (the rest on)."""
    from vtts.frontend.en.vlex import build_vlex

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    exe = tmp_path / "langs_test"
    src = ["src/vtts_model.c", "src/vtts_synth.c", "src/vtts_kernels_ref.c", *_text_sources(), "test/langs_test.c"]
    subprocess.run(["cc", "-std=c99", "-O1", "-Wall", "-Wextra", "-Werror", "-Iinclude", "-Isrc",
                    *(f"-DVTTS_ENABLE_{x}=0" for x in langs), *src, "-lm", "-o", str(exe)], cwd=RUNTIME, check=True)
    return subprocess.run([str(exe), str(lex)], check=False, capture_output=True, text=True)


def test_c_tagalog_disabled(tmp_path):
    """With VTTS_ENABLE_TL=0 the tl-en token set has no text mode and the mode is refused (langs_test)."""
    r = _langs_test_without(tmp_path, "TL")
    assert r.returncode == 0 and " of 27 " in r.stdout and "26 of" in r.stdout, r.stdout + r.stderr


def test_c_tagalog_tables_current():
    """runtime/src/vtts_text_tl_tables.h holds the current Tagalog tables (stress table, word lists)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    header = (RUNTIME / "src" / "vtts_text_tl_tables.h").read_text(encoding="utf-8")
    assert header == "\n".join(mod.tagalog_tables()), "run: uv run python runtime/tools/gen_text_tables.py"


def test_c_text_to_audio_tl_en(tmp_path):
    """Full device path on the host for a tl-en model (tiny, random weights): the header's token set
    picks the Tagalog front-end, ids above 106 reach the embedding."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    text = "Buksan mo ang Wi-Fi? Alas 3:30 ng hapon, 26 °C, ₱1,250.50 ang iPhone case; araw-araw kang mag-aral."
    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-tl-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "tl.vtts"
    write_model_int8(m, model, token_set="tl-en")
    assert token_set_of(read_model(model)[0]) == "tl-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set tl-en header mode tl lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "tl")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0


def test_c_token_set_header():
    """vtts_token_set: the token_set dim, old files by vocab; text modes per token set."""
    subprocess.run(["make", "-s", "build/token_set_test"], cwd=RUNTIME, check=True)
    r = subprocess.run([str(RUNTIME / "build" / "token_set_test")], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_c_text_to_audio_ko_en(tmp_path):
    """Full device path on the host for a ko-en model (tiny, random weights): the header's token set
    picks the ko front-end (no extra blob), ids above 106 reach the embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-ko-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "ko.vtts"
    write_model_int8(m, model, token_set="ko-en")
    assert token_set_of(read_model(model)[0]) == "ko-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "Wi-Fi를 켜 드릴까요? 지금은 8:30이고, 기온은 26도예요."
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set ko-en header mode ko lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "ko")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "zh", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: ko" in bad.stderr


def test_c_text_to_audio_hi_en(tmp_path):
    """Full device path on the host for a hi-en model (tiny, random weights): the header's token set
    (code 10) picks the hi front-end (no extra blob), ids above 106 reach the embedding, audio comes
    out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-hi-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "hi.vtts"
    write_model_int8(m, model, token_set="hi-en")
    assert token_set_of(read_model(model)[0]) == "hi-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "क्या मैं Wi-Fi चालू कर दूँ? अभी 8:30 बजे हैं। तापमान 26°C है।"
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set hi-en header mode hi lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "hi")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "ko", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: hi" in bad.stderr


@pytest.mark.parametrize("int8", [False, True])
def test_c_text_to_audio_zh_en(tmp_path, int8):
    """Full device path on the host for a zh-en model (tiny, random weights): the header's token
    set picks the zh front-end, ids above 106 reach the embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-zh-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "zh.vtts"
    (write_model_int8 if int8 else write_model)(m, model, token_set="zh-en")
    assert token_set_of(read_model(model)[0]) == "zh-en"
    lex, zh = tmp_path / "lex_en.bin", tmp_path / "zh_lex.bin"
    lex.write_bytes(build_vlex())
    _zh_blob(zh)
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "打开Wi-Fi设置，现在是8:30。今天气温26度。"
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), "--zh", str(zh),
                        text], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set zh-en header mode zh lex 1 zh 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "zh")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    # modes of another token set are refused, like the firmware's `lang`
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "vi", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: zh" in bad.stderr


def test_c_thai_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_TH mode (token set th-en, word list, respellings and rules
    compiled in, VLEX for English words) gives exactly text_to_ids(text, "th") on the fixture (the
    Thai eval sets and unit-test strings included), and survives the Thai fuzz run."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_th.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in ("ood_th.jsonl", "mixed_th.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --th --sentences data/th/sentences.jsonl "
            "--limit 3000 --out runtime/test/text_parity_th.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-th", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz th: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_thai_tables_current():
    """runtime/src/vtts_text_th_tables.h holds the current Thai tables (words.txt, overrides.tsv)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "\n".join(mod.thai_tables()) == (RUNTIME / "src" / "vtts_text_th_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_text_to_audio_th_en(tmp_path):
    """Full device path on the host for a th-en model (tiny, random weights): the header's token set
    picks the th front-end (no extra blob), ids above 106 reach the embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-th-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "th.vtts"
    write_model_int8(m, model, token_set="th-en")
    assert token_set_of(read_model(model)[0]) == "th-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "เปิดWi-Fiให้หน่อยครับ ตอนนี้ 14:30 น. อุณหภูมิ 26°C"
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set th-en header mode th lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "th")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "ko", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: th" in bad.stderr


@pytest.mark.parametrize("lang", ["nl", "sv", "no"])
def test_c_nx_frontend_parity(tmp_path, lang):
    """vtts_text_to_ids_ex in VTTS_LANG_NL / _SV / _NO mode (tables compiled in, VLEX for English words)
    gives exactly text_to_ids(text, lang) on the fixture (both eval sets and the unit-test strings
    included), and survives the fuzz run of the three languages."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / f"text_parity_{lang}.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in (f"ood_{lang}.jsonl", f"mixed_{lang}.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            f"run: uv run python scripts/frontend/export_text_parity.py --nx {lang} --sentences "
            f"data/{lang}/sentences.jsonl --limit 3000 --out runtime/test/text_parity_{lang}.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    if lang == "nl":
        f = subprocess.run([exe, "--fuzz-nx", "--lex", str(lex)], check=False, capture_output=True, text=True)
        assert f.returncode == 0 and "fuzz no: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_nx_tables_current():
    """runtime/src/vtts_text_nx_tables.h holds the current Dutch, Swedish and Norwegian tables."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables_nx.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables_nx", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "\n".join(mod.nx_tables()) == (RUNTIME / "src" / "vtts_text_nx_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


@pytest.mark.parametrize("lang, text", [
    ("nl", "Op 3-5-2026 is de update klaar. Het kost € 5,50 bij 26 °C."),
    ("sv", "Den 3 maj är vår update klar. Det kostar 12,50 kr vid 26 °C."),
    ("no", "Den 17. mai er oppdateringen klar. Det koster kr 12,50 ved 26 °C."),
])
def test_c_text_to_audio_nx_en(tmp_path, lang, text):
    """Full device path on the host for an nl-en / sv-en / no-en model (tiny, random weights): the
    header's token set picks the front-end (no extra blob), ids above 106 reach the embedding."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS[f"S-vocos-p-{lang}-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / f"{lang}.vtts"
    write_model_int8(m, model, token_set=f"{lang}-en")
    assert token_set_of(read_model(model)[0]) == f"{lang}-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith(f"token_set {lang}-en header mode {lang} lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, lang)
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "th", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and f"modes: {lang}" in bad.stderr


def test_c_swahili_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_SW mode (token set sw-en; tables compiled in, VLEX for English
    words) gives exactly text_to_ids(text, "sw"); the fuzz run stays inside sw-en."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_sw.tsv"
    lines = fixture.read_text(encoding="utf-8").split("\n")[:-1]
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in ("ood_sw.jsonl", "mixed_sw.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert mode == "sw"
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --sw --sentences data/sw/sentences.jsonl "
            "data/sw/mixed.jsonl --limit 1500 --out runtime/test/text_parity_sw.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-sw", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz sw: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_swahili_tables_current():
    """runtime/src/vtts_text_sw_tables.h holds the current Swahili tables (lexicons included)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    header = (RUNTIME / "src" / "vtts_text_sw_tables.h").read_text(encoding="utf-8")
    assert "\n".join(mod.swahili_tables()) == header, "run: uv run python runtime/tools/gen_text_tables.py"


def test_c_swahili_disabled(tmp_path):
    """Built with VTTS_ENABLE_SW=0: the sw-en token set has no text mode and the mode is refused."""
    r = _langs_test_without(tmp_path, "SW")
    assert r.returncode == 0 and " of 27 " in r.stdout and "26 of" in r.stdout, r.stdout + r.stderr


def test_c_text_to_audio_sw_en(tmp_path):
    """Full device path on the host for an sw-en model (tiny, random weights): the header's token set
    picks the Swahili front-end (no extra blob), ids above 106 reach the embedding."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    text = "Niwashe Wi-Fi sasa? Ni saa 8:30, joto ni 26 °C na bei ni TSh 1,250.50."
    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-sw-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "sw.vtts"
    write_model_int8(m, model, token_set="sw-en")
    assert token_set_of(read_model(model)[0]) == "sw-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set sw-en header mode sw lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "sw")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "es", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: sw" in bad.stderr


def test_c_french_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_FR mode (token set fr-en; tables compiled in, VLEX for English
    words) gives exactly text_to_ids(text, "fr"), and survives the fuzz run in fr mode."""
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_fr.tsv"
    lines = fixture.read_text(encoding="utf-8").split("\n")[:-1]
    assert len(lines) > 10000
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert mode == "fr"
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --fr --sentences data/fr/sentences.jsonl "
            "--limit 3000 --out runtime/test/text_parity_fr.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-fr", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz fr: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_french_tables_current():
    """runtime/src/vtts_text_fr_tables.h holds the current French tables (lexicons/fr included)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "\n".join(mod.french_tables()) == (RUNTIME / "src" / "vtts_text_fr_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_text_to_audio_french(tmp_path):
    """Full device path on the host for an fr-en model (tiny, random weights): the header's token set
    picks the French front-end (no blob), ids above 106 reach the embedding."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    text = "Les enfants allument le Wi-Fi à 14 h 30 : il fait 21 °C et l'iPhone coûte 1 299,99 €."
    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-fr-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "fr.vtts"
    write_model_int8(m, model, token_set="fr-en")
    assert token_set_of(read_model(model)[0]) == "fr-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set fr-en header mode fr lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "fr")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "es", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: fr" in bad.stderr


def test_c_german_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_DE mode (token set de-en, stem list, exception table and rules
    compiled in, VLEX for English words) gives exactly text_to_ids(text, "de") on the fixture (the
    German eval sets and unit-test strings included), and survives the German fuzz run."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_de.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in ("ood_de.jsonl", "mixed_de.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --de --sentences data/de/sentences.jsonl "
            "--limit 3000 --out runtime/test/text_parity_de.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-de", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz de: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_german_tables_current():
    """runtime/src/vtts_text_de_tables.h holds the current German tables (stems, overrides, lists)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "\n".join(mod.german_tables()) == (RUNTIME / "src" / "vtts_text_de_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_text_to_audio_de_en(tmp_path):
    """Full device path on the host for a de-en model (tiny, random weights): the header's token set
    picks the de front-end (no extra blob), ids above 106 reach the embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-de-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "de.vtts"
    write_model_int8(m, model, token_set="de-en")
    assert token_set_of(read_model(model)[0]) == "de-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "Am 3. Mai ist das Update fertig. Es kostet 5,50 € bei 26 °C."
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set de-en header mode de lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "de")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "th", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: de" in bad.stderr


def test_c_arabic_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_AR mode (token set ar-en, word table, patterns and rules
    compiled in, VLEX for English words) gives exactly text_to_ids(text, "ar") on the fixture (the
    Arabic eval sets included), and survives the Arabic fuzz run."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_ar.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in ("ood_ar.jsonl", "mixed_ar.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --ar --sentences data/ar/sentences.jsonl "
            "--limit 2000 --out runtime/test/text_parity_ar.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-ar", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz ar: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_arabic_tables_current():
    """runtime/src/vtts_text_ar_tables.h holds the current Arabic tables (words.tsv, spelling.tsv,
    patterns, normalizer strings)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "\n".join(mod.arabic_tables()) == (RUNTIME / "src" / "vtts_text_ar_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_text_to_audio_ar_en(tmp_path):
    """Full device path on the host for an ar-en model (tiny, random weights): the header's token set
    picks the ar front-end (no extra blob), ids above 106 reach the embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-ar-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "ar.vtts"
    write_model_int8(m, model, token_set="ar-en")
    assert token_set_of(read_model(model)[0]) == "ar-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "افتح Wi-Fi من فضلك، الساعة الآن 10:30 ودرجة الحرارة 26°C."
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set ar-en header mode ar lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "ar")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
    bad = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lang", "ko", text],
                         check=False, capture_output=True, text=True)
    assert bad.returncode == 2 and "modes: ar" in bad.stderr



PAIR_C = {"fi": ("fi-en", "Avaa Spotify klo 14.30, hinta on 12,50 €. Turn on the light."),
          "el": ("el-en", "Άνοιξε το Wi-Fi στις 14:30; Κοστίζει 12,50 € και 3 ώρες.")}


@pytest.mark.parametrize("lang", sorted(PAIR_C))
def test_c_pair_frontend_parity(tmp_path, lang):
    """vtts_text_to_ids_ex in the fi / el mode (tables compiled in, VLEX for English words) gives
    exactly text_to_ids(text, lang) on the fixture (both eval sets included) and survives the fuzz run."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    fixture = RUNTIME / "test" / f"text_parity_{lang}.tsv"
    if not fixture.exists():
        pytest.skip(f"no C front-end for {lang} yet")
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in (f"ood_{lang}.jsonl", f"mixed_{lang}.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            f"run: uv run python scripts/frontend/export_text_parity.py --fe {lang} --sentences "
            f"data/{lang}/sentences.jsonl data/{lang}/mixed.jsonl --limit 3000 --out runtime/test/text_parity_{lang}.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, f"--fuzz-{lang}", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and f"fuzz {lang}: ok" in f.stdout, f.stdout + f.stderr[-2000:]


@pytest.mark.parametrize("lang", sorted(PAIR_C))
def test_c_pair_tables_current(lang):
    """runtime/src/vtts_text_<lang>_tables.h holds the current tables of the Python front-end."""
    import importlib.util

    out = RUNTIME / "src" / f"vtts_text_{lang}_tables.h"
    if not out.exists():
        pytest.skip(f"no C front-end for {lang} yet")
    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = {"fi": "finnish_tables", "el": "greek_tables"}[lang]
    assert "\n".join(getattr(mod, fn)()) == out.read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


@pytest.mark.parametrize("lang", sorted(PAIR_C))
def test_c_text_to_audio_pair(tmp_path, lang):
    """Full device path on the host for a fi-en / el-en model (tiny, random weights): the header's
    token set picks the front-end (no extra blob), ids above 106 reach the embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    tset, text = PAIR_C[lang]
    if not (RUNTIME / "src" / f"vtts_text_{lang}.c").exists():
        pytest.skip(f"no C front-end for {lang} yet")
    torch.manual_seed(0)
    m = Student(PRESETS[f"S-vocos-p-{tset}"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / f"{lang}.vtts"
    write_model_int8(m, model, token_set=tset)
    assert token_set_of(read_model(model)[0]) == tset
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith(f"token_set {tset} header mode {lang} lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, lang)
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0


def test_c_lao_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_LO mode (token set lo-en, word list and rules compiled in, VLEX
    for English words) gives exactly text_to_ids(text, "lo") on the fixture (the Lao eval sets and
    unit-test strings included), survives the Lao fuzz run, and a build with VTTS_ENABLE_LO=0 refuses
    the mode but still loads lo-en models."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_lo.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in ("ood_lo.jsonl", "mixed_lo.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --lo --sentences data/lo/sentences.jsonl "
            "--limit 2000 --out runtime/test/text_parity_lo.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-lo", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz lo: ok" in f.stdout, f.stdout + f.stderr[-2000:]
    n = _langs_test_without(tmp_path, "LO")  # VTTS_ENABLE_LO=0: the mode is refused, the set still loads
    assert n.returncode == 0 and "26 of 27" in n.stdout, n.stdout + n.stderr


def test_c_lao_tables_current():
    """runtime/src/vtts_text_lo_tables.h holds the current Lao tables (words.txt, overrides.tsv)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "\n".join(mod.lao_tables()) == (RUNTIME / "src" / "vtts_text_lo_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_text_to_audio_lo_en(tmp_path):
    """Full device path on the host for a lo-en model (tiny, random weights): the header's token set
    picks the lo front-end (no extra blob), ids above 106 reach the embedding, audio comes out."""
    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-lo-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "lo.vtts"
    write_model_int8(m, model, token_set="lo-en")
    assert token_set_of(read_model(model)[0]) == "lo-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "ເປີດWi-Fiໃຫ້ແດ່ ຕອນນີ້ 14:30 ອຸນຫະພູມ 26°C ລາຄາ ₭5,000"
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set lo-en header mode lo lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "lo")
    assert wav.stat().st_size > 1000


def test_c_danish_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_DA mode (token set da-en, NST readings, word lists and rules
    compiled in, VLEX for English words) gives exactly text_to_ids(text, "da") on the fixture (the
    Danish eval sets and unit-test strings included), survives the Danish fuzz run, and a build with
    VTTS_ENABLE_DA=0 refuses the mode but still loads da-en models."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_da.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in ("ood_da.jsonl", "mixed_da.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --da --sentences data/da/sentences.jsonl "
            "data/da/mixed.jsonl --limit 2500 --out runtime/test/text_parity_da.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-da", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz da: ok" in f.stdout, f.stdout + f.stderr[-2000:]
    n = _langs_test_without(tmp_path, "DA")  # VTTS_ENABLE_DA=0: the mode is refused, the set still loads
    assert n.returncode == 0 and "26 of 27" in n.stdout, n.stdout + n.stderr


def test_c_danish_tables_current():
    """runtime/src/vtts_text_da_tables.h holds the current Danish tables (lexicon.tsv, words.txt, native.txt)."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_text_tables.py"
    spec = importlib.util.spec_from_file_location("gen_text_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "\n".join(mod.danish_tables()) == (RUNTIME / "src" / "vtts_text_da_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_text_to_audio_da_en(tmp_path):
    """Full device path on the host for a da-en model (tiny, random weights): the header's token set
    picks the da front-end (no extra blob), ids above 106 reach the embedding, audio comes out."""
    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-da-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "da.vtts"
    write_model_int8(m, model, token_set="da-en")
    assert token_set_of(read_model(model)[0]) == "da-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "Tænd for Wi-Fi. Mødet er kl. 14.30 den 5. marts, og det koster 12,50 kr."
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set da-en header mode da lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "da")
    assert wav.stat().st_size > 1000


def test_c_khmer_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_KM mode (token set km-en, word list, override, onset and rhyme
    tables compiled in, VLEX for English words) gives exactly text_to_ids(text, "km") on the fixture (the
    Khmer eval sets and unit-test strings included), and survives the Khmer fuzz run."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_km.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in ("ood_km.jsonl", "mixed_km.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --km --sentences data/km/sentences.jsonl "
            "--limit 2500 --out runtime/test/text_parity_km.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-km", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz km: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_khmer_tables_current():
    """runtime/src/vtts_text_km_tables.h holds the current Khmer tables."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_nsp_tables.py"
    spec = importlib.util.spec_from_file_location("gen_nsp_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "\n".join(mod.khmer_tables()) == (RUNTIME / "src" / "vtts_text_km_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_text_to_audio_km_en(tmp_path):
    """Full device path on the host for a km-en model (tiny, random weights): the header's token set
    picks the km front-end (no extra blob), ids above 106 reach the embedding, audio comes out."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-km-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "km.vtts"
    write_model_int8(m, model, token_set="km-en")
    assert token_set_of(read_model(model)[0]) == "km-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "សូមបើកWi-Fiឱ្យខ្ញុំ។ ម៉ោង 14:30 តម្លៃ 5000៛"
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set km-en header mode km lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "km")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0


def test_c_burmese_frontend_parity(tmp_path):
    """vtts_text_to_ids_ex in VTTS_LANG_MY mode (token set my-en: Zawgyi conversion, canonical order,
    syllable rules compiled in, VLEX for English words) gives exactly text_to_ids(text, "my") on the
    fixture (the Burmese eval sets and unit-test strings included), and survives the Burmese fuzz run."""
    import json
    import random

    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    fixture = RUNTIME / "test" / "text_parity_my.tsv"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 10000
    texts = {line.split("\t")[1] for line in lines}
    root = Path(__file__).parents[2]
    for name in ("ood_my.jsonl", "mixed_my.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                assert json.loads(x)["text"] in texts, f"{name} is not in the fixture"
    for line in random.Random(0).sample(lines, 300):  # the fixture is not stale
        mode, text, ids = line.split("\t")
        assert ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)) == ids, (
            "run: uv run python scripts/frontend/export_text_parity.py --my --sentences data/my/sentences.jsonl "
            "--limit 2500 --out runtime/test/text_parity_my.tsv")
    subprocess.run(["make", "-s", "build/text_test"], cwd=RUNTIME, check=True)
    exe = str(RUNTIME / "build" / "text_test")
    r = subprocess.run([exe, "--lex", str(lex), str(fixture)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    f = subprocess.run([exe, "--fuzz-my", "--lex", str(lex)], check=False, capture_output=True, text=True)
    assert f.returncode == 0 and "fuzz my: ok" in f.stdout, f.stdout + f.stderr[-2000:]


def test_c_burmese_tables_current():
    """runtime/src/vtts_text_my_tables.h holds the current Burmese tables."""
    import importlib.util

    script = RUNTIME / "tools" / "gen_nsp_tables.py"
    spec = importlib.util.spec_from_file_location("gen_nsp_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "\n".join(mod.burmese_tables()) == (RUNTIME / "src" / "vtts_text_my_tables.h").read_text(encoding="utf-8"), (
        "run: uv run python runtime/tools/gen_text_tables.py")


def test_c_text_to_audio_my_en(tmp_path):
    """Full device path on the host for a my-en model (tiny, random weights), Zawgyi input included."""
    import wave

    from vtts.export.format import read_model, token_set_of
    from vtts.export.quant import write_model_int8
    from vtts.frontend.en.vlex import build_vlex
    from vtts.frontend.text import text_to_ids

    torch.manual_seed(0)
    m = Student(PRESETS["S-vocos-p-my-en"]).eval()
    with torch.no_grad():
        m.duration.out.bias.fill_(math.log(4.0))
    model = tmp_path / "my.vtts"
    write_model_int8(m, model, token_set="my-en")
    assert token_set_of(read_model(model)[0]) == "my-en"
    lex = tmp_path / "lex_en.bin"
    lex.write_bytes(build_vlex())
    subprocess.run(["make", "-s", "build/vtts_say"], cwd=RUNTIME, check=True)
    text = "Wi-Fi ကို ဖွင့်ပေးပါ။ ေျပာပါတယ္ 14:30 5000 Ks"
    wav = tmp_path / "out.wav"
    r = subprocess.run([str(RUNTIME / "build" / "vtts_say"), str(model), str(wav), "--lex", str(lex), text],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("token_set my-en header mode my lex 1"), lines[0]
    c_ids = [[int(x) for x in ln.split()[1:]] for ln in lines if ln.startswith("ids ")]
    assert c_ids == text_to_ids(text, "my")
    assert max(max(c) for c in c_ids) > 106
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0
