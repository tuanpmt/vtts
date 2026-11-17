# Plan 1: Foundation (front-end, data, evaluation, baselines)

> **Status:** completed. Historical plan, kept for reference; the deliverables (Vietnamese front-end, InfoRe1 pipeline, evaluation tools, baselines) are in the repository. Current numbers: [README](../../../README.md) and [docs/reports](../../reports/).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Have everything needed to start training the teacher: a Vietnamese front-end (normalization + spelling-based G2P), a cleaned/filtered/split InfoRe1 dataset, an evaluation toolkit (CER, UTMOS, DNSMOS, whistle index) and baseline measurements for two reference voices.

**Architecture:** A single Python package `vtts` (src layout, managed with uv). The front-end consists of pure functions, independent of any model, with a golden JSONL so it can later be ported to C. The data pipeline is split into pure steps (easy to test on the Mac with sample data) and heavy scripts that run on the GPU machine. Baselines run as black boxes in a separate virtualenv.

**Tech Stack:** Python 3.11, uv, pytest, numpy, scipy, soundfile, pyarrow, huggingface_hub; on the GPU machine additionally torch, transformers (PhoWhisper), torchmetrics (DNSMOS), SpeechMOS (UTMOS).

**Spec:** `docs/design/specs/2026-11-14-vietnamese-tts-p4-design.md`

## Plan map

| Plan | Content | Runnable result |
|---|---|---|
| **1 (this document)** | Front-end, data, evaluation, baselines | `text_to_ids()`, filtered dataset, baseline report |
| 2 | VITS teacher: training (warm-start) on GPU, teacher gate | Teacher passes the CER gate + listening test |
| 3 | Distillation of S/M students, exporter, C runtime fp32/int8, golden | int8 student runs on the C host and passes the golden gate |
| 4 | ESP32-P4 port, **evaluate → optimize loop** (as requested by the maintainer), A/B listening page, final report | RTF on the real chip + report |

Each subsequent plan is written once the previous one is done, based on real measurements. The requirement "finish, run evaluation, then optimize" applies at the end of every plan (report the measurements) and is the focus of plan 4.

## Global Constraints

- Documentation written in Vietnamese with full diacritics (project convention at the time; the documentation has since been translated to English); file names, function names, code comments and commit messages in English.
- Python `>=3.11`, managed with `uv`; package `vtts` in `src/vtts/`.
- Do not import or read the source code of: espeak-ng, vPhon, `misaki`, `piper-tts`/`piper1-gpl`, and `sanoTTS/tools/`, `sanoTTS/pypkg/`. Baselines are only run as black boxes in `eval/baselines/` (separate venv).
- Do not use ElevenLabs output.
- Target sample rate: 22,050 Hz mono.
- The front-end token set is **spelling-based**: `tr`≠`ch`, `s`≠`x`, `r`≠`d`≠`gi`, coda `n`≠`ng`, `t`≠`c`, separate `ch`/`nh`; 6 tone tokens following the written tone marks.
- `sanoTTS/`, `data/`, `artifacts/`, `.venv/` are in `.gitignore`.
- Heavy work (7.8 GB download, ASR over 15k sentences, DNSMOS) runs on the GPU machine: a dedicated GPU server (accessed over SSH). The personal computer is used only for code and light tests.

## Review Focus

1. Non-canonical Unicode: precomposed and combining characters (NFD), old-style tone placement (`hoà` vs `hòa`), uppercase (`ĐƯỜNG`). The result must be identical to lowercase NFC. Tests added to Task 3 and Task 4.
2. Non-Vietnamese words: English, abbreviations, email/URL, unusual characters such as emoji. Must not crash and must never emit tokens outside the token set. Tests added to Task 6.
3. Number edge cases: 0, 10, 15, 21, 24, 105, 1005, 1.000.000, `3,5`, `-5`, numbers ≥ 10^15. Tests in Task 5.
4. Empty input, whitespace only, or punctuation only: `text_to_ids` returns `[]` without raising. Tests added to Task 6.
5. Very long paragraphs: must be split into sentences, each chunk at most 40 syllables. Tests added to Task 6.

---

### Task 1: Initialize the repo and Python project

**Files:**
- Create: `.gitignore`, `pyproject.toml`, `src/vtts/__init__.py`, `tests/test_smoke.py`, `README.md`

**Interfaces:**
- Produces: package `vtts` is importable; `vtts.__version__ == "0.1.0"`; `uv run pytest` runs.

- [ ] **Step 1:** `git init` at the repo root, default branch `main`. Write `.gitignore` with the lines: `sanoTTS/`, `data/`, `artifacts/`, `.venv/`, `__pycache__/`, `*.wav`, `*.onnx`, `*.ckpt`, `.pytest_cache/`.
- [ ] **Step 2:** Write `tests/test_smoke.py`:

