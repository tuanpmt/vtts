/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_resample.h -- streaming int16 sample-rate converter for speaker paths that cannot run at the
 * model rate (e.g. 22050 Hz models on a board whose I2S link is fixed at 16 kHz).
 *
 * Band-limited interpolation (J. O. Smith): every output sample is a dot product of the input with a
 * Kaiser-windowed sinc centred on the output time, read from a small table with linear interpolation
 * between its entries. The cutoff follows the lower of the two rates, so downsampling filters out what
 * would alias. Any ratio from 1/2 to 4 works; output times are tracked exactly (rates reduced by their
 * gcd), so long streams do not drift. The group delay is compensated: output sample j is the signal at
 * input time j * in_rate / out_rate. State: about 4.8 KB, no allocation. */
#ifndef VTTS_RESAMPLE_H
#define VTTS_RESAMPLE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define VTTS_RS_ZEROS 20  /* zero crossings of the windowed sinc on each side */
#define VTTS_RS_PHASES 48 /* table entries per zero crossing (linear interpolation in between) */
#define VTTS_RS_MAX_HALF 48 /* taps on each side at most (the 1/2 ratio needs 43) */
#define VTTS_RS_BUF 192   /* input history: 2 * VTTS_RS_MAX_HALF plus room for new samples */

typedef struct {
    int in_rate, out_rate; /* reduced by their gcd; equal rates: copy */
    float fc;              /* cutoff relative to the input Nyquist frequency (<= 1) */
    float step;            /* table entries per input sample: fc * VTTS_RS_PHASES */
    int half;              /* taps on each side of the output time */
    int pos, frac;         /* next output time: x[pos] + frac / out_rate input samples */
    int n;                 /* samples in x */
    long long n_in, n_out; /* totals since the last reset (the flush stops at the input's length) */
    float x[VTTS_RS_BUF];
    float k[VTTS_RS_ZEROS * VTTS_RS_PHASES + 2];
} vtts_resampler;

/* Set up the conversion from in_rate to out_rate (Hz) and reset the stream. Returns 0, or -1 for an
 * unsupported ratio (out_rate / in_rate below 1/2 or above 4) or a rate <= 0. */
int vtts_resample_init(vtts_resampler *r, int in_rate, int out_rate);

/* Start a new stream (e.g. a new utterance): clear the history and the totals. */
void vtts_resample_reset(vtts_resampler *r);

/* Upper bound on the samples that vtts_resample_process can write for n_in more input samples (and,
 * with n_in = 0, on what vtts_resample_flush writes). */
int vtts_resample_max_out(const vtts_resampler *r, int n_in);

/* Consume all n_in samples of in; write the output samples that are now complete to out (room for
 * vtts_resample_max_out(r, n_in)) and return how many. */
int vtts_resample_process(vtts_resampler *r, const int16_t *in, int n_in, int16_t *out);

/* End of the stream: write the remaining output (the last samples need input beyond the end, taken as
 * silence), so that the total output is ceil(total input * out_rate / in_rate). Returns the count. */
int vtts_resample_flush(vtts_resampler *r, int16_t *out);

#ifdef __cplusplus
}
#endif
#endif
