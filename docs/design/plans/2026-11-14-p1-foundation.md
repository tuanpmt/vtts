# Kế hoạch 1: Nền móng (front-end, dữ liệu, đánh giá, baseline)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Có đủ mọi thứ để bắt đầu train teacher: front-end tiếng Việt (chuẩn hoá + G2P bám chữ viết), bộ InfoRe1 đã làm sạch/lọc/chia tập, bộ công cụ đánh giá (CER, UTMOS, DNSMOS, chỉ số rít) và số đo baseline của hai giọng đối chứng.

**Architecture:** Một package Python `vtts` (src layout, quản lý bằng uv). Front-end là hàm thuần, không phụ thuộc model, có golden JSONL để sau này port sang C. Pipeline dữ liệu tách thành các bước thuần (dễ test trên Mac với dữ liệu mẫu) và các script chạy nặng trên máy GPU. Baseline chạy trong một virtualenv riêng như hộp đen.

**Tech Stack:** Python 3.11, uv, pytest, numpy, scipy, soundfile, pyarrow, huggingface_hub; trên máy GPU thêm torch, transformers (PhoWhisper), torchmetrics (DNSMOS), SpeechMOS (UTMOS).

**Spec:** `docs/design/specs/2026-11-14-vietnamese-tts-p4-design.md`

## Bản đồ các kế hoạch

| Kế hoạch | Nội dung | Kết quả chạy được |
|---|---|---|
| **1 (tài liệu này)** | Front-end, dữ liệu, đánh giá, baseline | `text_to_ids()`, dataset đã lọc, báo cáo baseline |
| 2 | Teacher VITS: train (warm-start) trên GPU, cổng teacher | Teacher qua cổng CER + bài nghe |
| 3 | Chưng cất student S/M, exporter, runtime C fp32/int8, golden | Student int8 chạy trên host C qua golden gate |
| 4 | Port ESP32-P4, **vòng đánh giá → tối ưu** (theo yêu cầu người dùng), trang nghe A/B, báo cáo cuối | RTF trên chip thật + báo cáo |

Mỗi kế hoạch sau được viết khi kế hoạch trước xong, dựa trên số đo thật. Yêu cầu "làm xong chạy đánh giá rồi tối ưu" áp dụng ở cuối mỗi kế hoạch (báo cáo số đo) và là trọng tâm của kế hoạch 4.

## Global Constraints

- Tài liệu viết tiếng Việt có dấu đầy đủ; tên file, tên hàm, comment code, commit message bằng tiếng Anh.
- Python `>=3.11`, quản lý bằng `uv`; package `vtts` ở `src/vtts/`.
- Không import, không đọc mã nguồn: espeak-ng, vPhon, `misaki`, `piper-tts`/`piper1-gpl`, và `sanoTTS/tools/`, `sanoTTS/pypkg/`. Baseline chỉ chạy như hộp đen trong `eval/baselines/` (venv riêng).
- Không dùng output ElevenLabs.
- Sample rate đích: 22,050 Hz mono.
- Bộ token front-end là **bám chữ viết**: `tr`≠`ch`, `s`≠`x`, `r`≠`d`≠`gi`, coda `n`≠`ng`, `t`≠`c`, `ch`/`nh` riêng; 6 token thanh theo dấu viết.
- `sanoTTS/`, `data/`, `artifacts/`, `.venv/` nằm trong `.gitignore`.
- Việc nặng (tải 7.8 GB, ASR trên 15k câu, DNSMOS) chạy trên máy GPU: máy chủ GPU riêng (truy cập qua SSH). Máy tính cá nhân chỉ dùng cho code và test nhẹ.

## Review Focus

1. Unicode không chuẩn: chữ dựng sẵn và tổ hợp (NFD), bỏ dấu kiểu cũ (`hoà` và `hòa`), chữ HOA (`ĐƯỜNG`). Kết quả phải giống hệt chữ thường NFC. Test thêm vào Task 3 và Task 4.
2. Từ không phải tiếng Việt: tiếng Anh, từ viết tắt, email/URL, ký tự lạ như emoji. Không được crash và không bao giờ sinh token ngoài bộ token. Test thêm vào Task 6.
3. Số biên: 0, 10, 15, 21, 24, 105, 1005, 1.000.000, `3,5`, `-5`, số ≥ 10^15. Test ở Task 5.
4. Đầu vào rỗng, chỉ có khoảng trắng hoặc chỉ có dấu câu: `text_to_ids` trả về `[]`, không ném lỗi. Test thêm vào Task 6.
5. Đoạn văn rất dài: phải được chia câu, mỗi đoạn tối đa 40 âm tiết. Test thêm vào Task 6.

---

### Task 1: Khởi tạo repo và project Python

**Files:**
- Create: `.gitignore`, `pyproject.toml`, `src/vtts/__init__.py`, `tests/test_smoke.py`, `README.md`

