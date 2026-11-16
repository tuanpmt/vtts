# Model song ngữ Việt–Anh — Kế hoạch thực hiện

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một file model `.vtts` đọc được tiếng Việt, tiếng Anh và câu trộn hai thứ tiếng bằng một giọng, chạy nhanh hơn thời gian thực trên ESP32-P4 và ESP32-S3.

**Architecture:**
- Bộ token v2 = 65 token tiếng Việt hiện có + 39 âm vị ARPAbet + 3 token trọng âm.
- Front-end mới:
  - gán ngôn ngữ cho từng từ;
  - chuẩn hoá tiếng Anh;
  - G2P tiếng Anh: CMUdict → tách hậu tố → luật NRL → đánh vần.
- Front-end có bản Python và bản C cho kết quả khớp nhau.
- Dữ liệu train sinh bằng VoxCPM2 qua API của người dùng, lọc tự động.
- Sau đó đi đúng quy trình hiện có: teacher VITS → chưng cất → int8 → firmware.

**Tech Stack:** Python 3.11 (uv, PyTorch, transformers), C99 (runtime không `malloc`), ESP-IDF v6.1, CMUdict (BSD), VoxCPM2 (Apache-2.0, qua HTTP API).

**Spec:** `docs/design/specs/2026-11-16-bilingual-vi-en-design.md`

## Global Constraints

- Không đọc hay lấy code GPL: espeak-ng, phonemizer, misaki, piper-phonemize, g2p_en, vPhon, các file GPL của sanoTTS.
- Token v1 giữ nguyên id 0–64.
- Token v2:
  - `EN:<ARPAbet>` id 65–103, theo đúng thứ tự `AA AE AH AO AW AY B CH D DH EH ER EY F G HH IH IY JH K L M N NG OW OY P R S SH T TH UH UW V W Y Z ZH`;
  - `S0 S1 S2` id 104–106;
  - `VOCAB_SIZE_V2 = 107`, `PHONEME_SET_VERSION_V2 = "2"`.
- Hành vi bộ token v1 (`text_to_ids(text)` không truyền tham số mới) phải khớp từng ID với hiện tại: test và fixture cũ phải pass không sửa.
- Mỗi chunk ID ≤ `VTTS_TEXT_MAX_IDS` (320), gồm cả BOS/EOS.
- URL và key VoxCPM2 chỉ đọc từ `~/.config/vtts/voxcpm.env` (`VOXCPM_URL`, `VOXCPM_KEY`). Không ghi vào repo, log hay manifest.
- Audio train lưu ở 22050 Hz mono PCM16.
- Runtime C: không `malloc`, C99; từ điển chỉ đọc qua con trỏ blob.
- Từ điển trên chip ≤ 1.5 MB. Model ≤ 3 MB.
- Tài liệu bằng tiếng Việt có dấu. Code, tên file và commit bằng tiếng Anh.
- Commit kết thúc bằng hai dòng `Co-Authored-By` / `Claude-Session` như các commit trước.
- Tiêu chí đạt ở mục 6 của spec là cổng cuối (Task 17).

## Review Focus

1. **Từ tiếng Anh dính dấu câu, sở hữu cách, gạch nối** ("Apple's", "Wi-Fi", "state-of-the-art,"): đọc đúng từ, không đánh vần cả cụm. Test thuộc Task 6.
2. **Chữ in hoa trộn số** ("USB-C", "4K", "MP3", "iPhone 15"): đánh vần chữ, đọc số theo ngôn ngữ của câu. Test thuộc Task 5 và Task 6.
3. **Tiếng Việt gõ không dấu ở chế độ `vi`** ("xin chao ban"): từ nào ghép được thành âm tiết hợp lệ thì vẫn đọc tiếng Việt, không chuyển sang tiếng Anh. Test thuộc Task 6.
4. **Câu tiếng Anh rất dài không có dấu câu**: luôn được cắt thành các chunk ≤ 320 ID, không lỗi và không mất chữ. Test thuộc Task 6 (Python) và Task 8 (C).
5. **API trả lỗi, audio rỗng, audio cụt hoặc sai sample rate**: thử lại rồi đánh dấu lỗi trong manifest. Không bao giờ ghi một wav hỏng vào dataset. Test thuộc Task 10.

