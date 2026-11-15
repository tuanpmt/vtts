# Kế hoạch 3: Student chưng cất, exporter và runtime C

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Student S và M chưng cất từ teacher, chạy được bằng runtime C99 tự viết (fp32 và int8) trên host, qua golden gate; chọn decoder theo số đo chất lượng so với lượng phép tính để vừa ngân sách real-time của ESP32-P4.

**Architecture:** Student gồm 3 khối: duration (conv mức token), âm học (conv mức token → mở rộng theo duration + vị trí tương đối trong token → conv mức frame → latent 192 kênh), decoder. Decoder là một họ có cấu hình: `hifigan` (upsample 8×8×4 về thẳng waveform) và `istft` (upsample ít hơn rồi iSTFT nhỏ, ví dụ upsample 8×8 + iSTFT n_fft 16 hop 4). Tập phép toán cố định: Embedding, Conv1d (có dilation), ConvTranspose1d, LeakyReLU, ReLU, LayerNorm theo kênh, Linear, tanh, iDFT nhỏ, mở rộng theo duration. Runtime C triển khai đúng tập này, đọc một file model tự mô tả. Chưng cất: teacher sinh dữ liệu cho mọi câu trong kho văn bản; mục tiêu là duration và latent `z` của teacher (noise của prior cố định bằng 0, để mục tiêu tất định) cùng audio do decoder teacher sinh từ `z`.

**Tech Stack:** PyTorch (train), C99 + Make (runtime, host test), numpy (golden).

**Spec:** `docs/design/specs/2026-11-14-vietnamese-tts-p4-design.md` (mục 5.5, 5.6)

## Global Constraints

- Ràng buộc chung của Kế hoạch 1 và 2 vẫn áp dụng.
- Runtime C: C99, không `malloc`; caller cấp arena và có hàm tính trước kích thước arena; không hardcode shape nào.
- Định dạng file model: magic `VTTS`, version `1`, bảng tensor (tên, dtype `f32`/`i8`, shape, offset, scale theo kênh), dims dạng key/value. Python exporter và C parser cùng dựa trên một mô tả định dạng duy nhất trong `docs/model-format.md`.
- Golden gate: C fp32 so với PyTorch có tương quan ≥ 0.9999, duration khớp tuyệt đối; int8 so với fp32 có tương quan > 0.98 và 0.80 < tỉ lệ RMS < 1.25; duration int8 lệch tối đa 1 frame mỗi token và tối đa 1% tổng số frame.
- Ngân sách phép tính (đo bằng bộ đếm MAC của exporter): **S ≤ 120 MMAC/s audio**, **M ≤ 300 MMAC/s audio**. Decoder nào vượt ngân sách thì không được chọn, dù nghe hay hơn.

## Review Focus

1. Câu chỉ có 1 token hoặc duration bị kẹp về 1 frame: không được tràn arena, không chia cho 0.
2. Câu dài 40 âm tiết (chunk tối đa của front-end): arena đủ lớn và kích thước arena được tính đúng trước khi chạy.
3. File model sai hoặc cụt (magic sai, version khác, offset vượt kích thước): `init` trả về mã lỗi âm, không đọc ra ngoài vùng nhớ.
4. Activation int8 bị bão hoà ở tầng cuối: phải thể hiện qua tỉ lệ RMS, không bị che bởi tương quan cao.
5. Biên giữa các chunk khi ghép câu: không có tiếng click (fade 5 ms ở biên).

---

### Task 1: Student model PyTorch + bộ đếm MAC
`src/vtts/student/{config,model,macs}.py`. `StudentConfig(size="S"|"M", decoder="hifigan"|"istft", ...)`; `Student.forward_duration(ids) -> log_dur`; `Student.forward_latent(ids, durations) -> z[192, T]`; `Student.decode(z) -> wav`; `count_macs(cfg) -> {"duration","acoustic","decoder","per_second"}`. Test: shape; MAC của mỗi preset nằm trong ngân sách; số tham số của S trong 0.4–0.8M, của M trong 1.2–2.0M.

### Task 2: Sinh bộ dữ liệu chưng cất
`src/vtts/student/distill_data.py`, `scripts/student/build_distill_pack.py`. Với mỗi câu trong kho văn bản (InfoRe1 train + câu tổng hợp; mục tiêu ≥ 50k câu), teacher (`best.pt`, noise 0) sinh `ids`, `durations` (số nguyên), `z` (fp16) và `audio` (int16). Ghi thành các shard `.npz`, mỗi shard 1000 câu. Test: shard đọc lại khớp đúng shape; tổng duration × 256 bằng độ dài audio.

### Task 3: Train student (3 giai đoạn)
`src/vtts/student/train.py`. (a) duration: MSE trên log-duration; (b) âm học: L1 + cosine trên `z`, có teacher forcing duration; (c) decoder: multi-resolution STFT + mel L1 + MPD/MRD adversarial + feature matching, input là `z` của teacher; (d) joint finetune với `z` do student dự đoán. Resume và NaN-skip giống Kế hoạch 2. Test: một bước CPU cho mỗi giai đoạn ra loss hữu hạn.

### Task 4: Định dạng model + exporter fp32 + golden
`docs/model-format.md`, `src/vtts/export/format.py`, `src/vtts/export/export.py`, `scripts/student/export_student.py`. Golden: `ids`, `durations`, `z`, `pcm` cho 5 câu. Test: round-trip đọc/ghi file model trong Python.

### Task 5: Runtime C fp32
`runtime/include/vtts.h`, `runtime/src/{model,ops,frontend_ids,synth}.c`, `runtime/test/golden_test.c`, `runtime/Makefile`. API: `vtts_init`, `vtts_arena_bytes(model, n_tokens, max_frames)`, `vtts_durations`, `vtts_synthesize`. Test (`make test`): golden fp32 qua cổng; các file model hỏng trả mã lỗi âm (chạy dưới ASan/UBSan).

### Task 6: Lượng tử hoá int8 + runtime int8
Trọng số int8 theo kênh, activation làn int16 giữ 12-bit, scale tĩnh hiệu chỉnh trên 200 câu; tầng cuối trước tanh và đầu log-duration giữ fp32. Port API `vtts_port.h` (dot/matvec s8 và s16×s8, `weights_resident`, `now_us`) với bản C tham chiếu. Test: golden int8 qua cổng.

### Task 7: Tìm decoder + đánh giá + tối ưu
Train 2–4 cấu hình decoder (hifigan-S, istft-S, istft-M, …) trên 2 GPU. Đánh giá bằng `eval_dir` (CER, UTMOS, chỉ số rít) với student fp32 và int8 trên host. Chọn theo luật: trong ngân sách MAC, CER ≤ 1.3 lần teacher, ít rít nhất. Viết `docs/reports/student.md`.

**Cổng kết thúc Kế hoạch 3:** có ít nhất một student qua cổng CER và qua golden int8 trên host, với MMAC/s trong ngân sách. Sau đó sang Kế hoạch 4 (port P4, đo trên chip, vòng đánh giá và tối ưu cuối).