**Interfaces:**
- Produces: package `vtts` import được; `vtts.__version__ == "0.1.0"`; lệnh `uv run pytest` chạy được.

- [ ] **Step 1:** `git init` tại thư mục gốc của repo, nhánh mặc định `main`. Ghi `.gitignore` với các dòng: `sanoTTS/`, `data/`, `artifacts/`, `.venv/`, `__pycache__/`, `*.wav`, `*.onnx`, `*.ckpt`, `.pytest_cache/`.
- [ ] **Step 2:** Viết `tests/test_smoke.py`:

```python
import vtts

def test_version():
    assert vtts.__version__ == "0.1.0"
```

- [ ] **Step 3:** Chạy `uv run pytest -q`. Kết quả mong đợi: FAIL (`ModuleNotFoundError: vtts`).
- [ ] **Step 4:** Tạo `pyproject.toml` (build backend hatchling, `requires-python = ">=3.11"`, dependencies `numpy`, `scipy`, `soundfile`, `pyarrow`, `huggingface_hub`; dev group `pytest`, `ruff`; extra `gpu` = `torch`, `transformers`, `torchmetrics[audio]`, `onnxruntime`; pytest marker `slow`, mặc định `-m "not slow"`). Tạo `src/vtts/__init__.py` với `__version__ = "0.1.0"`. `README.md` dài 5–10 dòng tiếng Việt, trỏ đến spec và các kế hoạch.
- [ ] **Step 5:** Chạy `uv sync && uv run pytest -q`. Kết quả mong đợi: `1 passed`.
- [ ] **Step 6:** Commit tất cả, gồm cả `docs/` (spec + kế hoạch): `chore: scaffold vtts project with design spec and plan 1`.

---

### Task 2: Bộ token (phoneme set)

**Files:**
- Create: `src/vtts/frontend/__init__.py`, `src/vtts/frontend/phoneme_set.py`
- Test: `tests/frontend/test_phoneme_set.py`

**Interfaces:**
- Produces:
  - `PHONEME_SET_VERSION: str = "1"`
  - `TOKENS: tuple[str, ...]`, theo đúng thứ tự dưới đây (ID chính là chỉ số trong tuple)
  - `PAD, BOS, EOS, SPACE = "<pad>", "<bos>", "<eos>", " "`
  - `token_to_id(tok: str) -> int` (ném `KeyError` nếu token lạ), `id_to_token(i: int) -> str`
  - `VOCAB_SIZE: int` (= 65)

Thứ tự token (cố định; muốn đổi thì phải tăng version):

```
<pad> <bos> <eos> " " , . ? ! ; :
O:b O:k O:ch O:d O:đ O:g O:gi O:h O:kh O:l O:m O:n O:ng O:nh O:p O:ph O:r O:s O:t O:th O:tr O:v O:x
G:w
N:a N:ă N:â N:e N:ê N:i N:o N:ô N:ơ N:u N:ư N:iê N:uô N:ươ N:oo
C:c C:ch C:m C:n C:ng C:nh C:p C:t C:j C:w
T1 T2 T3 T4 T5 T6
```

T1..T6 tương ứng ngang, huyền, sắc, hỏi, ngã, nặng.

- [ ] **Step 1:** Viết test:

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

- [ ] **Step 2:** Chạy `uv run pytest tests/frontend/test_phoneme_set.py -q`. Mong đợi: FAIL.
- [ ] **Step 3:** Cài đặt `phoneme_set.py` theo đúng thứ tự token ở trên.
- [ ] **Step 4:** Chạy lại. Mong đợi: PASS.
- [ ] **Step 5:** Commit: `feat(frontend): define versioned spelling-based token set`.

---

### Task 3: Phân tích âm tiết

**Files:**
- Create: `src/vtts/frontend/syllable.py`
- Test: `tests/frontend/test_syllable.py`

**Interfaces:**
- Consumes: không có.
- Produces:
  - `@dataclass(frozen=True) class Syllable: onset: str | None; glide: bool; nucleus: str; coda: str | None; tone: int` (tone 1..6). `onset`, `nucleus`, `coda` là tên **không có tiền tố** (ví dụ `"k"`, `"iê"`, `"ng"`).
  - `parse_syllable(word: str) -> Syllable | None`: nhận một âm tiết; tự xử lý NFC/NFD và chữ hoa; trả về `None` nếu không phải âm tiết tiếng Việt hợp lệ.