---

## Cấu trúc file

| File | Trách nhiệm |
|---|---|
| `src/vtts/frontend/phoneme_set.py` (sửa) | Thêm `TOKENS_V2`, `VOCAB_SIZE_V2`, `token_to_id_v2` |
| `src/vtts/frontend/en/cmudict.py` | Tải CMUdict (commit cố định), parse, ánh xạ sang token v2 |
| `src/vtts/frontend/en/lts.py` | Luật NRL đoán phát âm từ chữ viết (tự viết từ bài báo 1976) |
| `src/vtts/frontend/en/g2p_en.py` | Từ tiếng Anh → token: từ điển → hậu tố → luật → đánh vần |
| `src/vtts/frontend/en/normalize_en.py` | Số, ngày, giờ, tiền, đơn vị, viết tắt tiếng Anh |
| `src/vtts/frontend/lang.py` | Gán ngôn ngữ từng từ, chế độ `vi`/`en`/`auto` |
| `src/vtts/frontend/text.py` (sửa) | `text_to_ids(text, lang=None)`: `None` = v1 như cũ; `"vi"`/`"en"`/`"auto"` = v2 |
| `scripts/frontend/build_lexicon.py` | Tạo blob từ điển `lex_en.bin` cho chip |
| `runtime/src/vtts_lex.c`, `runtime/include/vtts_lex.h` | Đọc blob từ điển |
| `runtime/src/vtts_text_en.c` | Chuẩn hoá, luật NRL, G2P tiếng Anh, gán ngôn ngữ (C) |
| `runtime/src/vtts_text.c`, `runtime/include/vtts_text.h` (sửa) | `vtts_text_to_ids_ex` có lựa chọn ngôn ngữ |
| `scripts/data/build_bilingual_corpus.py` | Bộ câu VI (phủ âm tiết hiếm), EN, câu trộn |
| `scripts/data/synth_voxcpm.py`, `src/vtts/data/voxcpm_client.py` | Client API: song song, thử lại, chạy tiếp |
| `scripts/data/filter_synth.py`, `src/vtts/eval/speaker_sim.py` | Lọc theo CER, độ giống giọng, DNSMOS, tốc độ nói |
| `src/vtts/teacher/data.py`, `scripts/student/build_distill_pack.py` (sửa) | Đọc cột ngôn ngữ, dùng token v2 |
| `eval/sets/ood_en.jsonl`, `eval/sets/mixed.jsonl` | Bộ câu đánh giá mới |
| `firmware/esp32/main/main.c`, `CMakeLists.txt` (sửa) | Lệnh `lang`, nhúng từ điển, khe model song ngữ |

---

### Task 1: Bộ token v2

**Files:**
- Modify: `src/vtts/frontend/phoneme_set.py`
- Modify: `runtime/tools/gen_text_tables.py`, `runtime/src/vtts_text_tables.h` (generated)
- Test: `tests/frontend/test_phoneme_set.py`

**Interfaces:**
- Produces:
  - `ARPABET: tuple[str, ...]` (39 âm vị, đúng thứ tự trong Global Constraints)
  - `TOKENS_V2: tuple[str, ...]`, `VOCAB_SIZE_V2 = 107`, `PHONEME_SET_VERSION_V2 = "2"`
  - `token_to_id_v2(tok: str) -> int`
  - C: `VTTS_EN_BASE 65`, `VTTS_STRESS_BASE 104`

- [ ] **Step 1: Viết test**

```python
def test_v2_extends_v1():
    assert TOKENS_V2[:VOCAB_SIZE] == TOKENS and VOCAB_SIZE_V2 == 107
    assert token_to_id_v2("EN:AA") == 65 and token_to_id_v2("EN:ZH") == 103
    assert [token_to_id_v2(f"S{i}") for i in range(3)] == [104, 105, 106]
```