```python
import vtts

def test_version():
    assert vtts.__version__ == "0.1.0"
```

- [ ] **Step 3:** Run `uv run pytest -q`. Expected: FAIL (`ModuleNotFoundError: vtts`).
- [ ] **Step 4:** Create `pyproject.toml` (build backend hatchling, `requires-python = ">=3.11"`, dependencies `numpy`, `scipy`, `soundfile`, `pyarrow`, `huggingface_hub`; dev group `pytest`, `ruff`; extra `gpu` = `torch`, `transformers`, `torchmetrics[audio]`, `onnxruntime`; pytest marker `slow`, default `-m "not slow"`). Create `src/vtts/__init__.py` with `__version__ = "0.1.0"`. `README.md` of 5–10 lines in Vietnamese, pointing to the spec and the plans.
- [ ] **Step 5:** Run `uv sync && uv run pytest -q`. Expected: `1 passed`.
- [ ] **Step 6:** Commit everything, including `docs/` (spec + plan): `chore: scaffold vtts project with design spec and plan 1`.

---

### Task 2: Token set (phoneme set)

**Files:**
- Create: `src/vtts/frontend/__init__.py`, `src/vtts/frontend/phoneme_set.py`
- Test: `tests/frontend/test_phoneme_set.py`

**Interfaces:**
- Produces:
  - `PHONEME_SET_VERSION: str = "1"`
  - `TOKENS: tuple[str, ...]`, in exactly the order below (the ID is the index in the tuple)
  - `PAD, BOS, EOS, SPACE = "<pad>", "<bos>", "<eos>", " "`
  - `token_to_id(tok: str) -> int` (raises `KeyError` for an unknown token), `id_to_token(i: int) -> str`
  - `VOCAB_SIZE: int` (= 65)

Token order (fixed; changing it requires bumping the version):

```
<pad> <bos> <eos> " " , . ? ! ; :
O:b O:k O:ch O:d O:đ O:g O:gi O:h O:kh O:l O:m O:n O:ng O:nh O:p O:ph O:r O:s O:t O:th O:tr O:v O:x
G:w
N:a N:ă N:â N:e N:ê N:i N:o N:ô N:ơ N:u N:ư N:iê N:uô N:ươ N:oo
C:c C:ch C:m C:n C:ng C:nh C:p C:t C:j C:w
T1 T2 T3 T4 T5 T6
```

T1..T6 correspond to ngang, huyền, sắc, hỏi, ngã, nặng (level, falling, rising, dipping, broken, heavy).

- [ ] **Step 1:** Write the tests:

```python
from vtts.frontend import phoneme_set as ps

def test_vocab_layout():
    assert ps.VOCAB_SIZE == 65 == len(ps.TOKENS) == len(set(ps.TOKENS))
    assert ps.token_to_id("<pad>") == 0 and ps.token_to_id("<bos>") == 1
    assert ps.token_to_id("<eos>") == 2 and ps.token_to_id(" ") == 3
    assert ps.id_to_token(ps.token_to_id("N:ươ")) == "N:ươ"
    assert ps.TOKENS[-6:] == ("T1", "T2", "T3", "T4", "T5", "T6")

def test_unknown_token_raises():
    import pytest
    with pytest.raises(KeyError):
        ps.token_to_id("O:zz")
```

- [ ] **Step 2:** Run `uv run pytest tests/frontend/test_phoneme_set.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `phoneme_set.py` with exactly the token order above.
- [ ] **Step 4:** Run again. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(frontend): define versioned spelling-based token set`.

---

### Task 3: Syllable parsing