Các luật mà test không tự suy ra được, ghi lại ở đây:
- Thanh lấy từ dấu thanh tổ hợp sau khi NFD (huyền U+0300, sắc U+0301, hỏi U+0309, ngã U+0303, nặng U+0323); các dấu chất lượng (U+0306 breve, U+0302 circumflex, U+031B horn) được ghép lại vào chữ cái. Vị trí đặt dấu không ảnh hưởng kết quả.
- Gộp các biến thể chính tả thuần tuý: `c/k/q → k`; `gh → g`; `ngh → ng`; `f → ph`; `w → v`; `z → d`; `j → gi`.
- `qu` → onset `k` + glide. `o`/`u` đứng trước nguyên âm chính trong `oa, oă, oe, uê, uy, uâ, uơ, uya, uyê` → glide.
- `gi`: phần còn lại rỗng hoặc chỉ là coda → nucleus `i` (`gì`, `gìn`); phần còn lại bắt đầu bằng `ê` → nucleus `iê` (`giếng`); trường hợp khác thì bỏ `i` (`gia` → `gi`+`a`).
- Nguyên âm đôi: `iê/yê/ia/ya → iê`; `uô/ua → uô` (với `ua` khi không có `q` đứng trước); `ươ/ưa → ươ`. `y` làm nucleus → `i`. `oo → oo`; `ôô → ô`.
- Off-glide: `i/y` ở cuối vần → coda `j`; `o/u` ở cuối vần → coda `w`. Ngoại lệ chính tả: `ay → ă+j`, `au → ă+w`, `ây → â+j`, `âu → â+w`; `ai → a+j`, `ao → a+w`.

- [ ] **Step 1:** Viết test có tham số (`S(onset, glide, nucleus, coda, tone)`):

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

  Thêm 3 test riêng:
  - `test_tone_placement_and_case_insensitive`: `parse_syllable("hoà") == parse_syllable("hòa") == parse_syllable("HÒA") == parse_syllable(unicodedata.normalize("NFD", "hòa"))`.
  - `test_rejects_non_vietnamese`: `parse_syllable(x) is None` với `x` lần lượt là `"wifi"`, `"email"`, `"abc"`, `"xyz"`, `""`, `"b"`.
  - `test_tone_marks_ignore_order`: chuỗi NFD có dấu thanh đứng trước dấu mũ vẫn cho ra kết quả giống chuỗi NFC.
- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Cài đặt `parse_syllable`: tách onset theo khớp dài nhất, sau đó glide, rồi tách vần thành nucleus + coda theo bảng luật ở trên.
- [ ] **Step 4:** Chạy test. Mong đợi: tất cả PASS.
- [ ] **Step 5:** Commit: `feat(frontend): Vietnamese syllable parser`.

---

### Task 4: G2P (âm tiết → token → ID) và golden

**Files:**
- Create: `src/vtts/frontend/g2p.py`, `scripts/frontend/export_frontend_golden.py`
- Test: `tests/frontend/test_g2p.py`

**Interfaces:**
- Consumes: `parse_syllable`, `Syllable` (Task 3); `TOKENS`, `token_to_id`, `BOS`, `EOS`, `SPACE` (Task 2).
- Produces:
  - `syllable_tokens(s: Syllable) -> list[str]`, theo thứ tự: `O:<onset>`? → `G:w`? → `N:<nucleus>` → `C:<coda>`? → `T<tone>`
  - `g2p(normalized: str) -> list[str]`. Đầu vào là văn bản **đã chuẩn hoá** (Task 6): các âm tiết viết thường cách nhau bởi dấu cách, dấu câu `, . ? ! ; :` là token tách riêng bằng dấu cách. Âm tiết cách nhau bằng `" "`. Dấu câu **thay thế** dấu cách bên cạnh nó. Ném `ValueError` nếu gặp âm tiết không hợp lệ (normalizer phải loại bỏ trước).
  - `encode(tokens: list[str]) -> list[int]`: tự thêm `<bos>` ở đầu và `<eos>` ở cuối.

- [ ] **Step 1:** Viết test:

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

- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Cài đặt `g2p.py`.
- [ ] **Step 4:** Chạy test. Mong đợi: PASS.
- [ ] **Step 5:** Viết `scripts/frontend/export_frontend_golden.py --sentences <file.txt> --out tests/fixtures/frontend_golden.jsonl`. Mỗi dòng: `{"text", "normalized", "tokens", "ids", "phoneme_set_version"}`. Dùng `text_to_ids` từ Task 6, nên script này chỉ chạy được sau Task 6; ở Task 4 chỉ viết khung. Golden được sinh ở cuối Task 6.
- [ ] **Step 6:** Commit: `feat(frontend): token-level G2P and id encoding`.

---

### Task 5: Đọc số tiếng Việt (giọng Bắc chuẩn)

**Files:**
- Create: `src/vtts/frontend/numbers.py`
- Test: `tests/frontend/test_numbers.py`

**Interfaces:**
- Produces:
  - `read_int(n: int) -> str`: chỉ cho số nguyên không âm `< 10**15`; số lớn hơn thì đọc từng chữ số.
  - `read_number_token(tok: str) -> str`: nhận các dạng `"-5"`, `"1.000.000"`, `"3,5"`, `"1.5"`, `"007"`.