- [ ] **Step 2:** `uv run pytest tests/frontend/test_phoneme_set.py -q`. Expected: FAIL (`TOKENS_V2` chưa có).
- [ ] **Step 3:** Thêm các hằng số và hàm vào `phoneme_set.py`. Cho `gen_text_tables.py` sinh thêm `VTTS_EN_BASE` và `VTTS_STRESS_BASE`, rồi chạy lại để tạo header.
- [ ] **Step 4:** `uv run pytest tests/frontend -q`. Expected: PASS, kể cả test v1 cũ.
- [ ] **Step 5:** Commit `frontend: phoneme set v2 (Vietnamese + ARPAbet + stress)`.

### Task 2: CMUdict

**Files:**
- Create: `src/vtts/frontend/en/__init__.py`, `src/vtts/frontend/en/cmudict.py`
- Test: `tests/frontend/test_cmudict.py`

**Interfaces:**
- Produces:
  - `load_cmudict(path: Path | None = None) -> dict[str, list[str]]`: từ viết thường → token v2 của cách đọc đầu tiên (ví dụ `["EN:HH","EN:AH","S0","EN:L","EN:OW","S1"]`). Mặc định tải về `data/cmudict/cmudict.dict` theo URL và commit cố định, kiểm tra SHA256.
  - `arpabet_to_tokens(phones: list[str]) -> list[str]`: tách số trọng âm khỏi nguyên âm thành token `S0`/`S1`/`S2` đứng ngay sau.

- [ ] **Step 1: Viết test**

```python
def test_hello():
    assert arpabet_to_tokens(["HH", "AH0", "L", "OW1"]) == ["EN:HH", "EN:AH", "S0", "EN:L", "EN:OW", "S1"]

def test_lexicon_loads():
    lex = load_cmudict()
    assert len(lex) > 120_000 and lex["bluetooth"][0] == "EN:B"
```

- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
  - Bỏ các biến thể `word(2)` và comment `#`.
  - Ghi chú `LICENSE`/`NOTICE` cho CMUdict (BSD) vào `NOTICE`.
  - `data/cmudict/` cho vào `.gitignore`.
- [ ] **Step 4:** Chạy test. Expected: PASS.
- [ ] **Step 5:** Commit `frontend: CMUdict lexicon (BSD) mapped to v2 tokens`.

### Task 3: Luật NRL đoán phát âm

**Files:**
- Create: `src/vtts/frontend/en/lts.py`
- Test: `tests/frontend/test_lts.py`

**Interfaces:**
- Produces: `lts(word: str) -> list[str]`, trả token v2 kèm trọng âm.
  - Luật NRL không có trọng âm. Gán `S1` cho nguyên âm đầu tiên, `S0` cho các nguyên âm còn lại.

- [ ] **Step 1: Viết test**
  - `lts("cat") == ["EN:K","EN:AE","S1","EN:T"]`
  - `lts("ship")[0] == "EN:SH"`
  - Trên 2.000 từ CMUdict lấy ngẫu nhiên với seed 0 (bỏ qua trọng âm): tỉ lệ lỗi âm vị ≤ 0.35.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
  - Tự viết lại bảng luật từ báo cáo NRL 1976 (public domain): `[trái] khớp [phải] = âm`, quét trái sang phải.
  - Ghi nguồn ở đầu file.
  - Không tham khảo mã GPL.
- [ ] **Step 4:** Chạy test. Expected: PASS.
- [ ] **Step 5:** Commit `frontend: NRL letter-to-sound rules for out-of-lexicon English words`.

### Task 4: G2P tiếng Anh cho một từ

**Files:**
- Create: `src/vtts/frontend/en/g2p_en.py`
- Test: `tests/frontend/test_g2p_en.py`

**Interfaces:**
- Consumes: `load_cmudict`, `lts`.
- Produces: `g2p_word_en(word: str) -> list[str]`, theo thứ tự ưu tiên:
  1. tra từ điển;
  2. từ in hoa ≤ 4 chữ cái, không có trong từ điển → đánh vần tên chữ cái;
  3. tách hậu tố `'s`, `s`, `es`, `ed`, `ing`, `er`, `ly` khi phần gốc có trong từ điển;
  4. tách từ ghép thành hai phần đều có trong từ điển, mỗi phần ≥ 3 chữ;
  5. dùng `lts`.

