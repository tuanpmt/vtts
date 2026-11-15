# Nguồn gốc mã trong thư mục này

Các file `attentions.py`, `commons.py`, `losses.py`, `mel_processing.py`, `models.py`,
`modules.py`, `transforms.py` được sao chép từ `rhasspy/piper` commit `73c04d8`
(`src/python/piper_train/vits/`), giấy phép MIT, Copyright (c) 2022 Michael Hansen. Xem
`LICENSE-piper.md`. Bản thân mã đó dựa trên VITS (jaywalnut310/vits, MIT).

`monotonic_align.py` do dự án viết lại bằng numba (thuật toán Monotonic Alignment Search
trong bài báo VITS, Kim et al. 2021) thay cho bản Cython gốc.

Không có thay đổi nào khác so với bản gốc, trừ khi được ghi chú trong lịch sử git.
