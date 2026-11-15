# vtts

Giọng đọc tiếng Việt nhỏ gọn, chạy hoàn toàn trên vi điều khiển ESP32-P4: văn bản vào, âm thanh ra loa, không cần mạng.

> **English summary.** vtts is a tiny Vietnamese text-to-speech stack: a rule-based, dialect-ready
> Vietnamese front-end (Python + C99, exact parity), a VITS teacher, a 0.8–1.7M-parameter distilled
> student, and a malloc-free C99 int8 runtime with streaming synthesis. On an ESP32-P4 (360 MHz,
> PIE SIMD, 2 cores) the 1.7M model (v0.2, with an explicit pitch/energy predictor) runs at RTF ≈ 0.79–0.90 and the
> 0.8M model at RTF ≈ 0.42, with speech starting after 0.6–2.4 s. Code is Apache-2.0. Prototype int8 models (`.vtts`) are attached to GitHub Releases for non-commercial research use only (CC BY-NC 4.0).

## Kết quả

Đo trên 50 câu ngoài miền (thông báo thiết bị, số, tên riêng, câu hỏi, câu dài). CER là tỉ lệ lỗi ký tự khi ASR (PhoWhisper-large) nghe lại, có tính dấu thanh. UTMOS dự đoán độ tự nhiên. Audio của student được tạo bằng chính runtime C int8 chạy trên chip.

| Hệ thống | Tham số | CER ↓ | UTMOS ↑ | Tiếng rít ↓ |
|---|---:|---:|---:|---:|
| **vtts M-vocos v0.2** (int8, ngữ điệu v2) | 1.73M | **0.012** | 2.19 | 7.8 |
| vtts M-vocos v0.1 (int8) | 1.73M | 0.012 | 2.08 | 3.3 |
| vtts S-vocos (int8) | 0.77M | 0.023 | 1.86 | 61.5 |
| Teacher VITS | 23.7M | 0.015 | 2.50 | 14.8 |
| sanoTTS `vi` (baseline) | 1.57M | 0.064 | 1.49 | 1.5 |
| Piper `vi_VN-25hours_single` (baseline) | — | 0.089 | 2.06 | 1.1 |

Trên Waveshare ESP32-P4 Panel (chip rev 1.3, 360 MHz, PSRAM 32 MB):

| Model | RTF (2 lõi, PIE SIMD) | Bắt đầu phát | Flash | RAM làm việc |
|---|---:|---:|---:|---:|
| S-vocos | 0.42 | 0.6–0.9 s | 1.1 MB | ~0.4 MB (streaming) |
| M-vocos v0.2 | 0.79–0.90 | khoảng 2.4 s | 2.6 MB | ~0.6 MB (streaming) |

RTF < 1 nghĩa là tổng hợp nhanh hơn thời gian thực. Đoạn văn dài 56 giây phát liền mạch, không ngắt quãng.

**Ngữ điệu v0.2.** Model M có thêm bộ dự đoán cao độ và năng lượng tường minh, và sửa lỗi đọc quá nhanh. Đo trên 50 câu giữ lại: thời lượng trung bình mỗi câu 5.80 s (v0.1: 4.95 s, người đọc thật: 6.08 s), độ dao động cao độ 2.37 semitone (v0.1: 2.32, người thật: 2.60).

### Nghe thử: audio sinh trực tiếp trên ESP32-P4

Bấm ▶ để phát (trình duyệt mở trình phát âm thanh). Các file được tạo trên board bằng lệnh `dump` của firmware: chip tổng hợp câu, gửi PCM 16-bit qua cổng serial về máy tính, rồi chỉ nén sang mp3, không xử lý gì thêm. Audio từ chip khớp với runtime C chạy trên máy tính (hệ số tương quan 0.999999, sai khác mẫu lớn nhất 0.0016).