- [ ] **Step 1: Viết test**
  - `"Apple's"` = cách đọc `apple` + `EN:Z`.
  - `"USB"` đánh vần thành ba tên chữ cái (`Y UW1 | EH1 S | B IY1`).
  - `"smartwatches"` qua tách ghép và hậu tố.
  - `"zzyzx"` không lỗi và trả về ít nhất 1 token.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt theo đúng thứ tự trên.
- [ ] **Step 4:** Chạy test. Expected: PASS.
- [ ] **Step 5:** Commit `frontend: English word G2P (lexicon, morphology, rules, spelling)`.

### Task 5: Chuẩn hoá tiếng Anh

**Files:**
- Create: `src/vtts/frontend/en/normalize_en.py`
- Test: `tests/frontend/test_normalize_en.py`

**Interfaces:**
- Produces: `normalize_en(text: str) -> str`, trả chữ thường, các từ và dấu câu (`, . ? ! ; :`) cách nhau bằng dấu cách, cùng quy ước với `normalize()` tiếng Việt.

- [ ] **Step 1: Viết test** (giá trị chính xác)

| Đầu vào | Kết quả |
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

- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
  - Năm có 4 chữ số đọc theo cặp (2026 → "twenty twenty six"), ngoại lệ 2000–2009 → "two thousand (and) N".
- [ ] **Step 4:** Chạy test. Expected: PASS.
- [ ] **Step 5:** Commit `frontend: English text normalization`.

### Task 6: Gán ngôn ngữ và `text_to_ids` song ngữ (Python)

**Files:**
- Create: `src/vtts/frontend/lang.py`
- Modify: `src/vtts/frontend/text.py`
- Test: `tests/frontend/test_lang.py`, `tests/frontend/test_text_bilingual.py`

**Interfaces:**
- Consumes: `normalize`, `parse_syllable`, `normalize_en`, `g2p_word_en`, `token_to_id_v2`.
- Produces:
  - `sentence_lang(sentence: str, mode: str) -> str`: `mode` là `"vi"`, `"en"` hoặc `"auto"`; với `auto`, câu có tỉ lệ từ mang dấu tiếng Việt ≥ 0.2 thì là `"vi"`.
  - `tag_words(sentence: str, mode: str) -> list[tuple[str, str]]`: danh sách cặp (từ gốc, `"vi"`/`"en"`).
  - `text_to_ids(text: str, lang: str | None = None) -> list[list[int]]`:
    - `lang=None` cho đúng kết quả v1 như hiện tại;
    - các giá trị khác trả ID v2;
    - đóng chunk theo số ID (≤ 320) và ưu tiên cắt ở dấu phẩy.

**Luật gán ngôn ngữ** (theo spec 5.2):
- Từ có dấu tiếng Việt hoặc `đ` luôn là `vi`.
- Chế độ `vi`:
  - từ ghép được thành âm tiết hợp lệ → `vi`;
  - từ có trong `LOANWORDS` → `vi`, đọc theo cách Việt hoá;
  - các từ còn lại → `en`.
- Chế độ `en`: mọi từ không dấu → `en`.
- Số và ký hiệu theo ngôn ngữ của câu chứa nó.
- Các đoạn liên tiếp cùng ngôn ngữ được chuẩn hoá bằng bộ chuẩn hoá của ngôn ngữ đó.

- [ ] **Step 1: Viết test**
  - `tag_words("Đã kết nối Bluetooth với AirPods", "vi")` gán `en` cho đúng `Bluetooth` và `AirPods`.
  - `tag_words("xin chao ban", "vi")` gán toàn `vi` (Review Focus 3).
  - `text_to_ids("Wi-Fi, Apple's state-of-the-art phone.", "en")` không chứa token đánh vần cho `wi`/`fi`/`apple` (Review Focus 1).
  - `"iPhone 15 có giá 20 triệu"` ở chế độ `vi`: số đọc tiếng Việt; `"iPhone 15 costs $799"` ở chế độ `en`: số đọc tiếng Anh (Review Focus 2).
  - Một chuỗi 400 từ tiếng Anh không có dấu câu: mọi chunk ≤ 320 ID và tổng số từ không đổi (Review Focus 4).
  - Trước khi sửa `text.py`, lưu kết quả `text_to_ids(s)` của mọi câu trong `eval/sets/*.jsonl` và `runtime/test/text_parity.tsv` vào `tests/fixtures/text_ids_v1.json`. Sau khi sửa, `text_to_ids(s)` (không truyền `lang`) phải khớp file này từng ID.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** `uv run pytest tests/frontend -q`. Expected: PASS hết.