Luật (giọng Bắc):
- Đơn vị sau `mươi` (từ 20 trở lên): 1 → `mốt`, 4 → `tư`, 5 → `lăm`.
- Đơn vị sau `mười`: 5 → `lăm`.
- Hàng chục bằng 0 nhưng hàng trăm khác 0 → `linh`.
- Dùng `nghìn`, `triệu`, `tỷ`, `nghìn tỷ`. Nhóm 3 chữ số ở giữa mà bằng 0 thì bỏ qua cả nhóm. Nhóm không đứng đầu, giá trị khác 0 và < 100 → thêm tiền tố `không trăm` (cộng `linh` nếu < 10).
- Dấu chấm theo sau là đúng nhóm 3 chữ số → phân cách hàng nghìn. Dấu phẩy → thập phân `phẩy`. Dấu chấm không theo dạng nhóm 3 → `chấm`. Dấu trừ ở đầu → `âm`. Chuỗi có số 0 ở đầu (`007`) → đọc từng chữ số.

- [ ] **Step 1:** Viết test có tham số:

```python
CASES = [(0,"không"),(10,"mười"),(15,"mười lăm"),(21,"hai mươi mốt"),
 (24,"hai mươi tư"),(25,"hai mươi lăm"),(105,"một trăm linh năm"),
 (1005,"một nghìn không trăm linh năm"),(1050,"một nghìn không trăm năm mươi"),
 (1500,"một nghìn năm trăm"),(1000500,"một triệu năm trăm"),
 (2026,"hai nghìn không trăm hai mươi sáu"),(1000000000,"một tỷ")]
TOKENS = [("1.000.000","một triệu"),("3,5","ba phẩy năm"),("-5","âm năm"),
 ("1.5","một chấm năm"),("007","không không bảy")]
```

  Thêm test: `read_int(10**15)` trả về chuỗi 16 từ (`"một"` theo sau là 15 lần `"không"`).
- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** Chạy test. Mong đợi: PASS.
- [ ] **Step 5:** Commit: `feat(frontend): Northern Vietnamese number reading`.

---

### Task 6: Chuẩn hoá văn bản, chia câu, `text_to_ids`

**Files:**
- Create: `src/vtts/frontend/normalize.py`, `src/vtts/frontend/lexicon.py` (bảng viết tắt, từ mượn, tên chữ cái), `src/vtts/frontend/text.py`
- Test: `tests/frontend/test_normalize.py`, `tests/frontend/test_text.py`

**Interfaces:**
- Consumes: `read_int`, `read_number_token` (Task 5); `parse_syllable` (Task 3); `g2p`, `encode` (Task 4).
- Produces:
  - `normalize(text: str) -> str`: đầu ra chỉ gồm âm tiết tiếng Việt hợp lệ viết thường, cộng các dấu câu `, . ? ! ; :`, tất cả cách nhau một dấu cách.
  - `split_sentences(text: str, max_syllables: int = 40) -> list[str]`: tách theo `. ! ? ;`; đoạn nào dài hơn 40 âm tiết thì tách tiếp theo dấu phẩy, sau đó cắt cứng ở 40.
  - `text_to_ids(text: str) -> list[list[int]]`: mỗi đoạn một list ID; văn bản rỗng hoặc chỉ có dấu câu → `[]`.
  - `ABBREVIATIONS: dict[str, str]`, `LOANWORDS: dict[str, str]`, `LETTER_NAMES: dict[str, str]` trong `lexicon.py`.

Luật xử lý (theo thứ tự): NFC → khoảng trắng → mẫu đặc biệt (ngày `d/m/yyyy`, `d/m` với d ≤ 31 và m ≤ 12; giờ `8:30`, `8h30`, `8h`; `%`; tiền `đ`, `VNĐ`, `$`, `USD`; đơn vị `km`, `kg`, `m`, `cm`, `°C`) → viết tắt → số → chữ thường → mỗi từ: nếu `parse_syllable` hợp lệ thì giữ; nếu có trong `LOANWORDS` thì thay; ngược lại đánh vần bằng `LETTER_NAMES`. Ký tự không phải chữ, số hay dấu câu được hỗ trợ (emoji, `@`, `/`, ...) → bỏ. `… → .`; `– — → ,`; ngoặc và nháy → bỏ.

Tên chữ cái (giọng Bắc): a→`a`, b→`bê`, c→`xê`, d→`dê`, đ→`đê`, e→`e`, f→`ép`, g→`giê`, h→`hát`, i→`i`, j→`gi`, k→`ca`, l→`e lờ`, m→`em mờ`, n→`en nờ`, o→`o`, p→`pê`, q→`quy`, r→`e rờ`, s→`ét xì`, t→`tê`, u→`u`, v→`vê`, w→`vê kép`, x→`ích xì`, y→`i dài`, z→`dét`.

