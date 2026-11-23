/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_port_p4.c -- ESP32-P4 and ESP32-S31 PIE SIMD kernels for the vtts runtime (overrides the weak
 * C ones). Both chips have the same 128-bit PIE vector unit; the firmware builds this file for either.
 *
 * The 16-lane signed 8-bit multiply-accumulate (esp.vmulas.s8.xacc into the 40-bit XACC
 * accumulator) follows the approach of espressif/esp-nn (Apache-2.0,
 * src/fully_connected/esp_nn_fully_connected_s8_riscv_pie.c). A plain branch loop is used
 * instead of the hardware loop, which needs extra padding on P4 silicon before revision 3 (and keeps
 * the S31, whose silicon is preliminary, on the same well-tested code path).
 *
 * ESP32-S31: only core 1 has the PIE; FreeRTOS would move a task that runs a PIE instruction on
 * core 0 to core 1 for good. On core 0 (the two-core worker, vtts_par_freertos.c) the kernels take
 * the plain C path, whose int32 sums are the same. */
#include <stdint.h>

#include "sdkconfig.h"
#include "vtts_port.h"

#if CONFIG_IDF_TARGET_ESP32S31
static inline int no_pie(void) {
    unsigned hart;
    asm volatile("csrr %0, mhartid" : "=r"(hart));
    return hart == 0;
}

/* core 0: plain C, four rows of x against one weight row so each weight byte is loaded once */
static void dots_c(const int8_t *w, const int8_t *x, int stride, int n, int len, int32_t *out) {
    int t = 0;
    for (; t + 4 <= n; t += 4) {
        const int8_t *x0 = x + (long)t * stride, *x1 = x0 + stride, *x2 = x1 + stride, *x3 = x2 + stride;
        int32_t s0 = 0, s1 = 0, s2 = 0, s3 = 0;
        for (int i = 0; i < len; i++) {
            int32_t wi = w[i];
            s0 += wi * x0[i];
            s1 += wi * x1[i];
            s2 += wi * x2[i];
            s3 += wi * x3[i];
        }
        out[t] = s0, out[t + 1] = s1, out[t + 2] = s2, out[t + 3] = s3;
    }
    for (; t < n; t++) {
        const int8_t *xp = x + (long)t * stride;
        int32_t s0 = 0;
        for (int i = 0; i < len; i++) s0 += (int32_t)w[i] * xp[i];
        out[t] = s0;
    }
}
#else
#define no_pie() 0
#endif

static inline void pie_enable(void) {
    asm volatile("esp.movx.r.cfg x29\n\t"
                 "ori x29, x29, 0b11\n\t"
                 "esp.movx.w.cfg x29\n\t" ::: "x29");
}

int32_t vtts_dot_s8s8(const int8_t *a, const int8_t *b, int n) {
    if ((((uintptr_t)a | (uintptr_t)b) & 15) || (n & 15) || n == 0 || no_pie()) {
        int32_t s = 0;
        for (int i = 0; i < n; i++) s += (int32_t)a[i] * (int32_t)b[i];
        return s;
    }
    pie_enable();
    int32_t res;
    int32_t blocks = n >> 4;
    asm volatile(
        "esp.zero.xacc\n\t"
        "mv x30, %[a]\n\t"
        "mv x31, %[b]\n\t"
        "1:\n\t"
        "esp.vld.128.ip q0, x30, 16\n\t"
        "esp.vld.128.ip q1, x31, 16\n\t"
        "esp.vmulas.s8.xacc q0, q1\n\t"
        "addi %[k], %[k], -1\n\t"
        "bnez %[k], 1b\n\t"
        "esp.movx.r.xacc.l %[res]\n\t"
        : [res] "=r"(res), [k] "+r"(blocks)
        : [a] "r"(a), [b] "r"(b)
        : "x30", "x31", "memory");
    return res;
}

/* Dot of w against n rows of x. For an even number of 16-byte blocks the loop is software
 * pipelined: each multiply-accumulate also loads the next weight block (vmulas...ld.ip), so a
 * pair of blocks costs four instructions instead of six plus loop overhead. */
void vtts_dots_s8s8(const int8_t *w, const int8_t *x, int stride, int n, int len, int32_t *out) {
#if CONFIG_IDF_TARGET_ESP32S31
    if (no_pie()) { dots_c(w, x, stride, n, len, out); return; }
#endif
    if ((((uintptr_t)w | (uintptr_t)x) & 15) || (len & 15) || (stride & 15) || len == 0) {
        for (int t = 0; t < n; t++) out[t] = vtts_dot_s8s8(w, x + (long)t * stride, len);
        return;
    }
    pie_enable();
    const int32_t blocks = len >> 4;
    if (blocks & 1) {
        for (int t = 0; t < n; t++) out[t] = vtts_dot_s8s8(w, x + (long)t * stride, len);
        return;
    }
    for (int t = 0; t < n; t++) {
        const int8_t *xp = x + (long)t * stride;
        register int32_t res asm("a5"); /* the XACC move only encodes some registers */
        int32_t k = (blocks >> 1) - 1;
        asm volatile(
            "esp.zero.xacc\n\t"
            "mv x30, %[a]\n\t"
            "mv x31, %[b]\n\t"
            "esp.vld.128.ip q0, x30, 16\n\t"
            "esp.vld.128.ip q1, x31, 16\n\t"
            "beqz %[k], 2f\n\t"
            "1:\n\t"
            "esp.vld.128.ip q3, x31, 16\n\t"
            "esp.vmulas.s8.xacc.ld.ip q2, x30, 16, q0, q1\n\t"
            "esp.vld.128.ip q1, x31, 16\n\t"
            "esp.vmulas.s8.xacc.ld.ip q0, x30, 16, q2, q3\n\t"
            "addi %[k], %[k], -1\n\t"
            "bnez %[k], 1b\n\t"
            "2:\n\t"
            "esp.vld.128.ip q3, x31, 16\n\t"
            "esp.vmulas.s8.xacc.ld.ip q2, x30, 16, q0, q1\n\t"
            "esp.vmulas.s8.xacc q2, q3\n\t"
            "esp.movx.r.xacc.l %[res]\n\t"
            : [res] "=r"(res), [k] "+r"(k)
            : [a] "r"(w), [b] "r"(xp)
            : "x30", "x31", "memory");
        out[t] = res;
    }
}