- [ ] **Step 5:** Commit `frontend: per-word language tagging and bilingual text_to_ids`.

### Task 7: Blob từ điển cho chip

**Files:**
- Create: `scripts/frontend/build_lexicon.py`, `runtime/include/vtts_lex.h`, `runtime/src/vtts_lex.c`, `runtime/test/lex_test.c`
- Modify: `runtime/Makefile`, `tests/export/test_runtime_golden.py`, `docs/model-format.md` (thêm mục định dạng `VLEX`)

**Interfaces:**
- Produces:
  - Lệnh build: `build_lexicon.py --out lex_en.bin [--max-words N]`.
  - Định dạng `VLEX`, little-endian:
    - header: magic `VLEX`, version u16 = 1, n_words u32, block u16 = 32, n_blocks u32;
    - bảng offset khối u32 × n_blocks;
    - mỗi khối gồm các mục `[prefix_len u8][suffix_len u8][suffix bytes][n_tok u8][tok u8 × n_tok]`; từ đầu khối có `prefix_len = 0`; token lưu bằng ID v2.
  - C: `int vtts_lex_init(vtts_lex *lx, const uint8_t *blob, size_t n);`, trả 0 nếu thành công.
  - C: `int vtts_lex_lookup(const vtts_lex *lx, const char *word, uint8_t *out, int cap);`, trả số token hoặc 0 nếu không có từ. Tìm nhị phân trên từ đầu mỗi khối, rồi quét tuần tự trong khối.

- [ ] **Step 1: Viết test**
  - `lex_test.c` tra 5.000 từ ngẫu nhiên (seed 0) và 200 từ không có trong từ điển, so với file TSV kỳ vọng do Python xuất; ASan/UBSan sạch.
  - Test Python: blob đầy đủ ≤ 1.5 MB.
- [ ] **Step 2:** `uv run pytest tests/export/test_runtime_golden.py -q -k lex`. Expected: FAIL.
- [ ] **Step 3:** Cài đặt builder và reader.
- [ ] **Step 4:** Chạy test. Expected: PASS, in kích thước blob.
- [ ] **Step 5:** Commit `runtime: compact English lexicon blob (VLEX) and reader`.

### Task 8: Front-end tiếng Anh và song ngữ bằng C

**Files:**
- Create: `runtime/src/vtts_text_en.c`
- Modify: `runtime/src/vtts_text.c`, `runtime/include/vtts_text.h`, `scripts/frontend/export_text_parity.py`, `runtime/test/text_test.c`, `runtime/test/text_parity.tsv`
- Create: `runtime/test/text_parity_v2.tsv`

**Interfaces:**
- Consumes: `vtts_lex_*`; các quy tắc của Task 3–6 (bản C phải cho kết quả giống hệt).
- Produces:

```c
typedef enum { VTTS_LANG_V1 = 0, VTTS_LANG_VI, VTTS_LANG_EN, VTTS_LANG_AUTO } vtts_lang;
typedef struct { vtts_lang lang; const vtts_lex *lex; } vtts_text_opts;
int vtts_text_to_ids_ex(const char *utf8, vtts_text_ws *ws, const vtts_text_opts *o,
                        vtts_ids_cb cb, void *user);
```

  - `vtts_text_to_ids` cũ gọi bản `_ex` với `VTTS_LANG_V1`.
  - `lex == NULL` thì từ tiếng Anh chỉ dùng luật NRL.

- [ ] **Step 1: Viết test**
  - Fixture `text_parity_v2.tsv`: khoảng 1.500 câu EN, VI và câu trộn, do `export_text_parity.py --v2` sinh, gồm cả các câu ở Review Focus 1–4.
  - `text_test` phải khớp 100%.
  - Bản fuzz (`--fuzz`) chạy với `VTTS_LANG_AUTO`, không lỗi ASan.
  - Fixture v1 cũ vẫn khớp 100%.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
  - Không thêm bộ nhớ động.
  - Nếu workspace cần lớn hơn thì tăng các `#define` liên quan và ghi kích thước mới vào comment của `vtts_text.h`.
