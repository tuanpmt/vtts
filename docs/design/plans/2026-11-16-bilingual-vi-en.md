# Bilingual Vietnamese–English model — Implementation plan

> **Status:** in progress (2026-11-17). Done: token set v2 (107 tokens), the Python English front-end (CMUdict lexicon, learned letter-to-sound, normalizer, per-word language tagging), the VoxCPM2 synthesis client and corpus builder; about 98 h of synthesized speech per voice for `nam-1` (male) and `nu-10` (female). In progress: teacher training. Pending: the C port of the English front-end for the device, students, release. Design: [specs/2026-11-16-bilingual-vi-en-design.md](../specs/2026-11-16-bilingual-vi-en-design.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single `.vtts` model file that reads Vietnamese, English and sentences mixing both languages in one voice, running faster than real time on the ESP32-P4 and ESP32-S3.

**Architecture:**
- Token set v2 = the existing 65 Vietnamese tokens + 39 ARPAbet phonemes + 3 stress tokens.
- New front-end:
  - per-word language tagging;
  - English normalization;
  - English G2P: CMUdict → suffix stripping → NRL rules → spelling out.
- The front-end has a Python version and a C version whose outputs match.
- Training data is synthesized with a self-hosted VoxCPM2 server and filtered automatically.
- Then follow the existing pipeline: VITS teacher → distillation → int8 → firmware.

**Tech Stack:** Python 3.11 (uv, PyTorch, transformers), C99 (runtime without `malloc`), ESP-IDF v6.1, CMUdict (BSD), VoxCPM2 (Apache-2.0, via HTTP API).

**Spec:** `docs/design/specs/2026-11-16-bilingual-vi-en-design.md`

## Global Constraints

- Do not read or take GPL code: espeak-ng, phonemizer, misaki, piper-phonemize, g2p_en, vPhon, the GPL files of sanoTTS.
- v1 tokens keep ids 0–64 unchanged.
- v2 tokens:
  - `EN:<ARPAbet>` ids 65–103, in exactly the order `AA AE AH AO AW AY B CH D DH EH ER EY F G HH IH IY JH K L M N NG OW OY P R S SH T TH UH UW V W Y Z ZH`;
  - `S0 S1 S2` ids 104–106;
  - `VOCAB_SIZE_V2 = 107`, `PHONEME_SET_VERSION_V2 = "2"`.
- The behavior of token set v1 (`text_to_ids(text)` without the new parameter) must match the current output ID for ID: old tests and fixtures must pass unmodified.
- Each ID chunk ≤ `VTTS_TEXT_MAX_IDS` (320), including BOS/EOS.
- The VoxCPM2 URL and key are read only from `~/.config/vtts/voxcpm.env` (`VOXCPM_URL`, `VOXCPM_KEY`). Never written to the repo, logs or manifests.
- Training audio is stored as 22050 Hz mono PCM16.
- C runtime: no `malloc`, C99; the lexicon is read only through a blob pointer.
- On-chip lexicon ≤ 1.5 MB. Model ≤ 3 MB.
- Documentation in Vietnamese with full diacritics (project convention at the time; the documentation has since been translated to English). Code, file names and commits in English.
- Commits end with the two lines `Co-Authored-By` / `Claude-Session`, like previous commits.
- The acceptance criteria in section 6 of the spec are the final gate (Task 17).

## Review Focus

1. **English words attached to punctuation, possessives, hyphens** ("Apple's", "Wi-Fi", "state-of-the-art,"): read the word correctly, do not spell out the whole cluster. Tests in Task 6.
2. **Uppercase letters mixed with digits** ("USB-C", "4K", "MP3", "iPhone 15"): spell out the letters, read the numbers in the sentence's language. Tests in Task 5 and Task 6.
3. **Vietnamese typed without diacritics in `vi` mode** ("xin chao ban"): words that form a valid syllable are still read as Vietnamese, not switched to English. Tests in Task 6.
4. **Very long English sentences without punctuation**: always cut into chunks of ≤ 320 IDs, with no errors and no lost words. Tests in Task 6 (Python) and Task 8 (C).
5. **API errors, empty audio, truncated audio or wrong sample rate**: retry, then mark as failed in the manifest. Never write a broken wav into the dataset. Tests in Task 10.

---

## File structure

| File | Responsibility |
|---|---|
| `src/vtts/frontend/phoneme_set.py` (modified) | Add `TOKENS_V2`, `VOCAB_SIZE_V2`, `token_to_id_v2` |
| `src/vtts/frontend/en/cmudict.py` | Download CMUdict (pinned commit), parse, map to v2 tokens |
| `src/vtts/frontend/en/lts.py` | NRL letter-to-sound rules (written from scratch from the 1976 paper) |
| `src/vtts/frontend/en/g2p_en.py` | English word → tokens: lexicon → suffix → rules → spelling |
| `src/vtts/frontend/en/normalize_en.py` | English numbers, dates, times, currency, units, abbreviations |
| `src/vtts/frontend/lang.py` | Per-word language tagging, `vi`/`en`/`auto` modes |
| `src/vtts/frontend/text.py` (modified) | `text_to_ids(text, lang=None)`: `None` = v1 as before; `"vi"`/`"en"`/`"auto"` = v2 |
| `scripts/frontend/build_lexicon.py` | Build the `lex_en.bin` lexicon blob for the chip |
| `runtime/src/vtts_lex.c`, `runtime/include/vtts_lex.h` | Read the lexicon blob |
| `runtime/src/vtts_text_en.c` | Normalization, NRL rules, English G2P, language tagging (C) |
| `runtime/src/vtts_text.c`, `runtime/include/vtts_text.h` (modified) | `vtts_text_to_ids_ex` with a language option |
| `scripts/data/build_bilingual_corpus.py` | VI sentence set (covering rare syllables), EN, mixed sentences |
| `scripts/data/synth_voxcpm.py`, `src/vtts/data/voxcpm_client.py` | API client: parallel, retrying, resumable |
| `scripts/data/filter_synth.py`, `src/vtts/eval/speaker_sim.py` | Filter by CER, speaker similarity, DNSMOS, speaking rate |
| `src/vtts/teacher/data.py`, `scripts/student/build_distill_pack.py` (modified) | Read the language column, use v2 tokens |
| `eval/sets/ood_en.jsonl`, `eval/sets/mixed.jsonl` | New evaluation sentence sets |
| `firmware/esp32/main/main.c`, `CMakeLists.txt` (modified) | `lang` command, embedded lexicon, bilingual model slot |

---

### Task 1: Token set v2

**Files:**
- Modify: `src/vtts/frontend/phoneme_set.py`
- Modify: `runtime/tools/gen_text_tables.py`, `runtime/src/vtts_text_tables.h` (generated)
- Test: `tests/frontend/test_phoneme_set.py`

**Interfaces:**
- Produces:
  - `ARPABET: tuple[str, ...]` (39 phonemes, in exactly the order given in Global Constraints)
  - `TOKENS_V2: tuple[str, ...]`, `VOCAB_SIZE_V2 = 107`, `PHONEME_SET_VERSION_V2 = "2"`
  - `token_to_id_v2(tok: str) -> int`
  - C: `VTTS_EN_BASE 65`, `VTTS_STRESS_BASE 104`

- [ ] **Step 1: Write the test**

```python
def test_v2_extends_v1():
    assert TOKENS_V2[:VOCAB_SIZE] == TOKENS and VOCAB_SIZE_V2 == 107
    assert token_to_id_v2("EN:AA") == 65 and token_to_id_v2("EN:ZH") == 103
    assert [token_to_id_v2(f"S{i}") for i in range(3)] == [104, 105, 106]
```

- [ ] **Step 2:** `uv run pytest tests/frontend/test_phoneme_set.py -q`. Expected: FAIL (`TOKENS_V2` does not exist yet).
- [ ] **Step 3:** Add the constants and function to `phoneme_set.py`. Make `gen_text_tables.py` also emit `VTTS_EN_BASE` and `VTTS_STRESS_BASE`, then rerun it to regenerate the header.
- [ ] **Step 4:** `uv run pytest tests/frontend -q`. Expected: PASS, including the old v1 tests.
- [ ] **Step 5:** Commit `frontend: phoneme set v2 (Vietnamese + ARPAbet + stress)`.

### Task 2: CMUdict

**Files:**
- Create: `src/vtts/frontend/en/__init__.py`, `src/vtts/frontend/en/cmudict.py`
- Test: `tests/frontend/test_cmudict.py`

**Interfaces:**
- Produces:
  - `load_cmudict(path: Path | None = None) -> dict[str, list[str]]`: lowercase word → v2 tokens of the first pronunciation (e.g. `["EN:HH","EN:AH","S0","EN:L","EN:OW","S1"]`). By default downloads to `data/cmudict/cmudict.dict` from a pinned URL and commit, verifying the SHA256.
  - `arpabet_to_tokens(phones: list[str]) -> list[str]`: separates the stress digit from vowels into an `S0`/`S1`/`S2` token placed immediately after.

- [ ] **Step 1: Write the test**

```python
def test_hello():
    assert arpabet_to_tokens(["HH", "AH0", "L", "OW1"]) == ["EN:HH", "EN:AH", "S0", "EN:L", "EN:OW", "S1"]

def test_lexicon_loads():
    lex = load_cmudict()
    assert len(lex) > 120_000 and lex["bluetooth"][0] == "EN:B"
```

- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
  - Drop `word(2)` variants and `#` comments.
  - Add the `LICENSE`/`NOTICE` attribution for CMUdict (BSD) to `NOTICE`.
  - Add `data/cmudict/` to `.gitignore`.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit `frontend: CMUdict lexicon (BSD) mapped to v2 tokens`.

### Task 3: NRL letter-to-sound rules

**Files:**
- Create: `src/vtts/frontend/en/lts.py`
- Test: `tests/frontend/test_lts.py`

**Interfaces:**
- Produces: `lts(word: str) -> list[str]`, returning v2 tokens with stress.
  - The NRL rules carry no stress. Assign `S1` to the first vowel and `S0` to the remaining vowels.

- [ ] **Step 1: Write the test**
  - `lts("cat") == ["EN:K","EN:AE","S1","EN:T"]`
  - `lts("ship")[0] == "EN:SH"`
  - On 2,000 randomly sampled CMUdict words with seed 0 (ignoring stress): phoneme error rate ≤ 0.35.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
  - Rewrite the rule table from scratch from the 1976 NRL report (public domain): `[left] match [right] = sound`, scanning left to right.
  - Cite the source at the top of the file.
  - Do not consult GPL code.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit `frontend: NRL letter-to-sound rules for out-of-lexicon English words`.

### Task 4: English G2P for a single word

**Files:**
- Create: `src/vtts/frontend/en/g2p_en.py`
- Test: `tests/frontend/test_g2p_en.py`

**Interfaces:**
- Consumes: `load_cmudict`, `lts`.
- Produces: `g2p_word_en(word: str) -> list[str]`, in priority order:
  1. look up the lexicon;
  2. uppercase word of ≤ 4 letters not in the lexicon → spell out the letter names;
  3. strip the suffixes `'s`, `s`, `es`, `ed`, `ing`, `er`, `ly` when the stem is in the lexicon;
  4. split a compound into two parts that are both in the lexicon, each part ≥ 3 letters;
  5. use `lts`.

- [ ] **Step 1: Write the test**
  - `"Apple's"` = the pronunciation of `apple` + `EN:Z`.
  - `"USB"` is spelled out as three letter names (`Y UW1 | EH1 S | B IY1`).
  - `"smartwatches"` via compound splitting and suffix stripping.
  - `"zzyzx"` does not fail and returns at least 1 token.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement in exactly the order above.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit `frontend: English word G2P (lexicon, morphology, rules, spelling)`.

### Task 5: English normalization

**Files:**
- Create: `src/vtts/frontend/en/normalize_en.py`
- Test: `tests/frontend/test_normalize_en.py`

**Interfaces:**
- Produces: `normalize_en(text: str) -> str`, returning lowercase words and punctuation (`, . ? ! ; :`) separated by spaces, following the same convention as the Vietnamese `normalize()`.

- [ ] **Step 1: Write the test** (exact values)

| Input | Output |
|---|---|
| `"It costs $5.50."` | `"it costs five dollars fifty cents ."` |
| `"Meet at 3:30 pm on 11/16/2026"` | `"meet at three thirty p m on november sixteenth twenty twenty six"` |
| `"21st"` | `"twenty first"` |
| `"1,250"` | `"one thousand two hundred fifty"` |
| `"Dr. Smith"` | `"doctor smith"` |
| `"USB-C"` | `"u s b c"` |
| `"4K"` | `"four k"` |
| `"25°C"` | `"twenty five degrees celsius"` |
| `"50%"` | `"fifty percent"` |

- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
  - 4-digit years are read in pairs (2026 → "twenty twenty six"), except 2000–2009 → "two thousand (and) N".
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit `frontend: English text normalization`.

### Task 6: Language tagging and bilingual `text_to_ids` (Python)

**Files:**
- Create: `src/vtts/frontend/lang.py`
- Modify: `src/vtts/frontend/text.py`
- Test: `tests/frontend/test_lang.py`, `tests/frontend/test_text_bilingual.py`

**Interfaces:**
- Consumes: `normalize`, `parse_syllable`, `normalize_en`, `g2p_word_en`, `token_to_id_v2`.
- Produces:
  - `sentence_lang(sentence: str, mode: str) -> str`: `mode` is `"vi"`, `"en"` or `"auto"`; with `auto`, a sentence whose share of words carrying Vietnamese diacritics is ≥ 0.2 is `"vi"`.
  - `tag_words(sentence: str, mode: str) -> list[tuple[str, str]]`: a list of (original word, `"vi"`/`"en"`) pairs.
  - `text_to_ids(text: str, lang: str | None = None) -> list[list[int]]`:
    - `lang=None` gives exactly the current v1 output;
    - other values return v2 IDs;
    - chunks are closed by ID count (≤ 320), preferring to cut at commas.

**Language tagging rules** (per spec 5.2):
- A word with Vietnamese diacritics or `đ` is always `vi`.
- `vi` mode:
  - a word that forms a valid syllable → `vi`;
  - a word in `LOANWORDS` → `vi`, read in its Vietnamized form;
  - all other words → `en`.
- `en` mode: every word without diacritics → `en`.
- Numbers and symbols follow the language of the sentence containing them.
- Consecutive runs of the same language are normalized with that language's normalizer.

- [ ] **Step 1: Write the test**
  - `tag_words("Đã kết nối Bluetooth với AirPods", "vi")` tags exactly `Bluetooth` and `AirPods` as `en`.
  - `tag_words("xin chao ban", "vi")` tags everything `vi` (Review Focus 3).
  - `text_to_ids("Wi-Fi, Apple's state-of-the-art phone.", "en")` contains no spelled-out tokens for `wi`/`fi`/`apple` (Review Focus 1).
  - `"iPhone 15 có giá 20 triệu"` in `vi` mode: numbers are read in Vietnamese; `"iPhone 15 costs $799"` in `en` mode: numbers are read in English (Review Focus 2).
  - A 400-word English string without punctuation: every chunk ≤ 320 IDs and the total word count is unchanged (Review Focus 4).
  - Before modifying `text.py`, save the output of `text_to_ids(s)` for every sentence in `eval/sets/*.jsonl` and `runtime/test/text_parity.tsv` to `tests/fixtures/text_ids_v1.json`. After the change, `text_to_ids(s)` (without `lang`) must match this file ID for ID.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `uv run pytest tests/frontend -q`. Expected: all PASS.
- [ ] **Step 5:** Commit `frontend: per-word language tagging and bilingual text_to_ids`.

### Task 7: Lexicon blob for the chip

**Files:**
- Create: `scripts/frontend/build_lexicon.py`, `runtime/include/vtts_lex.h`, `runtime/src/vtts_lex.c`, `runtime/test/lex_test.c`
- Modify: `runtime/Makefile`, `tests/export/test_runtime_golden.py`, `docs/model-format.md` (add a section on the `VLEX` format)

**Interfaces:**
- Produces:
  - Build command: `build_lexicon.py --out lex_en.bin [--max-words N]`.
  - `VLEX` format, little-endian:
    - header: magic `VLEX`, version u16 = 1, n_words u32, block u16 = 32, n_blocks u32;
    - block offset table u32 × n_blocks;
    - each block consists of entries `[prefix_len u8][suffix_len u8][suffix bytes][n_tok u8][tok u8 × n_tok]`; the first word of a block has `prefix_len = 0`; tokens are stored as v2 IDs.
  - C: `int vtts_lex_init(vtts_lex *lx, const uint8_t *blob, size_t n);`, returns 0 on success.
  - C: `int vtts_lex_lookup(const vtts_lex *lx, const char *word, uint8_t *out, int cap);`, returns the number of tokens, or 0 if the word is not found. Binary search over the first word of each block, then a linear scan within the block.

- [ ] **Step 1: Write the test**
  - `lex_test.c` looks up 5,000 random words (seed 0) and 200 words not in the lexicon, comparing against an expected TSV exported by Python; ASan/UBSan clean.
  - Python test: the full blob is ≤ 1.5 MB.
- [ ] **Step 2:** `uv run pytest tests/export/test_runtime_golden.py -q -k lex`. Expected: FAIL.
- [ ] **Step 3:** Implement the builder and the reader.
- [ ] **Step 4:** Run the test. Expected: PASS, printing the blob size.
- [ ] **Step 5:** Commit `runtime: compact English lexicon blob (VLEX) and reader`.

### Task 8: English and bilingual front-end in C

**Files:**
- Create: `runtime/src/vtts_text_en.c`
- Modify: `runtime/src/vtts_text.c`, `runtime/include/vtts_text.h`, `scripts/frontend/export_text_parity.py`, `runtime/test/text_test.c`, `runtime/test/text_parity.tsv`
- Create: `runtime/test/text_parity_v2.tsv`

**Interfaces:**
- Consumes: `vtts_lex_*`; the rules of Tasks 3–6 (the C version must give identical results).
- Produces:

```c
typedef enum { VTTS_LANG_V1 = 0, VTTS_LANG_VI, VTTS_LANG_EN, VTTS_LANG_AUTO } vtts_lang;
typedef struct { vtts_lang lang; const vtts_lex *lex; } vtts_text_opts;
int vtts_text_to_ids_ex(const char *utf8, vtts_text_ws *ws, const vtts_text_opts *o,
                        vtts_ids_cb cb, void *user);
```

  - The old `vtts_text_to_ids` calls the `_ex` version with `VTTS_LANG_V1`.
  - With `lex == NULL`, English words use only the NRL rules.

- [ ] **Step 1: Write the test**
  - Fixture `text_parity_v2.tsv`: about 1,500 EN, VI and mixed sentences, generated by `export_text_parity.py --v2`, including the sentences from Review Focus 1–4.
  - `text_test` must match 100%.
  - The fuzz mode (`--fuzz`) runs with `VTTS_LANG_AUTO` without ASan errors.
  - The old v1 fixture still matches 100%.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
  - Do not add dynamic memory.
  - If the workspace needs to be larger, increase the relevant `#define`s and record the new size in the comment in `vtts_text.h`.
- [ ] **Step 4:** `uv run pytest tests/export/test_runtime_golden.py -q`. Expected: all PASS.
- [ ] **Step 5:** Commit `runtime: bilingual device front-end with exact Python parity`.

### Task 9: Sentence set for audio synthesis

**Files:**
- Create: `scripts/data/build_bilingual_corpus.py`, `data/bilingual/terms_en.txt` (hand-curated term list)
- Test: `tests/data/test_bilingual_corpus.py`

**Interfaces:**
- Produces: `data/bilingual/sentences.jsonl`, one line per sentence `{"id": str, "text": str, "lang": "vi"|"en"|"mixed", "src": str}`.
  - `vi`: greedy selection from `data/corpus/sentences.txt` so that every syllable present in the corpus reaches ≥ 20 occurrences; plus template sentences with numbers, dates and times, units, questions.
  - `en`: English Wikipedia (filtered to 6–40 words) and LJSpeech transcripts.
  - `mixed`: Vietnamese template sentences containing one or two terms from `terms_en.txt`.
  - Parameters `--hours-vi 30 --hours-en 25 --hours-mixed 5`; hours are estimated from word count, assuming 2.6 words/second.

- [ ] **Step 1: Write the test**
  - On a small corpus built inside the test: unique ids, `lang` within the allowed set of values.
  - Every sentence passes through `text_to_ids(text, lang)` without errors.
  - Rare-syllable coverage increases compared with random selection.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit `data: bilingual sentence corpus builder`.

### Task 10: VoxCPM2 client

**Files:**
- Create: `src/vtts/data/voxcpm_client.py`, `scripts/data/synth_voxcpm.py`
- Test: `tests/data/test_voxcpm_client.py` (a fake HTTP server running inside the test)

**Interfaces:**
- Produces:
  - `load_env(path: Path = Path("~/.config/vtts/voxcpm.env")) -> tuple[str, str]`: returns (URL, key).
  - `build_request(text: str, lang: str, voice: dict) -> dict`: the only function that depends on the API format, written according to the API guide provided by the maintainer.
  - `parse_response(resp) -> tuple[np.ndarray, int]`: returns (float32 audio, sample rate).
  - Command: `synth_voxcpm.py --sentences JSONL --out DIR --workers N`.
    - Writes `DIR/wavs/<id>.wav` (22050 Hz) and `DIR/manifest.jsonl` with `{"id","status","attempts","dur","sr_in","error"}`.
    - On rerun, skips sentences that already have `status == "ok"`.

- [ ] **Step 1: Write the test** (fake server)
  - Error 500 twice then success: `status == "ok"`, `attempts == 3`.
  - Empty audio or audio shorter than 0.3 s: `status == "bad_audio"` and no wav is created (Review Focus 5).
  - Sample rate 48000: the output wav is 22050.
  - A rerun does not resend sentences that are already ok.
  - The key does not appear in the manifest or logs.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
  - Bounded thread pool, retry with backoff up to 5 times.
  - Write the wav to a temporary file and then rename it, so a partially written wav never exists.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit `data: VoxCPM2 synthesis client (resumable, retrying)`.
- [ ] **Step 6 (waiting on the maintainer):** Once the API guide is available, update `build_request` and `parse_response`, add a test with a real example (key redacted), then commit.

### Task 11: Filtering synthesized data

**Files:**
- Create: `src/vtts/eval/speaker_sim.py`, `scripts/data/filter_synth.py`
- Modify: `src/vtts/eval/asr.py` (select the model by language: `vi` → `vinai/PhoWhisper-large`, `en`/`mixed` → `openai/whisper-large-v3`)
- Test: `tests/eval/test_filter_synth.py`

**Interfaces:**
- Produces:
  - `SpeakerEmbedder.embed(paths) -> np.ndarray`, using an Apache-2.0-licensed ECAPA model.
  - `filter_synth.py --synth DIR --sentences JSONL --out DIR2` writes:
    - `DIR2/pre/train.csv` (`id|text|dur|lang`);
    - `DIR2/rejects.jsonl` (`id` with the reason);
    - `DIR2/report.json`.
  - Default thresholds: CER ≤ 0.05; DNSMOS ≥ 3.2; speaker similarity ≥ mean − 2 standard deviations of the data itself; speaking rate within the 2nd–98th percentile per language.

- [ ] **Step 1: Write the test.** Use fake ASR, DNSMOS and embedder. Check the thresholds, rejection reasons and the `train.csv` format.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit `data: filter synthesized speech by ASR, speaker similarity, DNSMOS and rate`.

### Task 12: Data pilot (decision gate, requires the API)

**Files:**
- Create: `eval/sets/pilot_vi_hard.jsonl` (200 sentences with many rare rhymes, numbers, proper names), `eval/sets/pilot_en.jsonl` (100 sentences)
- Create: `docs/reports/voxcpm-pilot.md`

- [ ] **Step 1:** Synthesize data for the two sentence sets with Task 10, then run `filter_synth.py`.
- [ ] **Step 2:** Give the maintainer a listening page with 20 sentences (Artifact) together with the measurements: VI and EN CER, speaker similarity, DNSMOS, synthesis throughput (hours of audio per machine hour).
- [ ] **Step 3: Gate.**
  - Pass when VI CER ≤ 0.03 on the hard set, EN WER ≤ 0.05 and the maintainer accepts it after listening. Then continue with Task 13.
  - On failure, stop, report the cause (tones, rhymes, voice drift) and wait for the maintainer to change the voice or parameters.
- [ ] **Step 4:** Commit the report.

### Task 13: Synthesize and filter the full dataset

- [ ] **Step 1:** `build_bilingual_corpus.py` with `--hours-vi 33 --hours-en 28 --hours-mixed 6` (about 10% surplus to compensate for filtered sentences).
- [ ] **Step 2:** Run `synth_voxcpm.py` in the background, monitoring the manifest. It can be rerun if interrupted.
- [ ] **Step 3:** Run `filter_synth.py`. Expected: after filtering, ≥ 30 hours VI, ≥ 25 hours EN, ≥ 5 hours mixed sentences (per `report.json`).
- [ ] **Step 4:** Turn `docs/reports/voxcpm-pilot.md` into a dataset report (hours, rejection rate per reason). Commit.

### Task 14: Bilingual teacher

**Files:**
- Modify: `src/vtts/teacher/data.py` (`read_rows` accepts a 4th column `lang`; if present, encode with v2 `text_to_ids`, otherwise keep the old behavior)
- Modify: `scripts/teacher/train_teacher.py` (`--phoneme-set 1|2`)
- Test: `tests/teacher/test_data.py`

- [ ] **Step 1:** Write the test: a row `a|Hello world.|1.0|en` produces IDs ≥ 65 and < 107; a 3-column row produces IDs identical to the current ones.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the test, then `uv run pytest -q`. Expected: all PASS.
- [ ] **Step 5:** Commit.
- [ ] **Step 6:** Train on an idle GPU: `--max-steps 300000 --no-cache` if disk space is short. Every 25k steps run `eval_checkpoints.py` on `ood`, `ood_en` and `mixed` (requires Task 16 Steps 1–3).

### Task 15: Bilingual student

**Files:**
- Modify: `scripts/student/build_distill_pack.py` (`--sentences JSONL` with a `lang` field, using v2 IDs)
- Modify: `src/vtts/student/config.py` (preset `M-vocos-p-bi` with `vocab=107`)
- Test: `tests/student/test_distill_pack.py`

- [ ] **Step 1:** Write the test: a pack generated from a JSONL with `lang` contains v2 IDs; preset `M-vocos-p-bi` has `vocab == 107`; the export produces a header with `vocab=107`.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit.
- [ ] **Step 6:** Run the distillation chain as in `bible_student_chain300.sh`: front 10k → dec 30k → joint 20k, then export int8.
- [ ] **Step 7: Capacity gate** (spec 5.4).
  - If the Task 16 criteria are not met because of quality, try the preset `M-vocos-p-bi-L` (about 1.5 times the parameters).
  - Check RTF with `bench` on P4 and S3 before choosing.

### Task 16: Bilingual evaluation

**Files:**
- Create: `eval/sets/ood_en.jsonl` (50 sentences: device notifications, numbers, proper names, questions, long sentences), `eval/sets/mixed.jsonl` (50 sentences)
- Modify: `scripts/eval/eval_dir.py` (select ASR by each sentence's `lang`; WER for EN; for mixed sentences also compute `en_term_acc` = the fraction of English terms that appear correctly in the ASR transcript)
- Test: `tests/eval/test_eval_dir_lang.py`

- [ ] **Step 1:** Write tests for the ASR selection and `en_term_acc`, using a fake ASR.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement; write the two sentence sets.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit.

### Task 17: Firmware and acceptance gate

**Files:**
- Modify: `firmware/esp32/main/main.c`, `firmware/esp32/main/CMakeLists.txt`, `firmware/esp32/build.sh`, `firmware/esp32/README.md`, `README.md`

**Interfaces:**
- Consumes: `vtts_text_to_ids_ex`, `vtts_lex_init`.
- Produces:
  - `build.sh S.vtts M.vtts [LEX.bin]`: if `LEX.bin` is given, embed `lex_en.bin`.
  - Command `lang vi|en|auto`, default `vi`. The command only takes effect when the model has `vocab == 107`; v1 models always use `VTTS_LANG_V1`.
  - `bench` adds 2 EN sentences and 2 mixed sentences.

- [ ] **Step 1:** Implement.
- [ ] **Step 2:** Build all three boards.
  - On P4 and S3, run `selftest`, `bench`, `dump` for VI, EN and mixed sentences.
  - Compare chip audio with the runtime running on the computer. Expected: correlation ≥ 0.9999.
- [ ] **Step 3: Acceptance gate.** Run `render_student_c.py` and `eval_dir.py` on `ood`, the hard-word set, `ood_en`, `mixed`, then compare against the criteria table in section 6 of the spec. Write `docs/reports/bilingual.md`.
- [ ] **Step 4:** Build an A/B listening page (v0.2 vs bilingual) and give it to the maintainer to listen to.
- [ ] **Step 5:** Commit. Push to the public repo after running the privacy-check grep. The release waits for the maintainer to choose a model license.