**Files:**
- Create: `src/vtts/frontend/syllable.py`
- Test: `tests/frontend/test_syllable.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `@dataclass(frozen=True) class Syllable: onset: str | None; glide: bool; nucleus: str; coda: str | None; tone: int` (tone 1..6). `onset`, `nucleus`, `coda` are names **without prefix** (e.g. `"k"`, `"iê"`, `"ng"`).
  - `parse_syllable(word: str) -> Syllable | None`: takes one syllable; handles NFC/NFD and uppercase itself; returns `None` if it is not a valid Vietnamese syllable.

Rules that the tests do not make self-evident, recorded here:
- The tone is taken from the combining tone mark after NFD (huyền U+0300, sắc U+0301, hỏi U+0309, ngã U+0303, nặng U+0323); the quality marks (U+0306 breve, U+0302 circumflex, U+031B horn) are recombined into the letter. Tone mark placement does not affect the result.
- Merge purely orthographic variants: `c/k/q → k`; `gh → g`; `ngh → ng`; `f → ph`; `w → v`; `z → d`; `j → gi`.
- `qu` → onset `k` + glide. `o`/`u` before the main vowel in `oa, oă, oe, uê, uy, uâ, uơ, uya, uyê` → glide.
- `gi`: if the remainder is empty or only a coda → nucleus `i` (`gì`, `gìn`); if the remainder starts with `ê` → nucleus `iê` (`giếng`); otherwise drop the `i` (`gia` → `gi`+`a`).
- Diphthongs: `iê/yê/ia/ya → iê`; `uô/ua → uô` (for `ua` when not preceded by `q`); `ươ/ưa → ươ`. `y` as nucleus → `i`. `oo → oo`; `ôô → ô`.
- Off-glides: `i/y` at the end of the rhyme → coda `j`; `o/u` at the end of the rhyme → coda `w`. Spelling exceptions: `ay → ă+j`, `au → ă+w`, `ây → â+j`, `âu → â+w`; `ai → a+j`, `ao → a+w`.

- [ ] **Step 1:** Write parameterized tests (`S(onset, glide, nucleus, coda, tone)`):

```python
CASES = [
 ("ba",      S("b", False, "a", None, 1)),
 ("mà",      S("m", False, "a", None, 2)),
 ("quốc",    S("k", True,  "ô", "c", 3)),
 ("nghiêng", S("ng", False, "iê", "ng", 1)),
 ("gì",      S("gi", False, "i", None, 2)),
 ("giếng",   S("gi", False, "iê", "ng", 3)),
 ("gia",     S("gi", False, "a", None, 1)),
 ("trường",  S("tr", False, "ươ", "ng", 2)),
 ("chuyện",  S("ch", True,  "iê", "n", 6)),
 ("khuya",   S("kh", True,  "iê", None, 1)),
 ("mua",     S("m", False, "uô", None, 1)),
 ("mưa",     S("m", False, "ươ", None, 1)),
 ("hòa",     S("h", True,  "a", None, 2)),
 ("tay",     S("t", False, "ă", "j", 1)),
 ("tai",     S("t", False, "a", "j", 1)),
 ("sáu",     S("s", False, "ă", "w", 3)),
 ("sao",     S("s", False, "a", "w", 1)),
 ("ăn",      S(None, False, "ă", "n", 1)),
 ("yêu",     S(None, False, "iê", "w", 1)),
 ("ý",       S(None, False, "i", None, 3)),
 ("đã",      S("đ", False, "a", None, 5)),
 ("nặng",    S("n", False, "ă", "ng", 6)),
 ("xoong",   S("x", False, "oo", "ng", 1)),
 ("rồi",     S("r", False, "ô", "j", 2)),
 ("dạ",      S("d", False, "a", None, 6)),
 ("kê",      S("k", False, "ê", None, 1)),
 ("ghế",     S("g", False, "ê", None, 3)),
 ("khuỷu",   S("kh", True,  "i", "w", 4)),
]
```

  Add 3 separate tests:
  - `test_tone_placement_and_case_insensitive`: `parse_syllable("hoà") == parse_syllable("hòa") == parse_syllable("HÒA") == parse_syllable(unicodedata.normalize("NFD", "hòa"))`.
  - `test_rejects_non_vietnamese`: `parse_syllable(x) is None` for `x` in turn `"wifi"`, `"email"`, `"abc"`, `"xyz"`, `""`, `"b"`.
  - `test_tone_marks_ignore_order`: an NFD string with the tone mark placed before the circumflex still gives the same result as the NFC string.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `parse_syllable`: split the onset by longest match, then the glide, then split the rhyme into nucleus + coda according to the rule table above.
- [ ] **Step 4:** Run the tests. Expected: all PASS.
- [ ] **Step 5:** Commit: `feat(frontend): Vietnamese syllable parser`.

---

### Task 4: G2P (syllable → token → ID) and golden

**Files:**
- Create: `src/vtts/frontend/g2p.py`, `scripts/frontend/export_frontend_golden.py`
- Test: `tests/frontend/test_g2p.py`

**Interfaces:**
- Consumes: `parse_syllable`, `Syllable` (Task 3); `TOKENS`, `token_to_id`, `BOS`, `EOS`, `SPACE` (Task 2).
- Produces:
  - `syllable_tokens(s: Syllable) -> list[str]`, in the order: `O:<onset>`? → `G:w`? → `N:<nucleus>` → `C:<coda>`? → `T<tone>`
  - `g2p(normalized: str) -> list[str]`. The input is **already normalized** text (Task 6): lowercase syllables separated by spaces, with the punctuation marks `, . ? ! ; :` as separate space-delimited tokens. Syllables are separated by `" "`. A punctuation mark **replaces** the adjacent space. Raises `ValueError` on an invalid syllable (the normalizer must remove those beforehand).
  - `encode(tokens: list[str]) -> list[int]`: adds `<bos>` at the start and `<eos>` at the end.

- [ ] **Step 1:** Write the tests:

```python
def test_sentence_tokens():
    assert g2p("xin chào , việt nam !") == [
        "O:x","N:i","C:n","T1"," ","O:ch","N:a","C:w","T2",",",
        "O:v","N:iê","C:t","T6"," ","O:n","N:a","C:m","T1","!"]