- [ ] **Step 4:** `uv run pytest tests/export/test_runtime_golden.py -q`. Expected: PASS hết.
- [ ] **Step 5:** Commit `runtime: bilingual device front-end with exact Python parity`.

### Task 9: Bộ câu để sinh audio

**Files:**
- Create: `scripts/data/build_bilingual_corpus.py`, `data/bilingual/terms_en.txt` (danh sách thuật ngữ tự soạn)
- Test: `tests/data/test_bilingual_corpus.py`

**Interfaces:**
- Produces: `data/bilingual/sentences.jsonl`, mỗi dòng `{"id": str, "text": str, "lang": "vi"|"en"|"mixed", "src": str}`.
  - `vi`: chọn tham lam từ `data/corpus/sentences.txt` sao cho mọi âm tiết có trong corpus đạt ≥ 20 lần; cộng các câu mẫu có số, ngày giờ, đơn vị, câu hỏi.
  - `en`: Wikipedia EN (lọc 6–40 từ) và transcript LJSpeech.
  - `mixed`: các mẫu câu tiếng Việt chứa một hoặc hai thuật ngữ trong `terms_en.txt`.
  - Tham số `--hours-vi 30 --hours-en 25 --hours-mixed 5`; số giờ ước lượng theo số từ, ước tính 2.6 từ/giây.

- [ ] **Step 1: Viết test**
  - Trên corpus nhỏ dựng sẵn trong test: id duy nhất, `lang` đúng tập giá trị.
  - Mọi câu chạy qua `text_to_ids(text, lang)` mà không lỗi.
  - Độ phủ âm tiết hiếm tăng lên so với chọn ngẫu nhiên.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** Chạy test. Expected: PASS.
- [ ] **Step 5:** Commit `data: bilingual sentence corpus builder`.

### Task 10: Client VoxCPM2

**Files:**
- Create: `src/vtts/data/voxcpm_client.py`, `scripts/data/synth_voxcpm.py`
- Test: `tests/data/test_voxcpm_client.py` (server HTTP giả chạy trong test)

**Interfaces:**
- Produces:
  - `load_env(path: Path = Path("~/.config/vtts/voxcpm.env")) -> tuple[str, str]`: trả (URL, key).
  - `build_request(text: str, lang: str, voice: dict) -> dict`: hàm duy nhất phụ thuộc định dạng API, viết theo hướng dẫn người dùng gửi.
  - `parse_response(resp) -> tuple[np.ndarray, int]`: trả (audio float32, sample rate).
  - Lệnh: `synth_voxcpm.py --sentences JSONL --out DIR --workers N`.
    - Ghi `DIR/wavs/<id>.wav` (22050 Hz) và `DIR/manifest.jsonl` gồm `{"id","status","attempts","dur","sr_in","error"}`.
    - Chạy lại thì bỏ qua các câu đã có `status == "ok"`.

- [ ] **Step 1: Viết test** (server giả)
  - Lỗi 500 hai lần rồi thành công: `status == "ok"`, `attempts == 3`.
  - Audio rỗng hoặc ngắn hơn 0.3 s: `status == "bad_audio"` và không tạo wav (Review Focus 5).
  - Sample rate 48000: wav ra là 22050.
  - Chạy lại không gửi lại câu đã ok.
  - Key không xuất hiện trong manifest hay log.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
  - Thread pool có giới hạn, thử lại với backoff tối đa 5 lần.
  - Ghi wav ra file tạm rồi đổi tên, để không bao giờ có wav ghi dở.
- [ ] **Step 4:** Chạy test. Expected: PASS.
- [ ] **Step 5:** Commit `data: VoxCPM2 synthesis client (resumable, retrying)`.
- [ ] **Step 6 (chờ người dùng):** Khi có hướng dẫn API, sửa `build_request` và `parse_response`, thêm test với ví dụ thật (đã ẩn key), rồi commit.

