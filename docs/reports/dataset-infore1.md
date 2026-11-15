# Báo cáo dữ liệu InfoRe1

## Tóm tắt

| Bước | Số câu | Số giờ |
|---|---:|---:|
| Gốc (`doof-ferb/infore1_25hours`) | 14,935 | 24.54 |
| Sau lọc | 13,780 | ~22.7 |
| Train | 13,455 | 22.20 |
| Validation | 275 | 0.43 |
| Held-out (đánh giá, 3–10 giây/câu) | 50 | 0.08 |

Chuẩn bị audio: chuyển sang 22,050 Hz mono, cắt khoảng lặng hai đầu (ngưỡng −40 dB, đệm 50 ms), chuẩn hoá RMS về −23 dBFS với đỉnh tối đa −1 dBFS. Không có câu nào hỏng audio hoặc thiếu transcript.

## Lọc

Chấm điểm: ASR `vinai/PhoWhisper-small` (bản small nhanh gấp 6 lần bản large, đủ dùng cho việc lọc) và DNSMOS OVRL cho từng câu.

| Lý do loại | Số câu | Ngưỡng |
|---|---:|---|
| DNSMOS thấp | 623 | OVRL < 2.42 (phân vị 5%) |
| Chứa từ phải đánh vần từng chữ cái | 357 | từ không phải âm tiết tiếng Việt và không có trong bảng từ mượn |
| Transcript lệch ASR | 174 | CER > 0.10 |
| Quá ngắn | 1 | < 1 giây |

**Ngưỡng DNSMOS được hạ từ 3.0 (kế hoạch) xuống 2.42.** DNSMOS của toàn bộ InfoRe1 có trung vị chỉ 2.88, nên ngưỡng 3.0 sẽ loại khoảng 60% dữ liệu. Ngưỡng mới chỉ loại 5% câu tệ nhất.

**Từ phải đánh vần**: dòng có từ như `hlv`, `usd` đứng một mình, hay tên riêng nước ngoài viết liền bị loại, vì nhãn đánh vần ("hát e lờ vê") không khớp với điều người đọc thực sự nói ("huấn luyện viên").

## Câu bị loại vì CER (10 ví dụ)

Phần lớn là **loại oan**: ASR viết từ mượn theo chính tả tiếng Anh, trong khi transcript viết theo cách đọc tiếng Việt. Một số ít là lỗi thật: audio bị cắt cụt, hoặc transcript lặp câu.

| CER | ID | Transcript | ASR nghe được | Nhận định |
|---:|---|---|---|---|
| 0.54 | infore_13364 | hiện tại rô nan đô và men đét chưa đưa ra bình luận… | hiện tại ronaldo và mandel chưa đưa ra bình luận… | loại oan |
| 0.52 | infore_11723 | nên mua ghế mát xa loại nào… | nên mua ghế massage loại nào… | loại oan |
| 0.51 | infore_08252 | làm sạch đồng hồ mạ vàng… (lặp hai lần) | làm sạch đồng hồ mạ vàng… (một lần) | transcript lặp, loại đúng |
| 0.47 | infore_13727 | …có thể ghé đến nha khoa kim để được… | …có thể ghé đến. | audio cụt, loại đúng |
| 0.46 | infore_12176 | …người khác mát xa lưng… | …người khác massage lưng… | loại oan |
| 0.44 | infore_14021 | …phải ký cam mổ mở thì mới phẫu thuật… | …phải ký cam mổ. | audio cụt, loại đúng |
| 0.42 | infore_02939 | trước khi mát xa mặt… các cơ | trước khi massage mặt… các cô | phần lớn oan |
| 0.41 | infore_04271 | …bao cao su đôn dên | …bao cao su donetsk | loại oan |
| 0.41 | infore_12616 | …vi ta min e và vi ta min c… | …vitamin e và vitamin c… | loại oan |
| 0.38 | infore_05505 | sửa ti vi sam sung… | sửa tivi samsung… | loại oan |

Vì chỉ mất 1.2% dữ liệu nên không cần sửa ngay. Cải tiến sau này: thêm các từ mượn phổ biến (massage, vitamin, samsung…) vào bảng từ mượn để cả transcript lẫn ASR quy về cùng một cách đọc.

## Phân bố thanh điệu (tập train, số âm tiết)

| ngang | huyền | sắc | hỏi | ngã | nặng |
|---:|---:|---:|---:|---:|---:|
| 70,946 | 51,431 | 62,666 | 28,002 | 14,287 | 47,446 |

Thanh ngã ít nhất (5.5%) nhưng vẫn có hơn 14 nghìn mẫu, đủ để học.