| Câu | M-vocos v0.2 (1.73M) | S-vocos (0.77M) | Thời lượng M / S | RTF M / S |
|---|---|---|---:|---:|
| Xin chào, tôi là giọng đọc tiếng Việt chạy hoàn toàn trên chip ESP32-P4. | [▶ Nghe M](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-m-intro.mp3) | [▶ Nghe S](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-s-intro.mp3) | 6.5 / 5.4 s | 0.84 / 0.45 |
| Mưa kéo dài hơn hai giờ khiến nhiều đường ở Long Thành, Nhơn Trạch ngập gần nửa mét, xe chết máy, người dân phải dắt bộ, sáng 15/11. | [▶ Nghe M](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-m-news.mp3) | [▶ Nghe S](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-s-news.mp3) | 9.1 / 8.2 s | 0.84 / 0.43 |
| Pin còn 15%, nhiệt độ phòng là 28°C. Báo thức đã được đặt lúc 6 giờ 30 sáng mai. | [▶ Nghe M](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-m-numbers.mp3) | [▶ Nghe S](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-s-numbers.mp3) | 8.2 / 6.9 s | 0.82 / 0.42 |
| Bạn có muốn bật đèn phòng khách không? | [▶ Nghe M](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-m-question.mp3) | [▶ Nghe S](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-s-question.mp3) | 2.7 / 2.2 s | 0.94 / 0.45 |
| Đoạn bản tin thời tiết 5 câu (dấu phẩy, dấu chấm, số đọc thành chữ) | [▶ Nghe M](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-m-paragraph.mp3) | [▶ Nghe S](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-s-paragraph.mp3) | 30 / 26 s | 0.79 / 0.41 |

RTF ở bảng này đo khi tổng hợp cả câu một lần. Câu càng ngắn thì RTF càng cao vì có chi phí cố định cho mỗi câu. Khi phát loa, firmware dùng streaming nên câu bắt đầu phát trước khi tổng hợp xong.

## Kiến trúc

```mermaid
flowchart LR
    T["Văn bản UTF-8"] --> N["Chuẩn hoá<br/>(số, ngày giờ, viết tắt)"]
    N --> G["G2P bám chữ viết<br/>65 token, 6 thanh"]
    G --> D["Duration"]
    G --> A["Âm học + cao độ<br/>(latent 192)"]
    D --> A
    A --> V["Decoder Vocos-style<br/>ConvNeXt + iSTFT"]
    V --> P["PCM 22.05 kHz"]
```

Model nhỏ (student) được chưng cất từ một teacher VITS lớn: teacher sinh dữ liệu (thời lượng, latent, âm thanh) cho hàng chục nghìn câu, student học lại với ba giai đoạn (front, decoder, joint với bộ phân biệt đa phân giải). Chi tiết trong `docs/design/`.

Bộ token **bám chữ viết, không gắn với một vùng miền**: `tr`/`ch`, `s`/`x`, `r`/`d`/`gi` là các token riêng, 6 thanh theo dấu viết. Thêm giọng Huế, Nghệ An... chỉ cần thêm dữ liệu.

## Cấu trúc repo

| Thư mục | Nội dung |
|---|---|
| `runtime/` | Runtime C99 không `malloc`: tổng hợp fp32/int8, streaming khớp từng bit với tổng hợp cả câu, front-end văn bản tiếng Việt (`vtts_text`). `ports/esp32p4/` có kernel PIE SIMD và chạy 2 lõi |
| `firmware/esp32p4/` | Ứng dụng mẫu cho panel ESP32-P4: gõ câu qua serial, board đọc ra loa |
| `src/vtts/` | Gói Python: front-end, chuẩn bị dữ liệu, đánh giá, teacher, student, export |
| `scripts/` | Các bước pipeline, chia theo nhóm `data/`, `frontend/`, `teacher/`, `student/`, `eval/`, `device/` |
| `eval/` | Tập câu đánh giá, baseline, cấu hình trang nghe A/B |
| `docs/` | Thiết kế, định dạng file model, báo cáo số đo |
| `tests/` | Test Python và test runtime C (golden, int8, streaming, parity front-end, fuzz) |