`LOANWORDS` tối thiểu: `wifi→oai phai`, `email→i meo`, `ok→ô kê`, `internet→in tơ nét`, `video→vi đê ô`, `online→online`→`on lai`.
`ABBREVIATIONS` tối thiểu: `TP.HCM→thành phố hồ chí minh`, `TP.→thành phố`, `Q.→quận`, `P.→phường`, `HN→hà nội`, `VN→việt nam`, `v.v.→vân vân`.

- [ ] **Step 1:** Viết test cho `normalize`:

```python
CASES = [
 ("14/11/2026", "ngày mười bốn tháng mười một năm hai nghìn không trăm hai mươi sáu"),
 ("8:30", "tám giờ ba mươi phút"), ("8h", "tám giờ"),
 ("50%", "năm mươi phần trăm"), ("100.000đ", "một trăm nghìn đồng"),
 ("5 USD", "năm đô la"), ("5km", "năm ki lô mét"), ("25°C", "hai mươi lăm độ xê"),
 ("TP.HCM", "thành phố hồ chí minh"), ("ABC", "a bê xê"), ("wifi", "oai phai"),
 ("Xin chào, Việt Nam!", "xin chào , việt nam !"),
 ("ĐƯỜNG", "đường"), ("Bật đèn 😀 nhé", "bật đèn nhé"),
 ("Gửi tới a@b.com", "gửi tới a bê xê o em mờ"),  # @ . bị bỏ, phần chữ được đánh vần
]
```

  Test cho `text.py`:
  - `test_empty_inputs`: `text_to_ids(x) == []` với `x` là `""`, `"   "`, `"..."`, `"😀"`.
  - `test_long_paragraph_chunked`: một đoạn 150 âm tiết có vài dấu phẩy → mọi đoạn có ≤ 40 âm tiết, và nối các đoạn lại thì giữ đủ toàn bộ âm tiết theo đúng thứ tự.
  - `test_never_emits_unknown_ids`: chạy qua một danh sách 30 chuỗi khó (tiếng Anh, URL, ký hiệu, số lớn, chữ lẫn số như `A4`, `iPhone15`) → mọi ID nằm trong `range(VOCAB_SIZE)` và không có ngoại lệ nào.
- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Cài đặt `lexicon.py`, `normalize.py`, `text.py`.
- [ ] **Step 4:** Chạy `uv run pytest tests/frontend -q`. Mong đợi: tất cả PASS.
- [ ] **Step 5:** Viết `tests/fixtures/frontend_sentences.txt` (khoảng 200 câu: 100 câu lấy từ test và ví dụ ở trên, 100 câu tự viết trải đủ các nhóm của bộ ngoài miền ở Task 10). Chạy `uv run python scripts/frontend/export_frontend_golden.py --sentences tests/fixtures/frontend_sentences.txt --out tests/fixtures/frontend_golden.jsonl`. Thêm test `test_golden_stable` so sánh lại toàn bộ golden.
- [ ] **Step 6:** Commit: `feat(frontend): text normalization, sentence chunking, golden fixture`.

---

### Task 7: Xử lý audio và chuẩn bị InfoRe1

**Files:**
- Create: `src/vtts/data/__init__.py`, `src/vtts/data/audio.py`, `src/vtts/data/infore.py`, `scripts/data/prepare_infore.py`
- Test: `tests/data/test_audio.py`, `tests/data/test_infore.py`

**Interfaces:**
- Produces:
  - `resample(x: np.ndarray, sr_in: int, sr_out: int = 22050) -> np.ndarray`: dùng `scipy.signal.resample_poly` với tỉ lệ rút gọn theo gcd.
  - `trim_silence(x: np.ndarray, sr: int, top_db: float = 40.0, pad_ms: float = 50.0) -> np.ndarray`: tính RMS theo frame (cửa sổ 25 ms, bước 10 ms), giữ đoạn từ frame đầu tiên đến frame cuối cùng có RMS ≥ max − top_db, cộng thêm phần đệm.
  - `normalize_loudness(x: np.ndarray, target_rms_db: float = -23.0, peak_db: float = -1.0) -> np.ndarray`
  - `prepare_infore(parquet_dir: Path, out_dir: Path) -> PrepareReport`: ghi `out_dir/wavs/infore_{i:05d}.wav` (22,050 Hz, PCM16) và `out_dir/metadata.csv` (phân cách `|`: `id|text|duration_s`). Dòng có audio hỏng hoặc transcript rỗng → bỏ qua và ghi vào `report.skipped` (list `(index, reason)`).
  - `@dataclass PrepareReport: n_in: int; n_out: int; hours: float; skipped: list[tuple[int, str]]`

