/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_par_freertos.c -- vtts_par_run on a dual-core FreeRTOS chip.
 *
 * ESP32-P4, ESP32-S3: the caller runs [0, mid) while a worker pinned to core 1 runs [mid, n).
 *
 * ESP32-S31: only core 1 has the PIE vector unit, and FreeRTOS moves a task that runs a PIE
 * instruction on core 0 to core 1 for good. The caller (the synthesis task) therefore runs on core 1
 * and the worker on core 0, where the port's int8 kernels take their plain C path (vtts_port_p4.c).
 * The two cores differ in speed (about 8x on the int8 layers, equal on the float passes), so a fixed
 * split does not fit: the caller claims blocks from the front of [0, n) and the worker claims
 * single items from the back until they meet. Every item is computed by one core with the same
 * arithmetic, so results do not depend on the split. */
#include "vtts_port.h"

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include <stdio.h>

static struct {
    SemaphoreHandle_t go, done;
    vtts_par_fn fn;
    void *ctx;
    int lo, hi;
    int ready, enabled;
} s_par = {.enabled = 1};

/* diagnostics (`parstat`): split calls, time on each core, worker items, cores seen */
static struct {
    long calls, single, items_w, items;
    int64_t t_c, t_w, t_wait;
    int core_c, core_w;
} s_st = {.core_c = -1, .core_w = -1};

#if CONFIG_IDF_TARGET_ESP32S31
#define PAR_WORKER_CORE 0
/* below the speaker task (10) on core 0, above the console task (5) */
#define PAR_WORKER_PRIO 9
static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
static int s_front, s_back; /* unclaimed items: [s_front, s_back) */

/* claim up to `want` items from the front (caller) or one from the back (worker); 0 when none left */
static int claim(int front, int want, int *lo) {
    int got = 0;
    portENTER_CRITICAL(&s_mux);
    int left = s_back - s_front;
    if (left > 0) {
        got = front ? (want < left ? want : left) : 1;
        if (front) { *lo = s_front; s_front += got; }
        else { s_back -= got; *lo = s_back; }
    }
    portEXIT_CRITICAL(&s_mux);
    return got;
}

static void par_worker(void *arg) {
    (void)arg;
    for (;;) {
        xSemaphoreTake(s_par.go, portMAX_DELAY);
        int64_t t = esp_timer_get_time();
        int lo, items = 0;
        while (claim(0, 1, &lo)) {
            s_par.fn(lo, lo + 1, s_par.ctx);
            items++;
        }
        s_st.items_w += items;
        s_st.t_w += esp_timer_get_time() - t;
        s_st.core_w = xPortGetCoreID();
        xSemaphoreGive(s_par.done);
    }
}

static void par_split(vtts_par_fn fn, int n, void *ctx) {
    s_par.fn = fn;
    s_par.ctx = ctx;
    s_front = 0;
    s_back = n;
    xSemaphoreGive(s_par.go);
    int64_t t0 = esp_timer_get_time();
    int lo, got, block = n / 16 > 1 ? n / 16 : 1;
    while ((got = claim(1, block, &lo))) fn(lo, lo + got, ctx);
    int64_t t1 = esp_timer_get_time();
    xSemaphoreTake(s_par.done, portMAX_DELAY);
    s_st.t_c += t1 - t0;
    s_st.t_wait += esp_timer_get_time() - t1;
}
#else
#define PAR_WORKER_CORE 1
#define PAR_WORKER_PRIO (configMAX_PRIORITIES - 2)

static void par_worker(void *arg) {
    (void)arg;
    for (;;) {
        xSemaphoreTake(s_par.go, portMAX_DELAY);
        int64_t t = esp_timer_get_time();
        s_par.fn(s_par.lo, s_par.hi, s_par.ctx);
        s_st.items_w += s_par.hi - s_par.lo;
        s_st.t_w += esp_timer_get_time() - t;
        s_st.core_w = xPortGetCoreID();
        xSemaphoreGive(s_par.done);
    }
}

static void par_split(vtts_par_fn fn, int n, void *ctx) {
    int mid = n / 2;
    s_par.fn = fn;
    s_par.ctx = ctx;
    s_par.lo = mid;
    s_par.hi = n;
    xSemaphoreGive(s_par.go);
    int64_t t0 = esp_timer_get_time();
    fn(0, mid, ctx);
    int64_t t1 = esp_timer_get_time();
    xSemaphoreTake(s_par.done, portMAX_DELAY);
    s_st.t_c += t1 - t0;
    s_st.t_wait += esp_timer_get_time() - t1;
}
#endif

void vtts_par_enable(int on) { s_par.enabled = on; }

/* ESP32-S31: whether the int8 layers also use core 0 (plain C kernels there) */
static int s_simd_split = 1;
void vtts_par_simd_enable(int on) { s_simd_split = on; }

#if CONFIG_IDF_TARGET_ESP32S31
void vtts_par_run_simd(vtts_par_fn fn, int n, void *ctx) {
    if (s_simd_split) vtts_par_run(fn, n, ctx);
    else fn(0, n, ctx);
}
#endif

void vtts_par_run(vtts_par_fn fn, int n, void *ctx) {
    if (!s_par.ready) {
        s_par.go = xSemaphoreCreateBinary();
        s_par.done = xSemaphoreCreateBinary();
        xTaskCreatePinnedToCore(par_worker, "vtts_par", 4096, NULL, PAR_WORKER_PRIO, NULL, PAR_WORKER_CORE);
        s_par.ready = 1;
    }
    if (!s_par.enabled || n < 16) {
        s_st.single++;
        fn(0, n, ctx);
        return;
    }
    par_split(fn, n, ctx);
    s_st.calls++;
    s_st.items += n;
    s_st.core_c = xPortGetCoreID();
}

void vtts_par_stats(int reset) {
    printf("par: %ld split calls (%ld items, %.0f%% on the worker), %ld single; caller core %d %.1f ms, worker core %d "
           "%.1f ms, caller waited %.1f ms\n",
           s_st.calls, s_st.items, s_st.items ? 100.0 * s_st.items_w / s_st.items : 0.0, s_st.single, s_st.core_c,
           s_st.t_c / 1e3, s_st.core_w, s_st.t_w / 1e3, s_st.t_wait / 1e3);
    if (reset) {
        s_st.calls = s_st.single = s_st.items = s_st.items_w = 0;
        s_st.t_c = s_st.t_w = s_st.t_wait = 0;
    }
}
