/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_cli.c -- host tool: read phoneme ids (one utterance per line, space separated) from
 * stdin, write one 16-bit mono WAV per line to OUT_PREFIX<n>.wav.
 * usage: vtts_cli MODEL.vtts OUT_PREFIX [length_scale] */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts.h"

static void write_wav(const char *path, const float *pcm, long n, int sr) {
    FILE *f = fopen(path, "wb");
    if (!f) return;
    uint32_t data = (uint32_t)n * 2, riff = 36 + data, sr32 = (uint32_t)sr, br = sr32 * 2, fmt = 16;
    uint16_t pcm_tag = 1, ch = 1, align = 2, bits = 16;
    fwrite("RIFF", 1, 4, f); fwrite(&riff, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f);
    fwrite(&fmt, 4, 1, f); fwrite(&pcm_tag, 2, 1, f); fwrite(&ch, 2, 1, f); fwrite(&sr32, 4, 1, f);
    fwrite(&br, 4, 1, f); fwrite(&align, 2, 1, f); fwrite(&bits, 2, 1, f);
    fwrite("data", 1, 4, f); fwrite(&data, 4, 1, f);
    for (long i = 0; i < n; i++) {
        float v = pcm[i] * 32767.0f;
        int16_t s = (int16_t)(v > 32767.0f ? 32767 : v < -32768.0f ? -32768 : v);
        fwrite(&s, 2, 1, f);
    }
    fclose(f);
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s model out_prefix [length_scale [expressiveness]]\n", argv[0]); return 2; }
    float ls = argc > 3 ? (float)atof(argv[3]) : 1.0f;
    FILE *mf = fopen(argv[1], "rb");
    if (!mf) return 2;
    fseek(mf, 0, SEEK_END);
    size_t mb = (size_t)ftell(mf);
    fseek(mf, 0, SEEK_SET);
    void *blob = malloc(mb);
    if (fread(blob, 1, mb, mf) != mb) return 2;
    fclose(mf);
    vtts_model m;
    int rc = vtts_init(&m, blob, mb);
    if (rc) { fprintf(stderr, "init failed %d\n", rc); return 1; }
    if (argc > 4) vtts_set_expressiveness(&m, (float)atof(argv[4]));
    char line[65536];
    int k = 0;
    while (fgets(line, sizeof line, stdin)) {
        int32_t ids[4096];
        int n = 0;
        for (char *tok = strtok(line, " \t\n"); tok && n < 4096; tok = strtok(NULL, " \t\n")) ids[n++] = atoi(tok);
        if (n == 0) continue;
        long max_frames = (long)n * m.max_duration;
        size_t ab = vtts_arena_bytes(&m, n, max_frames);
        void *arena = malloc(ab);
        float *pcm = malloc(sizeof(float) * (size_t)max_frames * m.hop);
        long s = vtts_synthesize(&m, ids, n, ls, pcm, max_frames * m.hop, arena, ab);
        if (s < 0) { fprintf(stderr, "synth failed %ld\n", s); return 1; }
        char path[1024];
        snprintf(path, sizeof path, "%s%d.wav", argv[2], k++);
        write_wav(path, pcm, s, m.sample_rate);
        free(arena); free(pcm);
    }
    return 0;
}