def test_dialect_distinctions_preserved():
    ids = lambda w: g2p(w)[0]
    assert len({ids("tra"), ids("cha")}) == 2
    assert len({ids("sa"), ids("xa")}) == 2
    assert len({ids("ra"), ids("da"), ids("gia")}) == 3

def test_encode_wraps_bos_eos():
    out = encode(g2p("ba"))
    assert out[0] == 1 and out[-1] == 2 and len(out) == 5

def test_invalid_syllable_raises():
    with pytest.raises(ValueError):
        g2p("wifi")
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `g2p.py`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Write `scripts/frontend/export_frontend_golden.py --sentences <file.txt> --out tests/fixtures/frontend_golden.jsonl`. Each line: `{"text", "normalized", "tokens", "ids", "phoneme_set_version"}`. It uses `text_to_ids` from Task 6, so the script can only run after Task 6; in Task 4 only the skeleton is written. The golden is generated at the end of Task 6.
- [ ] **Step 6:** Commit: `feat(frontend): token-level G2P and id encoding`.

---

### Task 5: Vietnamese number reading (standard Northern accent)

**Files:**
- Create: `src/vtts/frontend/numbers.py`
- Test: `tests/frontend/test_numbers.py`

**Interfaces:**
- Produces:
  - `read_int(n: int) -> str`: only for non-negative integers `< 10**15`; larger numbers are read digit by digit.
  - `read_number_token(tok: str) -> str`: accepts forms such as `"-5"`, `"1.000.000"`, `"3,5"`, `"1.5"`, `"007"`.

Rules (Northern accent):
- Units after `mươi` (20 and above): 1 → `mốt`, 4 → `tư`, 5 → `lăm`.
- Units after `mười`: 5 → `lăm`.
- Tens digit is 0 but hundreds digit is non-zero → `linh`.
- Use `nghìn`, `triệu`, `tỷ`, `nghìn tỷ`. A middle 3-digit group equal to 0 is skipped entirely. A non-leading group with a non-zero value < 100 → prefix `không trăm` (plus `linh` if < 10).
- A dot followed by exactly 3-digit groups → thousands separator. A comma → decimal `phẩy`. A dot not in 3-digit-group form → `chấm`. A leading minus sign → `âm`. A string with leading zeros (`007`) → read digit by digit.

- [ ] **Step 1:** Write parameterized tests:

