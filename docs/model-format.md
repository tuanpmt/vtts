# `VTTS` model file format (version 1)

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

`vocab` is the size of the token set the model was trained with (65 for token set v1, 107 for v2), so a model for a new language needs no runtime change.

## Tensor names

Tensor names are the PyTorch `state_dict` names (`duration.*`, `acoustic.*`, `decoder.*`). Convolutions with weight normalization must have their weights folded before export.

## Load-time checks

`vtts_init` returns a negative error code when: the magic is wrong, the version is not 1, the tensor table or payload exceeds the file size, `offset + nbytes` exceeds the file size, a required dim is missing, or a tensor needed by the graph is missing.
