/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_port_s3.c -- ESP32-S3 SIMD kernels for the vtts runtime (overrides the weak C ones).
 *
 * The S3's 128-bit extension multiplies 16 signed bytes per instruction and accumulates into
 * the 40-bit ACCX register (ee.vmulas.s8.accx); ee.srs.accx with a zero shift reads it back.
 * Loops use the Xtensa zero-overhead loop (loopnez).
 *
 * The fused multiply-accumulate-and-load form (ee.vmulas.s8.accx.ld.ip) used by the P4 port is
 * deliberately avoided: on the S3 it returned wrong sums when both cores ran it at the same time
 * (single-core runs were exact), while this plain load + multiply-accumulate loop stays exact on
 * two cores. The firmware's selftest checks both cases. */
#include <stdint.h>

#include "vtts_port.h"

static int32_t dot_scalar(const int8_t *a, const int8_t *b, int n) {
    int32_t s = 0;
    for (int i = 0; i < n; i++) s += (int32_t)a[i] * (int32_t)b[i];
    return s;
}

/* blocks of 16 bytes, both pointers 16-byte aligned */
static inline int32_t dot_simd(const int8_t *a, const int8_t *b, int32_t blocks) {
    int32_t res;
    asm volatile(
        "ee.zero.accx\n\t"
        "loopnez %[k], 1f\n\t"
        "ee.vld.128.ip q0, %[a], 16\n\t"
        "ee.vld.128.ip q1, %[b], 16\n\t"
        "ee.vmulas.s8.accx q0, q1\n\t"
        "1:\n\t"
        "movi a8, 0\n\t"
        "ee.srs.accx %[res], a8, 0\n\t"
        : [res] "=&r"(res), [a] "+r"(a), [b] "+r"(b)
        : [k] "r"(blocks)
        : "a8", "memory");
    return res;
}

int32_t vtts_dot_s8s8(const int8_t *a, const int8_t *b, int n) {
    if ((((uintptr_t)a | (uintptr_t)b) & 15) || (n & 15) || n == 0) return dot_scalar(a, b, n);
    return dot_simd(a, b, n >> 4);
}

void vtts_dots_s8s8(const int8_t *w, const int8_t *x, int stride, int n, int len, int32_t *out) {
    if ((((uintptr_t)w | (uintptr_t)x) & 15) || (len & 15) || (stride & 15) || len == 0) {
        for (int t = 0; t < n; t++) out[t] = dot_scalar(w, x + (long)t * stride, len);
        return;
    }
    for (int t = 0; t < n; t++) out[t] = dot_simd(w, x + (long)t * stride, len >> 4);
}
