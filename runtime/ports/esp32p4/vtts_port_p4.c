/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_port_p4.c -- ESP32-P4 PIE SIMD kernels for the vtts runtime (overrides the weak C ones).
 *
 * The 16-lane signed 8-bit multiply-accumulate (esp.vmulas.s8.xacc into the 40-bit XACC
 * accumulator) follows the approach of espressif/esp-nn (Apache-2.0,
 * src/fully_connected/esp_nn_fully_connected_s8_riscv_pie.c). A plain branch loop is used
 * instead of the hardware loop, which needs extra padding on P4 silicon before revision 3. */
#include <stdint.h>

#include "vtts_port.h"

static inline void pie_enable(void) {
    asm volatile("esp.movx.r.cfg x29\n\t"
                 "ori x29, x29, 0b11\n\t"
                 "esp.movx.w.cfg x29\n\t" ::: "x29");
}

int32_t vtts_dot_s8s8(const int8_t *a, const int8_t *b, int n) {
    if ((((uintptr_t)a | (uintptr_t)b) & 15) || (n & 15) || n == 0) {
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

/* ---------------- two-core split for vtts_par_run ---------------- */
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

static struct {
    SemaphoreHandle_t go, done;
    vtts_par_fn fn;
    void *ctx;
    int lo, hi;
    int ready, enabled;
} s_par = {.enabled = 1};

static void par_worker(void *arg) {
    (void)arg;
    for (;;) {
        xSemaphoreTake(s_par.go, portMAX_DELAY);
        s_par.fn(s_par.lo, s_par.hi, s_par.ctx);
        xSemaphoreGive(s_par.done);
    }
}

void vtts_p4_par_enable(int on) { s_par.enabled = on; }

void vtts_par_run(vtts_par_fn fn, int n, void *ctx) {
    if (!s_par.ready) {
        s_par.go = xSemaphoreCreateBinary();
        s_par.done = xSemaphoreCreateBinary();
        xTaskCreatePinnedToCore(par_worker, "vtts_par", 4096, NULL, configMAX_PRIORITIES - 2, NULL, 1);
        s_par.ready = 1;
    }
    if (!s_par.enabled || n < 16) {
        fn(0, n, ctx);
        return;
    }
    int mid = n / 2;
    s_par.fn = fn;
    s_par.ctx = ctx;
    s_par.lo = mid;
    s_par.hi = n;
    xSemaphoreGive(s_par.go);
    fn(0, mid, ctx);
    xSemaphoreTake(s_par.done, portMAX_DELAY);
}

/* Dot of w against n rows of x. For an even number of 16-byte blocks the loop is software
 * pipelined: each multiply-accumulate also loads the next weight block (vmulas...ld.ip), so a
 * pair of blocks costs four instructions instead of six plus loop overhead. */
void vtts_dots_s8s8(const int8_t *w, const int8_t *x, int stride, int n, int len, int32_t *out) {
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
