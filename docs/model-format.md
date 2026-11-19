# `VTTS` model file format (version 1, revision 1.1)

One file holds all three blocks of a student model (duration, acoustic, decoder). All numbers are little-endian. The C runtime reads only this file and hard-codes no shapes.

## Layout

| Region | Size | Contents |
|---|---|---|
| Header | 20 bytes | `magic` = `"VTTS"` (4 bytes), `version` u32 = 1, `n_dims` u32, `n_tensors` u32, `payload_offset` u32 |
| Dims | `n_dims` × 36 bytes | `key` char[32] (NUL-padded), `value` i32 |
| Tensor table | `n_tensors` × 80 bytes | see below |
| Payload | the rest | tensor data, each tensor aligned to 16 bytes |

Each tensor table entry (80 bytes):

| Field | Type | Meaning |
|---|---|---|
| `name` | char[48] | tensor name, e.g. `dur.blocks.0.conv.weight` |
| `dtype` | u8 | 0 = f32, 1 = i8 |
| `ndim` | u8 | 1–4 |
| `_pad` | u16 | 0 |
| `shape` | i32[4] | unused dimensions = 1 |
| `offset` | u32 | payload position from the start of the file |
| `nbytes` | u32 | payload size |
| `scale_offset` | u32 | for i8: position of the f32 array of per-output-channel scales (dimension 0); for f32: 0 |

## Required dims

`vocab`, `latent`, `hop`, `sample_rate`, `max_duration`, `d_hidden`, `d_depth`, `d_kernel`, `a_hidden`, `a_token_depth`, `a_frame_depth`, `a_kernel`, `decoder` (0 = hifigan, 1 = istft, 2 = vocos), plus the decoder-specific dims: `c0`, `n_up`, `up0..up3`, `upk0..upk3`, `n_res`, `res_d0..res_d3`, `res_kernel`, `n_fft`, `istft_hop`, `v_dim`, `v_blocks`, `v_mult`. Floating-point values (activation quantization scales) live in a separate f32 tensor named `act_scales`.

`vocab` is the number of embedding rows (at least the size of the token set the model was trained with), so a model for a new language needs no runtime change.

## Optional dims

| Dim | Meaning | When absent |
|---|---|---|
| `prosody`, `p_depth` | Pitch/energy predictor (prosody models) | 0: no prosody branch |
| `expr_milli` | Default expressiveness × 1000 | 1000 |
| `token_set` | Token set the model was trained with (below) | derived from `vocab` |

Unknown dims are ignored by every runtime, so new optional dims keep the format at version 1: older firmware loads newer files, and newer firmware loads older files.

### `token_set` (added in format revision 1.1)

The token set decides which text front-end produces the ids, so the firmware and host tools pick the front-end from it rather than guessing from `vocab`.

| Code | Name | Ids | Device text modes |
|---|---|---|---|
| 0 | not recorded (same as absent) | | |
| 1 | `v1` (Vietnamese) | 65 | `vi` |
| 2 | `vi-en` (v2) | 107 | `vi`, `en`, `auto` |
| 3 | `zh-en` | 171 | `zh` |
| 4 | `ko-en` | 153 | `ko` |
| 5 | `ja-en` | 144 | `ja` |
| 6 | `es-en` | 138 | `es` |
| 7 | `id-en` | 141 | `id` |
| 8 | `pt-en` | 150 | `pt` |
| 9 | `th-en` | 162 | `th` |
| 10 | `hi-en` | 157 | `hi` |
| 11 | `fr-en` | 143 | `fr` (device: when built with `VTTS_ENABLE_FR`) |
| 12 | `de-en` | 167 | `de` (device: when built with `VTTS_ENABLE_DE`) |
| 13 | `it-en` | 142 | `it` (device: when built with `VTTS_ENABLE_IT`) |
| 14 | unused | | |
| 15 | `tr-en` | 146 | `tr` (device: when built with `VTTS_ENABLE_TR`) |
| 16 | `ru-en` | 154 | `ru` (device: when built with `VTTS_ENABLE_RU`; RLEX blob for the stress tables) |
| 17 | `pl-en` | 151 | `pl` (device: when built with `VTTS_ENABLE_PL`) |
| 18 | unused | | |
| 19 | `ar-en` | 149 | `ar` (device: when built with `VTTS_ENABLE_AR`) |
| 20 | unused | | |
| 21 | `nl-en` | 159 | `nl` (device: when built with `VTTS_ENABLE_NL`) |
| 22 | `da-en` | 158 | `da` (device: when built with `VTTS_ENABLE_DA`) |
| 23 | `sv-en` | 155 | `sv` (device: when built with `VTTS_ENABLE_SV`) |
| 24 | `no-en` | 156 | `no` (device: when built with `VTTS_ENABLE_NO`) |
| 25 | `fi-en` | 142 | `fi` (device: when built with `VTTS_ENABLE_FI`) |
| 26 | `el-en` | 139 | `el` (device: when built with `VTTS_ENABLE_EL`) |
| 27 | reserved | | |
| 28 | `ms-en` | 145 | `ms` (device: when built with `VTTS_ENABLE_MS`) |
| 29 | `tl-en` | 139 | `tl` (device: when built with `VTTS_ENABLE_TL`) |
| 30 | `my-en` | 160 | `my` (device: when built with `VTTS_ENABLE_MY`) |
| 31 | `km-en` | 176 | `km` (device: when built with `VTTS_ENABLE_KM`) |
| 32 | `lo-en` | 163 | `lo` (device: when built with `VTTS_ENABLE_LO`) |
| 33 | `sw-en` | 147 | `sw` (device: when built with `VTTS_ENABLE_SW`) |

The names and sizes are those of `TOKEN_SETS` in `src/vtts/frontend/phoneme_set.py`. Reading rules (`vtts_init`, `vtts.export.format.token_set_of`):

- Present with a known code: `vocab` must be at least the set's size, else the file is rejected (`VTTS_ERR_FORMAT`).
- Present with a code this runtime does not know: the model loads with token set `unknown`; only raw ids can be synthesized.
- Absent or 0 (all files exported before revision 1.1): by `vocab`: 65 → `v1`, 107 → `vi-en`, 171 → `zh-en`, 153 → `ko-en`, 144 → `ja-en`, 138 → `es-en`, 141 → `id-en`, 150 → `pt-en`, 162 → `th-en`, 157 → `hi-en` (only the sets that existed before the dim, codes 1-10, whose sizes are distinct; a set added later is never inferred, its size may equal another's); any other `vocab` > 65 → `vi-en` and ≤ 65 → `v1` (the rule the firmware used before).

Writers (`write_model`, `write_model_int8`, `scripts/student/export_student.py`) record the set given with `token_set=` / `--token-set`, else the one set whose size is the `vocab` (no dim when several sets have that size, such as it-en and fi-en; `export_student.py` then requires `--token-set`); a model with spare embedding rows needs the explicit argument. C: `vtts_token_set(&m)`, `vtts_token_set_name()`, `vtts_token_set_size()`; `m.token_set_in_file` tells whether the file had the dim.

## Tensor names

Tensor names are the PyTorch `state_dict` names (`duration.*`, `acoustic.*`, `decoder.*`). Convolutions with weight normalization must have their weights folded before export.

## Load-time checks

`vtts_init` returns a negative error code when: the magic is wrong, the version is not 1, a known `token_set` is larger than `vocab`, the tensor table or payload exceeds the file size, `offset + nbytes` exceeds the file size, a required dim is missing, or a tensor needed by the graph is missing.