```python
CASES = [(0,"không"),(10,"mười"),(15,"mười lăm"),(21,"hai mươi mốt"),
 (24,"hai mươi tư"),(25,"hai mươi lăm"),(105,"một trăm linh năm"),
 (1005,"một nghìn không trăm linh năm"),(1050,"một nghìn không trăm năm mươi"),
 (1500,"một nghìn năm trăm"),(1000500,"một triệu năm trăm"),
 (2026,"hai nghìn không trăm hai mươi sáu"),(1000000000,"một tỷ")]
TOKENS = [("1.000.000","một triệu"),("3,5","ba phẩy năm"),("-5","âm năm"),
 ("1.5","một chấm năm"),("007","không không bảy")]
```

  Add a test: `read_int(10**15)` returns a 16-word string (`"một"` followed by 15 times `"không"`).
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(frontend): Northern Vietnamese number reading`.

---

### Task 6: Text normalization, sentence splitting, `text_to_ids`

**Files:**
- Create: `src/vtts/frontend/normalize.py`, `src/vtts/frontend/lexicon.py` (abbreviation, loanword and letter-name tables), `src/vtts/frontend/text.py`
- Test: `tests/frontend/test_normalize.py`, `tests/frontend/test_text.py`

**Interfaces:**
- Consumes: `read_int`, `read_number_token` (Task 5); `parse_syllable` (Task 3); `g2p`, `encode` (Task 4).
- Produces:
  - `normalize(text: str) -> str`: the output consists only of valid lowercase Vietnamese syllables plus the punctuation marks `, . ? ! ; :`, all separated by a single space.
  - `split_sentences(text: str, max_syllables: int = 40) -> list[str]`: split on `. ! ? ;`; any chunk longer than 40 syllables is further split on commas, then hard-cut at 40.
  - `text_to_ids(text: str) -> list[list[int]]`: one ID list per chunk; empty or punctuation-only text → `[]`.
  - `ABBREVIATIONS: dict[str, str]`, `LOANWORDS: dict[str, str]`, `LETTER_NAMES: dict[str, str]` in `lexicon.py`.

Processing rules (in order): NFC → whitespace → special patterns (dates `d/m/yyyy`, `d/m` with d ≤ 31 and m ≤ 12; times `8:30`, `8h30`, `8h`; `%`; currency `đ`, `VNĐ`, `$`, `USD`; units `km`, `kg`, `m`, `cm`, `°C`) → abbreviations → numbers → lowercase → for each word: if `parse_syllable` accepts it, keep it; if it is in `LOANWORDS`, replace it; otherwise spell it out using `LETTER_NAMES`. Characters that are not letters, digits or supported punctuation (emoji, `@`, `/`, ...) → dropped. `… → .`; `– — → ,`; brackets and quotes → dropped.

Letter names (Northern accent): a→`a`, b→`bê`, c→`xê`, d→`dê`, đ→`đê`, e→`e`, f→`ép`, g→`giê`, h→`hát`, i→`i`, j→`gi`, k→`ca`, l→`e lờ`, m→`em mờ`, n→`en nờ`, o→`o`, p→`pê`, q→`quy`, r→`e rờ`, s→`ét xì`, t→`tê`, u→`u`, v→`vê`, w→`vê kép`, x→`ích xì`, y→`i dài`, z→`dét`.

Minimum `LOANWORDS`: `wifi→oai phai`, `email→i meo`, `ok→ô kê`, `internet→in tơ nét`, `video→vi đê ô`, `online→online`→`on lai`.
Minimum `ABBREVIATIONS`: `TP.HCM→thành phố hồ chí minh`, `TP.→thành phố`, `Q.→quận`, `P.→phường`, `HN→hà nội`, `VN→việt nam`, `v.v.→vân vân`.

- [ ] **Step 1:** Write tests for `normalize`:

```python
CASES = [
 ("14/11/2026", "ngày mười bốn tháng mười một năm hai nghìn không trăm hai mươi sáu"),
 ("8:30", "tám giờ ba mươi phút"), ("8h", "tám giờ"),
 ("50%", "năm mươi phần trăm"), ("100.000đ", "một trăm nghìn đồng"),
 ("5 USD", "năm đô la"), ("5km", "năm ki lô mét"), ("25°C", "hai mươi lăm độ xê"),
 ("TP.HCM", "thành phố hồ chí minh"), ("ABC", "a bê xê"), ("wifi", "oai phai"),
 ("Xin chào, Việt Nam!", "xin chào , việt nam !"),
 ("ĐƯỜNG", "đường"), ("Bật đèn 😀 nhé", "bật đèn nhé"),
 ("Gửi tới a@b.com", "gửi tới a bê xê o em mờ"),  # @ and . are dropped, the letters are spelled out
]
```

  Tests for `text.py`:
  - `test_empty_inputs`: `text_to_ids(x) == []` for `x` in `""`, `"   "`, `"..."`, `"😀"`.
  - `test_long_paragraph_chunked`: a 150-syllable paragraph with a few commas → every chunk has ≤ 40 syllables, and concatenating the chunks preserves all syllables in the original order.
  - `test_never_emits_unknown_ids`: run a list of 30 hard strings (English, URLs, symbols, large numbers, mixed letters and digits such as `A4`, `iPhone15`) → every ID is in `range(VOCAB_SIZE)` and no exception is raised.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `lexicon.py`, `normalize.py`, `text.py`.
- [ ] **Step 4:** Run `uv run pytest tests/frontend -q`. Expected: all PASS.
- [ ] **Step 5:** Write `tests/fixtures/frontend_sentences.txt` (about 200 sentences: 100 taken from the tests and examples above, 100 hand-written ones covering all groups of the out-of-domain (OOD) set in Task 10). Run `uv run python scripts/frontend/export_frontend_golden.py --sentences tests/fixtures/frontend_sentences.txt --out tests/fixtures/frontend_golden.jsonl`. Add a test `test_golden_stable` that re-checks the entire golden.
- [ ] **Step 6:** Commit: `feat(frontend): text normalization, sentence chunking, golden fixture`.

---

### Task 7: Audio processing and InfoRe1 preparation

**Files:**
- Create: `src/vtts/data/__init__.py`, `src/vtts/data/audio.py`, `src/vtts/data/infore.py`, `scripts/data/prepare_infore.py`
- Test: `tests/data/test_audio.py`, `tests/data/test_infore.py`

**Interfaces:**
- Produces:
  - `resample(x: np.ndarray, sr_in: int, sr_out: int = 22050) -> np.ndarray`: uses `scipy.signal.resample_poly` with the ratio reduced by gcd.
  - `trim_silence(x: np.ndarray, sr: int, top_db: float = 40.0, pad_ms: float = 50.0) -> np.ndarray`: computes per-frame RMS (25 ms window, 10 ms hop), keeps the span from the first to the last frame with RMS ≥ max − top_db, plus padding.
  - `normalize_loudness(x: np.ndarray, target_rms_db: float = -23.0, peak_db: float = -1.0) -> np.ndarray`
  - `prepare_infore(parquet_dir: Path, out_dir: Path) -> PrepareReport`: writes `out_dir/wavs/infore_{i:05d}.wav` (22,050 Hz, PCM16) and `out_dir/metadata.csv` (`|`-separated: `id|text|duration_s`). Rows with broken audio or an empty transcript → skipped and recorded in `report.skipped` (list of `(index, reason)`).
  - `@dataclass PrepareReport: n_in: int; n_out: int; hours: float; skipped: list[tuple[int, str]]`

- [ ] **Step 1:** Write the tests:
  - `test_resample_44100_to_22050`: a 1 kHz sine of 1 second → length 22050 ± 1, peak frequency 1000 ± 5 Hz.
  - `test_trim_silence`: 0.5 s silence + 1 s sine + 0.5 s silence → length about 1.1 s (± 0.05 s).
  - `test_loudness`: output RMS is −23 ± 0.5 dB, peak ≤ −1 dB.
  - `test_prepare_infore_tiny`: create in `tmp_path` a 3-row parquet file with the InfoRe schema (column `audio` is a struct `{bytes, path}` containing 44.1 kHz WAV, column `transcription` is a string). One row has an empty transcript. Expected: `n_out == 2`, `skipped == [(index_of_empty, "empty_transcript")]`, metadata has 2 rows, the wav read back has sr = 22050.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. The script `scripts/data/prepare_infore.py --download-to data/infore1/raw --out data/infore1/prepared` uses `huggingface_hub.snapshot_download(repo_id="doof-ferb/infore1_25hours", repo_type="dataset")`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(data): audio utils and InfoRe1 preparation`.