- [ ] **Step 1:** Viết test:
  - `test_resample_44100_to_22050`: tín hiệu sin 1 kHz dài 1 giây → độ dài 22050 ± 1, tần số đỉnh 1000 ± 5 Hz.
  - `test_trim_silence`: 0.5 s im lặng + 1 s sin + 0.5 s im lặng → độ dài khoảng 1.1 s (± 0.05 s).
  - `test_loudness`: RMS đầu ra là −23 ± 0.5 dB, peak ≤ −1 dB.
  - `test_prepare_infore_tiny`: tạo trong `tmp_path` một file parquet 3 dòng có cùng schema InfoRe (cột `audio` là struct `{bytes, path}` chứa WAV 44.1 kHz, cột `transcription` là string). Một dòng có transcript rỗng. Kết quả mong đợi: `n_out == 2`, `skipped == [(index_of_empty, "empty_transcript")]`, metadata có 2 dòng, wav đọc ra có sr = 22050.
- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Cài đặt. Script `scripts/data/prepare_infore.py --download-to data/infore1/raw --out data/infore1/prepared` dùng `huggingface_hub.snapshot_download(repo_id="doof-ferb/infore1_25hours", repo_type="dataset")`.
- [ ] **Step 4:** Chạy test. Mong đợi: PASS.
- [ ] **Step 5:** Commit: `feat(data): audio utils and InfoRe1 preparation`.

---

### Task 8: Các chỉ số đánh giá

**Files:**
- Create: `src/vtts/eval/__init__.py`, `src/vtts/eval/cer.py`, `src/vtts/eval/whistle.py`, `src/vtts/eval/asr.py`, `src/vtts/eval/mos.py`
- Test: `tests/eval/test_cer.py`, `tests/eval/test_whistle.py`, `tests/eval/test_models_slow.py`

**Interfaces:**
- Consumes: `normalize` (Task 6).
- Produces:
  - `prep_for_cer(text: str) -> str`: đưa qua `normalize`, bỏ dấu câu, gộp khoảng trắng. **Giữ nguyên dấu thanh**.
  - `cer(ref: str, hyp: str) -> float` và `wer(ref: str, hyp: str) -> float`: khoảng cách Levenshtein tự cài, chia cho độ dài của ref; cả hai chuỗi đều qua `prep_for_cer`.
  - `corpus_cer(pairs: list[tuple[str, str]]) -> float`: tổng số lỗi chia tổng độ dài.
  - `whistle_score(x: np.ndarray, sr: int) -> float`. Thuật toán: STFT (n_fft 2048, hop 256, cửa sổ Hann), đổi sang dB; chỉ xét các bin 2–8 kHz. Một ô (bin, frame) là "tonal" nếu cao hơn median của ±20 bin lân cận ít nhất 15 dB. Đếm các ô thuộc chuỗi tonal cùng bin kéo dài ≥ 8 frame liên tiếp. Điểm = số ô đó chia cho số giây.
  - `class AsrTranscriber: __init__(model_id: str = "vinai/PhoWhisper-large", device: str | None = None); transcribe(paths: list[Path], batch_size: int = 8) -> list[str]`
  - `dnsmos(x: np.ndarray, sr: int) -> dict[str, float]` (khoá `sig`, `bak`, `ovrl`; dùng torchmetrics DNSMOS)
  - `utmos(x: np.ndarray, sr: int) -> float` (SpeechMOS `utmos22_strong` qua `torch.hub`)

- [ ] **Step 1:** Viết test:
  - `test_cer_tone_sensitive`: `cer("ma", "mà") == 0.5` (một ký tự sai trên 2).
  - `test_cer_ignores_case_punct_and_digits`: `cer("Hai mươi mốt.", "hai mươi mốt") == 0.0` và `cer("21", "hai mươi mốt") == 0.0`.
  - `test_corpus_cer`: với `[("ab", "ab"), ("abcd", "abcf")]`, kết quả là `1/6`.
  - `test_whistle_detects_tone`: nhiễu trắng 2 s → điểm `< 5`; cùng nhiễu đó cộng một sin 4 kHz ở mức −20 dB → điểm `> 50`.
  - `test_models_slow` (đánh dấu `@pytest.mark.slow`): `AsrTranscriber` chép lại một file wav mẫu ra chuỗi khác rỗng; `dnsmos` trả về đủ 3 khoá với giá trị trong [1, 5]; `utmos` trả về giá trị trong [1, 5].
- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Cài đặt. Các model nặng được import lười (import bên trong hàm), để test nhanh trên Mac không cần torch.
- [ ] **Step 4:** Chạy `uv run pytest tests/eval -q`. Mong đợi: PASS (bỏ qua test `slow`).
- [ ] **Step 5:** Commit: `feat(eval): CER/WER, whistle score, ASR and MOS wrappers`.

---

### Task 9: Lọc dữ liệu, chia tập, báo cáo dữ liệu

**Files:**
- Create: `src/vtts/data/filter.py`, `src/vtts/data/splits.py`, `src/vtts/data/report.py`, `scripts/data/score_dataset.py` (chạy trên GPU), `scripts/data/filter_and_split.py`
- Test: `tests/data/test_filter.py`, `tests/data/test_splits.py`

