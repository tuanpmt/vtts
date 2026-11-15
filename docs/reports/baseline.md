# Báo cáo baseline

Hai giọng tiếng Việt có sẵn, chạy như hộp đen (`eval/baselines/render.py`). Đầu vào cho cả hai là văn bản đã chuẩn hoá bằng `vtts.frontend.normalize`, để cách đọc số và viết tắt giống nhau.

- ASR chấm điểm: `vinai/PhoWhisper-large`. CER/WER giữ nguyên dấu thanh, nên đọc sai thanh cũng tính là lỗi.
- UTMOS (`utmos22_strong`) và DNSMOS (OVRL) là chỉ số dự đoán độ tự nhiên/độ sạch, được huấn luyện chủ yếu trên tiếng Anh. Chỉ dùng để so sánh giữa các hệ thống tiếng Việt với nhau.
- Chỉ số rít: số ô phổ thuộc các vệt âm sắc đứng yên, tính trên mỗi giây (thấp là tốt).

## Tập ngoài miền (`eval/sets/ood.jsonl`, 50 câu)

| Hệ thống | CER | WER | UTMOS | DNSMOS | Rít |
|---|---:|---:|---:|---:|---:|
| sanoTTS `vi` (1.57M, Piper VAIS1000 làm teacher) | 0.064 | 0.127 | 1.49 | 2.83 | 1.5 |
| Piper `vi_VN-25hours_single-low` (InfoRe1) | 0.089 | 0.197 | 2.06 | 2.43 | 1.1 |

CER theo nhóm câu:

| Nhóm | sanoTTS `vi` | Piper 25h |
|---|---:|---:|
| device (thông báo thiết bị) | 0.117 | 0.109 |
| numbers (số, ngày, giờ, tiền) | 0.032 | 0.081 |
| names (tên người, địa danh) | 0.125 | 0.143 |
| prosody (câu hỏi, cảm thán) | 0.072 | 0.111 |
| long (> 30 âm tiết) | 0.046 | 0.068 |

Ví dụ lỗi điển hình (tham chiếu → ASR nghe được):

- sanoTTS `vi`: "Phố cổ Hội An lung linh đèn lồng về đêm" → "phố cổ hội an lũng nghinh đằng lùng về đằng kia"; "Pin yếu, vui lòng cắm sạc ngay" → mất hai âm tiết đầu.
- Piper 25h: "Cẩn thận, sàn nhà đang ướt!" → "thân thân xanh nhả nặng ruột"; "Chúc bạn ngủ ngon" → "chúc bạn hy vọng".

## Nhận xét

- Câu ngắn kiểu thông báo thiết bị (nhóm `device`) là điểm yếu chung của cả hai. Đây chính là kiểu câu sản phẩm ESP32 sẽ đọc nhiều nhất.
- sanoTTS `vi` rõ chữ hơn Piper 25h, nhưng UTMOS thấp hơn (1.49 so với 2.06): đọc rõ hơn nhưng nghe kém tự nhiên hơn.
- CER được tính sau khi chuẩn hoá vị trí dấu thanh (`hoà` và `hòa` coi là một), để không phạt khác biệt chính tả thuần tuý.
- WER 0.127 của sanoTTS `vi` ở đây thấp hơn con số 0.468 trong README của sanoTTS, vì khác ASR (PhoWhisper so với Whisper) và khác tập câu. Chỉ so sánh các con số trong cùng một báo cáo.

## Cổng teacher suy ra (theo spec mục 6)

Trên tập ngoài miền, teacher của dự án phải đạt:

- CER ≤ 50% của sanoTTS `vi`, tức **CER ≤ 0.032**;
- và CER ≤ Piper 25h (0.089). Điều kiện này tự thoả khi đã đạt điều kiện trên.

Số đo trên tập held-out (50 câu InfoRe1) sẽ được bổ sung sau khi lọc dữ liệu xong.