---

### Task 8: Evaluation metrics

**Files:**
- Create: `src/vtts/eval/__init__.py`, `src/vtts/eval/cer.py`, `src/vtts/eval/whistle.py`, `src/vtts/eval/asr.py`, `src/vtts/eval/mos.py`
- Test: `tests/eval/test_cer.py`, `tests/eval/test_whistle.py`, `tests/eval/test_models_slow.py`

**Interfaces:**
- Consumes: `normalize` (Task 6).
- Produces:
  - `prep_for_cer(text: str) -> str`: passes through `normalize`, removes punctuation, collapses whitespace. **Keeps tone marks**.
  - `cer(ref: str, hyp: str) -> float` and `wer(ref: str, hyp: str) -> float`: self-implemented Levenshtein distance divided by the length of ref; both strings go through `prep_for_cer`.
  - `corpus_cer(pairs: list[tuple[str, str]]) -> float`: total errors divided by total length.
  - `whistle_score(x: np.ndarray, sr: int) -> float`. Algorithm: STFT (n_fft 2048, hop 256, Hann window), converted to dB; only bins in 2–8 kHz are considered. A (bin, frame) cell is "tonal" if it is at least 15 dB above the median of the ±20 neighboring bins. Count the cells belonging to same-bin tonal runs lasting ≥ 8 consecutive frames. Score = that count divided by the number of seconds.
  - `class AsrTranscriber: __init__(model_id: str = "vinai/PhoWhisper-large", device: str | None = None); transcribe(paths: list[Path], batch_size: int = 8) -> list[str]`
  - `dnsmos(x: np.ndarray, sr: int) -> dict[str, float]` (keys `sig`, `bak`, `ovrl`; uses torchmetrics DNSMOS)
  - `utmos(x: np.ndarray, sr: int) -> float` (SpeechMOS `utmos22_strong` via `torch.hub`)

- [ ] **Step 1:** Write the tests:
  - `test_cer_tone_sensitive`: `cer("ma", "mà") == 0.5` (one wrong character out of 2).
  - `test_cer_ignores_case_punct_and_digits`: `cer("Hai mươi mốt.", "hai mươi mốt") == 0.0` and `cer("21", "hai mươi mốt") == 0.0`.
  - `test_corpus_cer`: for `[("ab", "ab"), ("abcd", "abcf")]`, the result is `1/6`.
  - `test_whistle_detects_tone`: 2 s of white noise → score `< 5`; the same noise plus a 4 kHz sine at −20 dB → score `> 50`.
  - `test_models_slow` (marked `@pytest.mark.slow`): `AsrTranscriber` transcribes a sample wav file to a non-empty string; `dnsmos` returns all 3 keys with values in [1, 5]; `utmos` returns a value in [1, 5].
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Heavy models are imported lazily (import inside the function), so fast tests on the Mac do not need torch.
- [ ] **Step 4:** Run `uv run pytest tests/eval -q`. Expected: PASS (`slow` tests skipped).
- [ ] **Step 5:** Commit: `feat(eval): CER/WER, whistle score, ASR and MOS wrappers`.