**Interfaces:**
- Consumes: `cer` (Task 8), `g2p`/`normalize` (Task 4, Task 6), định dạng `metadata.csv` (Task 7).
- Produces:
  - `@dataclass Row: id: str; text: str; duration_s: float; asr: str | None = None; dnsmos_ovrl: float | None = None`
  - `apply_filters(rows: list[Row], cer_max: float = 0.10, dnsmos_min: float = 3.0, dur_min: float = 1.0, dur_max: float = 15.0) -> tuple[list[Row], dict[str, int]]`: dict thứ hai đếm số dòng bị loại theo từng lý do (`cer`, `dnsmos`, `too_short`, `too_long`, `invalid_text`). `invalid_text` là dòng mà `normalize` + `g2p` ném lỗi.
  - `make_splits(rows: list[Row], n_heldout: int = 50, val_frac: float = 0.02, seed: int = 1234) -> dict[str, list[Row]]` (khoá `train`, `val`, `heldout`); tất định; heldout chỉ chọn câu dài 3–10 s.
  - `dataset_report(splits) -> dict`: số giờ và số câu của từng tập, histogram độ dài (bin 1 s), phân bố 6 token thanh trên tập train.
  - `scripts/data/score_dataset.py --prepared data/infore1/prepared --out data/infore1/scores.jsonl`: chạy ASR + DNSMOS, ghi mỗi dòng `{id, asr, dnsmos_ovrl}`.
  - `scripts/data/filter_and_split.py --prepared ... --scores ... --out data/infore1/final`: ghi `train.csv`, `val.csv`, `heldout.csv` (cùng định dạng metadata, cột text là văn bản gốc) và `report.json`. **Nếu train < 18 giờ thì in cảnh báo**, kèm đề xuất nới ngưỡng.

- [ ] **Step 1:** Viết test:
  - `test_filters_each_reason`: 6 dòng giả, mỗi dòng vi phạm đúng một lý do, cộng 1 dòng sạch → giữ lại 1, và mỗi lý do đếm đúng 1.
  - `test_splits_deterministic_and_disjoint`: 500 dòng giả → hai lần gọi cho cùng kết quả; ba tập không giao nhau; `len(heldout) == 50`; mọi câu heldout dài 3–10 s.
  - `test_report_tone_distribution_sums`: tổng phân bố thanh bằng tổng số âm tiết.
- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** Chạy test. Mong đợi: PASS.
- [ ] **Step 5:** Commit: `feat(data): quality filters, deterministic splits, dataset report`.

---

### Task 10: Bộ câu đánh giá ngoài miền và CLI đánh giá

**Files:**
- Create: `eval/sets/ood.jsonl`, `src/vtts/eval/run_eval.py`, `scripts/eval/eval_dir.py`
- Test: `tests/eval/test_run_eval.py`

**Interfaces:**
- Consumes: `corpus_cer`, `cer`, `whistle_score`, `AsrTranscriber`, `utmos`, `dnsmos` (Task 8).
- Produces:
  - Định dạng tập câu (JSONL): `{"id": str, "text": str, "group": str}`.
  - `@dataclass ClipScore: id; cer; wer; whistle; utmos: float | None; dnsmos_ovrl: float | None`
  - `@dataclass EvalReport: system: str; set_name: str; corpus_cer: float; corpus_wer: float; mean_whistle: float; mean_utmos: float | None; mean_dnsmos: float | None; clips: list[ClipScore]`
  - `evaluate(system: str, set_name: str, audio_dir: Path, sentences: list[dict], asr: Callable[[list[Path]], list[str]], mos: bool = True) -> EvalReport`. File audio của câu có id `X` là `audio_dir/X.wav`; nếu thiếu file thì ném `FileNotFoundError` kèm danh sách id bị thiếu.
  - `scripts/eval/eval_dir.py --system NAME --set eval/sets/ood.jsonl --audio DIR --out reports/NAME-SET.json [--no-mos]`

- [ ] **Step 1:** Viết `eval/sets/ood.jsonl` gồm 50 câu tự viết, chia đều 5 nhóm (`group`), mỗi nhóm 10 câu: `device` (thông báo thiết bị), `numbers` (số, ngày, giờ, tiền), `names` (tên người, địa danh), `prosody` (câu hỏi, câu cảm thán), `long` (trên 30 âm tiết).
- [ ] **Step 2:** Viết test `test_evaluate_with_fake_asr`: 3 câu, audio là các file sin, ASR giả trả đúng văn bản cho 2 câu và sai một chữ cho câu thứ ba, `mos=False` → `corpus_cer` đúng bằng giá trị tính tay; `test_missing_audio_lists_ids`: thiếu 1 file thì ném lỗi có chứa id đó.
- [ ] **Step 3:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 4:** Cài đặt.
- [ ] **Step 5:** Chạy test. Mong đợi: PASS.
- [ ] **Step 6:** Commit: `feat(eval): OOD sentence set and evaluation runner`.

---

### Task 11: Baseline (hộp đen) và báo cáo baseline