### Task 11: Lọc dữ liệu sinh

**Files:**
- Create: `src/vtts/eval/speaker_sim.py`, `scripts/data/filter_synth.py`
- Modify: `src/vtts/eval/asr.py` (chọn model theo ngôn ngữ: `vi` → `vinai/PhoWhisper-large`, `en`/`mixed` → `openai/whisper-large-v3`)
- Test: `tests/eval/test_filter_synth.py`

**Interfaces:**
- Produces:
  - `SpeakerEmbedder.embed(paths) -> np.ndarray`, dùng model ECAPA giấy phép Apache-2.0.
  - `filter_synth.py --synth DIR --sentences JSONL --out DIR2` ghi:
    - `DIR2/pre/train.csv` (`id|text|dur|lang`);
    - `DIR2/rejects.jsonl` (`id` kèm lý do);
    - `DIR2/report.json`.
  - Ngưỡng mặc định: CER ≤ 0.05; DNSMOS ≥ 3.2; độ giống giọng ≥ trung bình − 2 độ lệch chuẩn của chính dữ liệu; tốc độ nói trong khoảng 2–98% phân vị theo từng ngôn ngữ.

- [ ] **Step 1: Viết test.** Dùng ASR, DNSMOS và embedder giả. Kiểm tra ngưỡng, lý do loại và định dạng `train.csv`.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** Chạy test. Expected: PASS.
- [ ] **Step 5:** Commit `data: filter synthesized speech by ASR, speaker similarity, DNSMOS and rate`.

### Task 12: Chạy thử dữ liệu (cổng quyết định, cần API)

**Files:**
- Create: `eval/sets/pilot_vi_hard.jsonl` (200 câu nhiều vần hiếm, số, tên riêng), `eval/sets/pilot_en.jsonl` (100 câu)
- Create: `docs/reports/voxcpm-pilot.md`

- [ ] **Step 1:** Sinh dữ liệu cho hai bộ câu bằng Task 10, rồi chạy `filter_synth.py`.
- [ ] **Step 2:** Đưa người dùng trang nghe 20 câu (Artifact) kèm số đo: CER VI và EN, độ giống giọng, DNSMOS, tốc độ sinh (giờ audio trên giờ máy).
- [ ] **Step 3: Cổng.**
  - Đạt khi CER VI ≤ 0.03 trên bộ khó, WER EN ≤ 0.05 và người dùng nghe chấp nhận. Khi đó tiếp Task 13.
  - Không đạt thì dừng, báo nguyên nhân (thanh, vần, giọng trôi) và chờ người dùng đổi giọng hoặc tham số.
- [ ] **Step 4:** Commit báo cáo.

### Task 13: Sinh và lọc toàn bộ dữ liệu

- [ ] **Step 1:** `build_bilingual_corpus.py` với `--hours-vi 33 --hours-en 28 --hours-mixed 6` (dư khoảng 10% để bù câu bị lọc).
- [ ] **Step 2:** Chạy `synth_voxcpm.py` ở nền, theo dõi manifest. Chạy lại được khi bị ngắt.
- [ ] **Step 3:** Chạy `filter_synth.py`. Expected: sau lọc có ≥ 30 giờ VI, ≥ 25 giờ EN, ≥ 5 giờ câu trộn (theo `report.json`).
- [ ] **Step 4:** Cập nhật `docs/reports/voxcpm-pilot.md` thành báo cáo dataset (số giờ, tỉ lệ loại theo lý do). Commit.

### Task 14: Teacher song ngữ

**Files:**
- Modify: `src/vtts/teacher/data.py` (`read_rows` nhận cột thứ 4 `lang`; có cột thì mã hoá bằng `text_to_ids` v2, không có thì giữ như cũ)
- Modify: `scripts/teacher/train_teacher.py` (`--phoneme-set 1|2`)
- Test: `tests/teacher/test_data.py`