---

### Task 9: Data filtering, splitting, data report

**Files:**
- Create: `src/vtts/data/filter.py`, `src/vtts/data/splits.py`, `src/vtts/data/report.py`, `scripts/data/score_dataset.py` (runs on GPU), `scripts/data/filter_and_split.py`
- Test: `tests/data/test_filter.py`, `tests/data/test_splits.py`

**Interfaces:**
- Consumes: `cer` (Task 8), `g2p`/`normalize` (Task 4, Task 6), the `metadata.csv` format (Task 7).
- Produces:
  - `@dataclass Row: id: str; text: str; duration_s: float; asr: str | None = None; dnsmos_ovrl: float | None = None`
  - `apply_filters(rows: list[Row], cer_max: float = 0.10, dnsmos_min: float = 3.0, dur_min: float = 1.0, dur_max: float = 15.0) -> tuple[list[Row], dict[str, int]]`: the second dict counts rejected rows per reason (`cer`, `dnsmos`, `too_short`, `too_long`, `invalid_text`). `invalid_text` is a row for which `normalize` + `g2p` raises.
  - `make_splits(rows: list[Row], n_heldout: int = 50, val_frac: float = 0.02, seed: int = 1234) -> dict[str, list[Row]]` (keys `train`, `val`, `heldout`); deterministic; the held-out set only picks sentences of 3–10 s.
  - `dataset_report(splits) -> dict`: hours and sentence count per split, duration histogram (1 s bins), distribution of the 6 tone tokens on the train set.
  - `scripts/data/score_dataset.py --prepared data/infore1/prepared --out data/infore1/scores.jsonl`: runs ASR + DNSMOS, writes one line per row `{id, asr, dnsmos_ovrl}`.
  - `scripts/data/filter_and_split.py --prepared ... --scores ... --out data/infore1/final`: writes `train.csv`, `val.csv`, `heldout.csv` (same format as metadata, the text column is the original text) and `report.json`. **If train < 18 hours, print a warning**, with a suggestion to relax thresholds.

