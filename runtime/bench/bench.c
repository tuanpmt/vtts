/* SPDX-License-Identifier: Apache-2.0 */
/* bench.c -- host speed of the reference kernels: RTF and effective MMAC/s.
 * usage: bench MODEL.vtts N_TOKENS FRAMES_PER_TOKEN MMAC_PER_SECOND_OF_AUDIO */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "vtts.h"

static int sink(const float *p, long n, void *u) { (void)p; (void)n; (void)u; return 0; }

int main(int argc, char **argv) {
    if (argc < 5) return 2;
    FILE *f = fopen(argv[1], "rb");
    fseek(f, 0, SEEK_END); size_t n = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
    void *blob = malloc(n);
    if (fread(blob, 1, n, f) != n) return 2;
    fclose(f);
    vtts_model m;
    if (vtts_init(&m, blob, n)) return 1;
    int nt = atoi(argv[2]);
    double mmac = atof(argv[4]);
    int32_t *ids = malloc(sizeof(int32_t) * nt);
    for (int i = 0; i < nt; i++) ids[i] = 4 + (i * 7) % 60;
    float ls = 1.0f;
    size_t ab = vtts_stream_arena_bytes(&m, nt, 32);
    void *arena = malloc(ab);
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    long s = vtts_synthesize_stream(&m, ids, nt, ls, 32, sink, NULL, arena, ab);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double sec = (t1.tv_sec - t0.tv_sec) + 1e-9 * (t1.tv_nsec - t0.tv_nsec);
    double audio = (double)s / m.sample_rate;
    printf("audio %.2fs compute %.3fs RTF %.3f eff %.0f MMAC/s arena %zu B\n", audio, sec, sec / audio,
           mmac / (sec / audio), ab);
    return 0;
}