- [ ] **Step 1:** Viết test: một dòng `a|Hello world.|1.0|en` cho ra ID ≥ 65 và < 107; dòng 3 cột cho ra ID giống hệt hiện tại.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** Chạy test, rồi `uv run pytest -q`. Expected: PASS hết.
- [ ] **Step 5:** Commit.
- [ ] **Step 6:** Train trên GPU rảnh: `--max-steps 300000 --no-cache` nếu thiếu đĩa. Cứ 25k bước chạy `eval_checkpoints.py` trên `ood`, `ood_en` và `mixed` (cần Task 16 Step 1–3).

### Task 15: Student song ngữ

**Files:**
- Modify: `scripts/student/build_distill_pack.py` (`--sentences JSONL` có trường `lang`, dùng ID v2)
- Modify: `src/vtts/student/config.py` (preset `M-vocos-p-bi` với `vocab=107`)
- Test: `tests/student/test_distill_pack.py`

- [ ] **Step 1:** Viết test: pack sinh từ JSONL có `lang` chứa ID v2; preset `M-vocos-p-bi` có `vocab == 107`; export ra header `vocab=107`.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** Chạy test. Expected: PASS.
- [ ] **Step 5:** Commit.
- [ ] **Step 6:** Chạy chuỗi chưng cất như `bible_student_chain300.sh`: front 10k → dec 30k → joint 20k, rồi export int8.
- [ ] **Step 7: Cổng dung lượng** (spec 5.4).
  - Nếu tiêu chí ở Task 16 không đạt vì chất lượng, thử preset `M-vocos-p-bi-L` (khoảng 1.5 lần tham số).
  - Kiểm tra RTF bằng `bench` trên P4 và S3 trước khi chọn.

### Task 16: Đánh giá song ngữ

**Files:**
- Create: `eval/sets/ood_en.jsonl` (50 câu: thông báo thiết bị, số, tên riêng, câu hỏi, câu dài), `eval/sets/mixed.jsonl` (50 câu)
- Modify: `scripts/eval/eval_dir.py` (chọn ASR theo `lang` của từng câu; WER cho EN; với câu trộn tính thêm `en_term_acc` = tỉ lệ thuật ngữ tiếng Anh xuất hiện đúng trong bản ASR)
- Test: `tests/eval/test_eval_dir_lang.py`

- [ ] **Step 1:** Viết test cho cách chọn ASR và `en_term_acc`, dùng ASR giả.
- [ ] **Step 2:** Chạy test. Expected: FAIL.
- [ ] **Step 3:** Cài đặt; soạn hai bộ câu.
- [ ] **Step 4:** Chạy test. Expected: PASS.
- [ ] **Step 5:** Commit.

### Task 17: Firmware và cổng nghiệm thu

**Files:**
- Modify: `firmware/esp32/main/main.c`, `firmware/esp32/main/CMakeLists.txt`, `firmware/esp32/build.sh`, `firmware/esp32/README.md`, `README.md`

**Interfaces:**
- Consumes: `vtts_text_to_ids_ex`, `vtts_lex_init`.
- Produces:
  - `build.sh S.vtts M.vtts [LEX.bin]`: có `LEX.bin` thì nhúng `lex_en.bin`.
  - Lệnh `lang vi|en|auto`, mặc định `vi`. Lệnh chỉ có hiệu lực khi model có `vocab == 107`; model v1 luôn dùng `VTTS_LANG_V1`.
  - `bench` thêm 2 câu EN và 2 câu trộn.

- [ ] **Step 1:** Cài đặt.
- [ ] **Step 2:** Build cả ba board.
  - Trên P4 và S3 chạy `selftest`, `bench`, `dump` cho các câu VI, EN và trộn.
  - So audio chip với runtime chạy trên máy tính. Expected: tương quan ≥ 0.9999.
- [ ] **Step 3: Cổng nghiệm thu.** Chạy `render_student_c.py` và `eval_dir.py` trên `ood`, bộ từ khó, `ood_en`, `mixed`, rồi so với bảng tiêu chí ở mục 6 của spec. Ghi `docs/reports/bilingual.md`.
- [ ] **Step 4:** Làm trang nghe A/B (v0.2 so với song ngữ) và đưa người dùng nghe.
- [ ] **Step 5:** Commit. Đẩy lên repo public sau khi chạy lệnh grep kiểm tra quyền riêng tư. Release chờ người dùng chọn giấy phép model.