**Files:**
- Create: `eval/baselines/pyproject.toml` (venv riêng, **không** phải workspace member của `vtts`), `eval/baselines/render.py`, `eval/baselines/README.md`, `docs/reports/baseline.md`

**Interfaces:**
- Consumes: các file JSONL tập câu (Task 10; tập heldout lấy từ Task 12, nên bước chạy heldout làm sau Task 12); `normalize` (Task 6). Script baseline gọi `vtts` qua subprocess (`uv run --project ../.. python -c ...`) để lấy văn bản đã chuẩn hoá, **không import chéo** giữa hai venv.
- Produces: `render.py --system {sanotts-vi,piper-25h} --set FILE --out DIR` ghi `DIR/<id>.wav`.
  - `sanotts-vi`: `pip install sanotts`, giọng `vi`.
  - `piper-25h`: `pip install piper-tts`, model `vi_VN-25hours_single-low` (tải từ `rhasspy/piper-voices`).
  - Đầu vào cho cả hai hệ thống là **văn bản đã qua `normalize` của `vtts`**, để cách đọc số giống hệt nhau giữa các hệ thống.

- [ ] **Step 1:** Tạo venv riêng: `cd eval/baselines && uv sync`. Chạy thử `render.py` với 2 câu cho mỗi hệ thống. Mong đợi: có 2 file wav cho mỗi hệ thống, độ dài > 0.5 s.
- [ ] **Step 2:** Render toàn bộ tập `ood.jsonl` cho cả hai hệ thống vào `artifacts/baselines/<system>/ood/`.
- [ ] **Step 3:** Chạy `scripts/eval/eval_dir.py` cho cả hai (trên Mac dùng MPS với 50 câu, hoặc trên máy GPU). Mong đợi: hai file `reports/*.json`.
- [ ] **Step 4:** Viết `docs/reports/baseline.md` (tiếng Việt): bảng CER, WER, UTMOS, DNSMOS và chỉ số rít của hai hệ thống, tách theo từng nhóm câu; ghi rõ model ASR dùng; nêu ngưỡng cổng teacher suy ra từ số đo (≤ 50% CER của `sanotts-vi` và ≤ CER của `piper-25h`).
- [ ] **Step 5:** Commit: `feat(eval): black-box baselines and baseline report (ood set)`.

---

### Task 12: Chạy pipeline dữ liệu trên máy GPU

**Files:**
- Create: `docs/reports/dataset-infore1.md`, `scripts/remote/README.md` (các lệnh đã dùng trên máy GPU)

**Interfaces:**
- Consumes: Task 7, Task 9, Task 11.
- Produces trên máy GPU: `data/infore1/final/{train,val,heldout}.csv`, `wavs/`, `report.json`. Đồng bộ `heldout.csv` và `report.json` về Mac (`eval/sets/heldout.jsonl` được tạo từ `heldout.csv`).

- [ ] **Step 1:** Chuẩn bị máy GPU (SSH) và đồng bộ code lên đó.
- [ ] **Step 2:** Trên container: clone repo (hoặc rsync), chạy `uv sync --extra gpu`, sau đó `nvidia-smi` và `uv run python -c "import torch; print(torch.cuda.is_available())"`. Mong đợi: thấy RTX 3060, in ra `True`.
- [ ] **Step 3:** `uv run pytest -q -m slow`. Mong đợi: PASS.
- [ ] **Step 4:** `uv run python scripts/data/prepare_infore.py ...`. Mong đợi: `n_out` gần 14,935, khoảng 25 giờ.
- [ ] **Step 5:** `uv run python scripts/data/score_dataset.py ...` (chạy nền, kèm log).
- [ ] **Step 6:** `uv run python scripts/data/filter_and_split.py ...`. Mong đợi: train ≥ 18 giờ. Nếu dưới 18 giờ: nới `cer_max` lên 0.15 rồi chạy lại, và ghi lý do vào báo cáo.
- [ ] **Step 7:** Tạo `eval/sets/heldout.jsonl` từ `heldout.csv`. Render baseline cho tập heldout (Task 11, bước 2–3), cập nhật `docs/reports/baseline.md` với cả hai tập câu.
- [ ] **Step 8:** Viết `docs/reports/dataset-infore1.md`: số câu và số giờ trước/sau lọc, số dòng bị loại theo từng lý do, histogram độ dài, phân bố thanh, và 10 câu bị loại vì CER kèm transcript và output ASR (để người dùng tự kiểm tra ngưỡng có hợp lý không).
- [ ] **Step 9:** Commit: `docs: InfoRe1 dataset report and heldout baseline numbers`.

**Cổng kết thúc Kế hoạch 1:** toàn bộ test pass (kể cả test `slow` trên máy GPU); train ≥ 18 giờ; `baseline.md` có số đo của hai hệ thống trên cả hai tập câu. Sau đó viết Kế hoạch 2 (teacher).
