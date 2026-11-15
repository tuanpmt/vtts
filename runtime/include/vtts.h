/* SPDX-License-Identifier: Apache-2.0 */
/* vtts.h -- tiny Vietnamese TTS runtime (C99, no malloc).
 *
 * Pipeline: phoneme ids -> durations -> latent [latent, frames] -> PCM (22.05 kHz).
 * The model file format is described in docs/model-format.md. All working
 * memory comes from a caller-provided arena sized with vtts_arena_bytes().
 */
#ifndef VTTS_H
#define VTTS_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define VTTS_MAX_TENSORS 256
#define VTTS_MAX_DIMS 64

enum {
    VTTS_OK = 0,
    VTTS_ERR_ARGS = -1,
    VTTS_ERR_FORMAT = -2,
    VTTS_ERR_MISSING = -3,
    VTTS_ERR_ARENA = -4,
    VTTS_ERR_RANGE = -5
};

enum { VTTS_DEC_HIFIGAN = 0, VTTS_DEC_ISTFT = 1, VTTS_DEC_VOCOS = 2 };

typedef struct {
    const char *name; /* points into the model blob (NUL padded field) */
    int dtype;        /* 0 = f32, 1 = i8 */
    int ndim;
    int32_t shape[4];
    const void *data;
    const float *scale; /* i8 only: per-out-channel scales */
} vtts_tensor;

typedef struct {
    /* dims */
    int vocab, latent, hop, sample_rate, max_duration;
    int d_hidden, d_depth, d_kernel;
    int a_hidden, a_token_depth, a_frame_depth, a_kernel;
    int decoder, c0, n_up, up[4], upk[4], n_res, res_d[4], res_kernel;
    int n_fft, istft_hop, v_dim, v_blocks, v_mult;
    int prosody, p_depth, expr_milli; /* prosody branch (v2) and its default expressiveness x1000 */
    float expressiveness;            /* scales the predicted log-F0 deviation; 1 = as trained */
    /* tensors */
    int n_tensors;
    vtts_tensor t[VTTS_MAX_TENSORS];
} vtts_model;

/* Parse a model blob (must stay alive while the model is used). */
int vtts_init(vtts_model *m, const void *blob, size_t blob_bytes);

/* Arena bytes needed for n_ids tokens and up to max_frames total frames. */
size_t vtts_arena_bytes(const vtts_model *m, int n_ids, long max_frames);

/* ids -> integer frame counts in [1, max_duration]; returns total frames (>0) or error (<0).
 * log_dur_out may be NULL. */
long vtts_durations(const vtts_model *m, const int32_t *ids, int n_ids, float length_scale,
                    int32_t *dur_out, float *log_dur_out, void *arena, size_t arena_bytes);

/* ids + durations -> latent [latent, frames] (channel-major). Returns frames or error. */
long vtts_latent(const vtts_model *m, const int32_t *ids, const int32_t *dur, int n_ids,
                 float *latent_out, void *arena, size_t arena_bytes);

/* latent [latent, frames] -> pcm[frames * hop] in [-1, 1]. Returns samples or error. */
long vtts_decode(const vtts_model *m, const float *latent, long frames, float *pcm_out,
                 void *arena, size_t arena_bytes);

/* Convenience: ids -> pcm. pcm_out must hold vtts_durations(...) * hop samples. */
long vtts_synthesize(const vtts_model *m, const int32_t *ids, int n_ids, float length_scale,
                     float *pcm_out, long pcm_capacity, void *arena, size_t arena_bytes);

/* Streaming synthesis (vocos decoder only): PCM is produced chunk by chunk through `cb`
 * (return non-zero from cb to abort). Output equals vtts_synthesize() exactly; working
 * memory depends on chunk_frames, not on utterance length. Returns total samples or error
 * (VTTS_ERR_ARGS for decoders that do not support streaming). */
typedef int (*vtts_pcm_cb)(const float *pcm, long n, void *user);
size_t vtts_stream_arena_bytes(const vtts_model *m, int n_ids, int chunk_frames);
long vtts_synthesize_stream(const vtts_model *m, const int32_t *ids, int n_ids, float length_scale,
                            int chunk_frames, vtts_pcm_cb cb, void *user, void *arena,
                            size_t arena_bytes);

/* Same, with a small first chunk for low time-to-first-audio; later chunks double in size up to
 * chunk_frames (first_chunk <= chunk_frames);
 * vtts_stream_arena_bytes(m, n_ids, chunk_frames) covers it. */
long vtts_synthesize_stream_ex(const vtts_model *m, const int32_t *ids, int n_ids, float length_scale,
                               int first_chunk, int chunk_frames, vtts_pcm_cb cb, void *user,
                               void *arena, size_t arena_bytes);

/* Prosody models only: scale the predicted pitch movement (1.0 = as trained, >1 livelier). */
void vtts_set_expressiveness(vtts_model *m, float e);

/* Tensor lookup by name (NULL when missing). */
const vtts_tensor *vtts_find(const vtts_model *m, const char *name);

#ifdef __cplusplus
}
#endif
#endif