- [ ] **Step 1:** Write the tests:
  - `test_filters_each_reason`: 6 fake rows, each violating exactly one reason, plus 1 clean row → 1 is kept, and each reason counts exactly 1.
  - `test_splits_deterministic_and_disjoint`: 500 fake rows → two calls give the same result; the three splits are disjoint; `len(heldout) == 50`; every held-out sentence is 3–10 s long.
  - `test_report_tone_distribution_sums`: the tone distribution sums to the total number of syllables.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(data): quality filters, deterministic splits, dataset report`.

---

### Task 10: Out-of-domain evaluation sentence set and evaluation CLI

**Files:**
- Create: `eval/sets/ood.jsonl`, `src/vtts/eval/run_eval.py`, `scripts/eval/eval_dir.py`
- Test: `tests/eval/test_run_eval.py`

**Interfaces:**
- Consumes: `corpus_cer`, `cer`, `whistle_score`, `AsrTranscriber`, `utmos`, `dnsmos` (Task 8).
- Produces:
  - Sentence set format (JSONL): `{"id": str, "text": str, "group": str}`.
  - `@dataclass ClipScore: id; cer; wer; whistle; utmos: float | None; dnsmos_ovrl: float | None`
  - `@dataclass EvalReport: system: str; set_name: str; corpus_cer: float; corpus_wer: float; mean_whistle: float; mean_utmos: float | None; mean_dnsmos: float | None; clips: list[ClipScore]`
  - `evaluate(system: str, set_name: str, audio_dir: Path, sentences: list[dict], asr: Callable[[list[Path]], list[str]], mos: bool = True) -> EvalReport`. The audio file for the sentence with id `X` is `audio_dir/X.wav`; if files are missing, raises `FileNotFoundError` with the list of missing ids.
  - `scripts/eval/eval_dir.py --system NAME --set eval/sets/ood.jsonl --audio DIR --out reports/NAME-SET.json [--no-mos]`

- [ ] **Step 1:** Write `eval/sets/ood.jsonl` with 50 hand-written sentences, split evenly into 5 groups (`group`), 10 sentences each: `device` (device notifications), `numbers` (numbers, dates, times, money), `names` (person and place names), `prosody` (questions, exclamations), `long` (over 30 syllables).
- [ ] **Step 2:** Write the test `test_evaluate_with_fake_asr`: 3 sentences, audio is sine files, a fake ASR returns the correct text for 2 sentences and one wrong word for the third, `mos=False` → `corpus_cer` exactly equals the hand-computed value; `test_missing_audio_lists_ids`: with 1 file missing, an error containing that id is raised.
- [ ] **Step 3:** Run the tests. Expected: FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Run the tests. Expected: PASS.
- [ ] **Step 6:** Commit: `feat(eval): OOD sentence set and evaluation runner`.

---

### Task 11: Baselines (black box) and baseline report

**Files:**
- Create: `eval/baselines/pyproject.toml` (separate venv, **not** a workspace member of `vtts`), `eval/baselines/render.py`, `eval/baselines/README.md`, `docs/reports/baseline.md`

**Interfaces:**
- Consumes: the sentence set JSONL files (Task 10; the held-out set comes from Task 12, so the held-out run happens after Task 12); `normalize` (Task 6). The baseline script calls `vtts` via subprocess (`uv run --project ../.. python -c ...`) to obtain normalized text, with **no cross-imports** between the two venvs.
- Produces: `render.py --system {sanotts-vi,piper-25h} --set FILE --out DIR` writes `DIR/<id>.wav`.
  - `sanotts-vi`: `pip install sanotts`, voice `vi`.
  - `piper-25h`: `pip install piper-tts`, model `vi_VN-25hours_single-low` (downloaded from `rhasspy/piper-voices`).
  - The input to both systems is **text already passed through `vtts`'s `normalize`**, so that number reading is identical across systems.

- [ ] **Step 1:** Create the separate venv: `cd eval/baselines && uv sync`. Try `render.py` with 2 sentences for each system. Expected: 2 wav files per system, each longer than 0.5 s.
- [ ] **Step 2:** Render the full `ood.jsonl` set for both systems into `artifacts/baselines/<system>/ood/`.
- [ ] **Step 3:** Run `scripts/eval/eval_dir.py` for both (on the Mac using MPS for the 50 sentences, or on the GPU machine). Expected: two `reports/*.json` files.
- [ ] **Step 4:** Write `docs/reports/baseline.md` (in Vietnamese): a table of CER, WER, UTMOS, DNSMOS and whistle index for the two systems, broken down by sentence group; state clearly which ASR model was used; give the teacher gate thresholds derived from the measurements (≤ 50% of the CER of `sanotts-vi` and ≤ the CER of `piper-25h`).
- [ ] **Step 5:** Commit: `feat(eval): black-box baselines and baseline report (ood set)`.

---

### Task 12: Run the data pipeline on the GPU machine

**Files:**
- Create: `docs/reports/dataset-infore1.md`, `scripts/remote/README.md` (the commands used on the GPU machine)

**Interfaces:**
- Consumes: Task 7, Task 9, Task 11.
- Produces on the GPU machine: `data/infore1/final/{train,val,heldout}.csv`, `wavs/`, `report.json`. Sync `heldout.csv` and `report.json` back to the Mac (`eval/sets/heldout.jsonl` is created from `heldout.csv`).

- [ ] **Step 1:** Prepare the GPU machine (SSH) and sync the code to it.
- [ ] **Step 2:** In the container: clone the repo (or rsync), run `uv sync --extra gpu`, then `nvidia-smi` and `uv run python -c "import torch; print(torch.cuda.is_available())"`. Expected: the RTX 3060 is visible and `True` is printed.
- [ ] **Step 3:** `uv run pytest -q -m slow`. Expected: PASS.
- [ ] **Step 4:** `uv run python scripts/data/prepare_infore.py ...`. Expected: `n_out` close to 14,935, about 25 hours.
- [ ] **Step 5:** `uv run python scripts/data/score_dataset.py ...` (run in the background, with a log).
- [ ] **Step 6:** `uv run python scripts/data/filter_and_split.py ...`. Expected: train ≥ 18 hours. If below 18 hours: relax `cer_max` to 0.15, rerun, and record the reason in the report.
- [ ] **Step 7:** Create `eval/sets/heldout.jsonl` from `heldout.csv`. Render the baselines for the held-out set (Task 11, steps 2–3), and update `docs/reports/baseline.md` with both sentence sets.
- [ ] **Step 8:** Write `docs/reports/dataset-infore1.md`: sentence count and hours before/after filtering, number of rejected rows per reason, duration histogram, tone distribution, and 10 sentences rejected for CER together with their transcript and ASR output (so the maintainer can check whether the threshold is reasonable).
- [ ] **Step 9:** Commit: `docs: InfoRe1 dataset report and heldout baseline numbers`.

**Plan 1 exit gate:** all tests pass (including the `slow` tests on the GPU machine); train ≥ 18 hours; `baseline.md` has measurements for both systems on both sentence sets. Then write Plan 2 (teacher).