## Bắt đầu nhanh

### Front-end và runtime trên máy tính

```bash
uv sync --extra gpu                 # Python 3.11, PyTorch
uv run pytest -q                    # test nhanh (gồm cả build runtime C với ASan/UBSan)
make -C runtime build/vtts_cli      # công cụ dòng lệnh C
uv run python -c "from vtts.frontend.text import text_to_ids; print(text_to_ids('Xin chào, hôm nay là 15/11.'))"
```

### Firmware ESP32-P4

Cần ESP-IDF v6.1 và hai file model int8 (`.vtts`): tải từ [Releases](https://github.com/tuanpmt/vtts/releases) hoặc tự export bằng `scripts/student/export_student.py --int8`.

```bash
gh release download v0.2.0 -R tuanpmt/vtts -p '*.vtts' -D models
cd firmware/esp32p4
./build.sh ../../models/vtts-vi-s-v0.1.q8.vtts ../../models/vtts-vi-m-v0.2.q8.vtts -p /dev/cu.usbmodemXXXX flash monitor
```

Trong cửa sổ serial, gõ một câu tiếng Việt rồi Enter. Các lệnh: `model s|m`, `vol 0-100`, `gain dB`, `speed 0.7-1.6`, `expr 0.5-2.5` (độ lên xuống của ngữ điệu, với model có cao độ), `bench`, `prof`, `selftest`, `dump <câu>` (tổng hợp và gửi audio về máy tính; lưu thành WAV bằng `scripts/device/p4_say.py PORT "dump <câu>" --dump-dir out/`).

### Train lại toàn bộ

1. Dữ liệu: `scripts/data/prepare_infore.py` → `score_dataset.py` → `filter_and_split.py`
2. Teacher: `scripts/teacher/train_teacher.py`, đánh giá bằng `eval_checkpoints.py`
3. Chưng cất: `scripts/student/build_distill_pack.py` → `convert_shards.py` → `add_prosody.py` → `run_prosody_chain.sh`
4. Export và kiểm tra: `export_student.py --int8`, `render_student_c.py`, `scripts/eval/eval_dir.py`

Quy trình không phụ thuộc nguồn dữ liệu: thay thư mục audio + transcript là chạy lại được từ đầu.

## Trạng thái

- Đây là prototype kiểm chứng chất lượng, train trên InfoRe1 (25 giờ, một người đọc).
- **Model prototype chỉ dùng phi thương mại**: hai file `.vtts` int8 (S và M) được đính kèm ở [Releases](https://github.com/tuanpmt/vtts/releases) theo giấy phép CC BY-NC 4.0, chỉ để nghiên cứu và chạy thử. Lý do: teacher được khởi tạo từ checkpoint Piper lessac (dữ liệu gốc chỉ cho dùng phi thương mại) và điều khoản thương mại của InfoRe1 chưa rõ. Checkpoint PyTorch và teacher không được phát hành. Bản dùng được cho thương mại sẽ có sau khi train lại trên bản thu âm có bản quyền.
- Ngữ điệu: v0.2 đã sửa tốc độ đọc và thêm bộ dự đoán cao độ; độ lên xuống vẫn còn hơi đều do người đọc InfoRe1 đọc khá đều giọng.
- Đang train một giọng mới trên bộ dữ liệu mở VietBibleVox (CC BY-SA 4.0, khoảng 60 giờ, một người đọc) với teacher train từ đầu, hướng tới model dùng được cho thương mại. Xem `scripts/data/prepare_bible.py`.

## Giấy phép

Code: Apache-2.0 (`LICENSE`). Phần sao chép từ Piper/VITS giữ giấy phép MIT gốc; xem `NOTICE`.

Model `.vtts` trong Releases: CC BY-NC 4.0, chỉ dùng phi thương mại (xem mục Trạng thái). Giấy phép Apache-2.0 của code không áp dụng cho các file model này.
