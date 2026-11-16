/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_par_freertos.c -- vtts_par_run on a dual-core FreeRTOS chip (ESP32-P4, ESP32-S3):
 * the caller runs [0, mid) while a worker pinned to core 1 runs [mid, n). */
#include "vtts_port.h"

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

void vtts_par_enable(int on) { s_par.enabled = on; }

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
