/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_port_s3.c -- ESP32-S3 SIMD kernels for the vtts runtime (overrides the weak C ones).
 *
 * The S3's 128-bit extension multiplies 16 signed bytes per instruction and accumulates into
 * the 40-bit ACCX register (ee.vmulas.s8.accx); ee.srs.accx with a zero shift reads it back.
 *
 * The block loops are plain branch loops, not the Xtensa zero-overhead loop (loopnez): with
 * loopnez around the 128-bit loads the dot products were now and then wrong during synthesis
 * (one value in about 10^6, more with two cores and with more cache misses; heard as short
 * bursts or a changed token duration that differed from run to run), while the same loads in a
 * branch loop and the plain C dot gave the ESP32-P4's output in every test. The P4 port avoids
 * its hardware loop for a similar silicon reason.
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

/* blocks of 16 bytes (>= 1), both pointers 16-byte aligned */
static inline int32_t dot_simd(const int8_t *a, const int8_t *b, int32_t blocks) {
    int32_t res;
    asm volatile(
        "ee.zero.accx\n\t"
        "1:\n\t"
        "ee.vld.128.ip q0, %[a], 16\n\t"
        "ee.vld.128.ip q1, %[b], 16\n\t"
        "addi %[k], %[k], -1\n\t"
        "ee.vmulas.s8.accx q0, q1\n\t"
        "bnez %[k], 1b\n\t"
        "movi a8, 0\n\t"
        "ee.srs.accx %[res], a8, 0\n\t"
        : [res] "=&r"(res), [a] "+r"(a), [b] "+r"(b), [k] "+r"(blocks)
        :
        : "a8", "memory");
    return res;
}

/* Fused form under investigation: ee.vmulas.s8.accx.ld.ip multiplies one block and loads the next
 * `a` block in the same instruction (2 instructions per block instead of 3). Selected at run
 * time by vtts_s3_kernel = 1 (test hook; 0 = plain loop). No load past the last block. */
int vtts_s3_kernel = 0;

static inline int32_t dot_fused(const int8_t *a, const int8_t *b, int32_t blocks) {
    int32_t res, pairs = (blocks - 1) >> 1, odd = (blocks - 1) & 1;
    asm volatile(
        "ee.zero.accx\n\t"
        "ee.vld.128.ip q0, %[a], 16\n\t"
        "ee.vld.128.ip q1, %[b], 16\n\t"
        "loopnez %[p], 1f\n\t"
        "ee.vmulas.s8.accx.ld.ip q2, %[a], 16, q0, q1\n\t"
        "ee.vld.128.ip q3, %[b], 16\n\t"
        "ee.vmulas.s8.accx.ld.ip q0, %[a], 16, q2, q3\n\t"
        "ee.vld.128.ip q1, %[b], 16\n\t"
        "1:\n\t"
        "beqz %[o], 2f\n\t"
        "ee.vmulas.s8.accx.ld.ip q2, %[a], 16, q0, q1\n\t"
        "ee.vld.128.ip q3, %[b], 16\n\t"
        "ee.vmulas.s8.accx q2, q3\n\t"
        "j 3f\n\t"
        "2:\n\t"
        "ee.vmulas.s8.accx q0, q1\n\t"
        "3:\n\t"
        "movi a8, 0\n\t"
        "ee.srs.accx %[res], a8, 0\n\t"
        : [res] "=&r"(res), [a] "+r"(a), [b] "+r"(b)
        : [p] "r"(pairs), [o] "r"(odd)
        : "a8", "memory");
    return res;
}

int32_t vtts_dot_s8s8(const int8_t *a, const int8_t *b, int n) {
    if ((((uintptr_t)a | (uintptr_t)b) & 15) || (n & 15) || n == 0) return dot_scalar(a, b, n);
    return dot_simd(a, b, n >> 4);
}

/* n dots of one weight row against n frames (x, x + stride, ...), with the frame loop in assembly:
 * per frame the ACCX reset, an odd first block, then two blocks per branch-loop iteration, the
 * read-back and the store. */
static void dots_frames(const int8_t *w, const int8_t *x, int stride, int n, int32_t blocks, int32_t *out) {
    asm volatile(
        "movi a11, 0\n\t"
        "1:\n\t"
        "mov a9, %[w]\n\t"
        "mov a10, %[x]\n\t"
        "mov a13, %[k]\n\t"
        "ee.zero.accx\n\t"
        "bbci a13, 0, 3f\n\t"
        "ee.vld.128.ip q0, a9, 16\n\t"
        "ee.vld.128.ip q1, a10, 16\n\t"
        "ee.vmulas.s8.accx q0, q1\n\t"
        "3:\n\t"
        "srli a13, a13, 1\n\t"
        "beqz a13, 4f\n\t"
        "2:\n\t"
        "ee.vld.128.ip q0, a9, 16\n\t"
        "ee.vld.128.ip q1, a10, 16\n\t"
        "ee.vld.128.ip q2, a9, 16\n\t"
        "ee.vld.128.ip q3, a10, 16\n\t"
        "ee.vmulas.s8.accx q0, q1\n\t"
        "addi a13, a13, -1\n\t"
        "ee.vmulas.s8.accx q2, q3\n\t"
        "bnez a13, 2b\n\t"
        "4:\n\t"
        "ee.srs.accx a12, a11, 0\n\t"
        "s32i a12, %[o], 0\n\t"
        "addi %[o], %[o], 4\n\t"
        "add %[x], %[x], %[s]\n\t"
        "addi %[n], %[n], -1\n\t"
        "bnez %[n], 1b\n\t"
        : [x] "+r"(x), [o] "+r"(out), [n] "+r"(n)
        : [w] "r"(w), [k] "r"(blocks), [s] "r"(stride)
        : "a9", "a10", "a11", "a12", "a13", "memory");
}

void vtts_dots_s8s8(const int8_t *w, const int8_t *x, int stride, int n, int len, int32_t *out) {
    if (n <= 0) return;
    if ((((uintptr_t)w | (uintptr_t)x) & 15) || (len & 15) || (stride & 15) || len == 0) {
        for (int t = 0; t < n; t++) out[t] = dot_scalar(w, x + (long)t * stride, len);
        return;
    }
    if (vtts_s3_kernel == 1)
        for (int t = 0; t < n; t++) out[t] = dot_fused(w, x + (long)t * stride, len >> 4);
    else if (vtts_s3_kernel == 2)
        for (int t = 0; t < n; t++) out[t] = dot_simd(w, x + (long)t * stride, len >> 4);
    else
        dots_frames(w, x, stride, n, len >> 4, out);
}
