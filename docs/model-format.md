# Định dạng file model `VTTS` (version 1)

Một file chứa cả ba khối của student (duration, âm học, decoder). Mọi số đều little-endian. Runtime C chỉ đọc file này; không hardcode shape nào.

## Bố cục

| Vùng | Kích thước | Nội dung |
|---|---|---|
| Header | 20 byte | `magic` = `"VTTS"` (4 byte), `version` u32 = 1, `n_dims` u32, `n_tensors` u32, `payload_offset` u32 |
| Dims | `n_dims` × 36 byte | `key` char[32] (đệm NUL), `value` i32 |
| Bảng tensor | `n_tensors` × 80 byte | xem dưới |
| Payload | còn lại | dữ liệu tensor, mỗi tensor căn lề 16 byte |

Mỗi dòng trong bảng tensor (80 byte):

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `name` | char[48] | tên tensor, ví dụ `dur.blocks.0.conv.weight` |
| `dtype` | u8 | 0 = f32, 1 = i8 |
| `ndim` | u8 | 1–4 |
| `_pad` | u16 | 0 |
| `shape` | i32[4] | các chiều không dùng = 1 |
| `offset` | u32 | vị trí payload tính từ đầu file |
| `nbytes` | u32 | kích thước payload |
| `scale_offset` | u32 | với i8: vị trí mảng f32 scale theo kênh ra (chiều 0); với f32: 0 |

## Dims bắt buộc

`vocab`, `latent`, `hop`, `sample_rate`, `max_duration`, `d_hidden`, `d_depth`, `d_kernel`, `a_hidden`, `a_token_depth`, `a_frame_depth`, `a_kernel`, `decoder` (0 = hifigan, 1 = istft, 2 = vocos), cùng các dims riêng của decoder: `c0`, `n_up`, `up0..up3`, `upk0..upk3`, `n_res`, `res_d0..res_d3`, `res_kernel`, `n_fft`, `istft_hop`, `v_dim`, `v_blocks`, `v_mult`. Các giá trị số thực (scale lượng tử hoá activation) nằm ở tensor f32 riêng tên `act_scales`.

## Tên tensor

Giữ nguyên tên `state_dict` của PyTorch (`duration.*`, `acoustic.*`, `decoder.*`). Riêng conv có weight norm thì phải gộp weight trước khi export.

## Kiểm tra khi nạp

`vtts_init` trả về mã lỗi âm khi: magic sai, version khác 1, bảng tensor hoặc payload vượt kích thước file, `offset + nbytes` vượt kích thước file, thiếu dims bắt buộc, hoặc thiếu tensor mà đồ thị cần.
