/* SPDX-License-Identifier: Apache-2.0 */
/* text_test.c -- device front-end must produce exactly the Python ids.
 * usage: text_test text_parity.tsv   (text \t ids;ids...) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts_text.h"

typedef struct { char buf[65536]; size_t n; } out_t;

static int collect(const int32_t *ids, int n, void *user) {
    out_t *o = user;
    if (o->n) o->buf[o->n++] = ';';
    for (int i = 0; i < n; i++) o->n += (size_t)snprintf(o->buf + o->n, sizeof(o->buf) - o->n, i ? " %d" : "%d", ids[i]);
    o->buf[o->n] = 0;
    return 0;
}

static int fuzz(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    unsigned seed = 12345;
    for (int it = 0; it < 3000; it++) {
        int n = (int)((seed = seed * 1103515245u + 12345u) >> 16) % 19999;
        for (int i = 0; i < n; i++) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            /* mix of ASCII, digits, separators, Vietnamese UTF-8 and random high bytes */
            static const char *const parts[] = {"a", "7", ".", ",", "/", ":", "-", " ", "\xc3\xa0", "\xe1\xbb\x87", "%", "h"};
            buf[i] = (r % 5 == 0) ? (char)(r >> 3) : parts[r % 12][0];
        }
        buf[n] = 0;
        int rc = vtts_text_to_ids(buf, &ws, NULL, NULL);
        if (rc < 0) { printf("fuzz: error %d\n", rc); return 1; }
    }
    if (vtts_text_to_ids("", &ws, NULL, NULL) != 0 || vtts_text_to_ids("...", &ws, NULL, NULL) != 0) {
        puts("fuzz: empty input must give 0 chunks");
        return 1;
    }
    puts("fuzz: ok");
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    if (strcmp(argv[1], "--fuzz") == 0) return fuzz();
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    static char line[1 << 16];
    static vtts_text_ws ws;
    static out_t out;
    int total = 0, bad = 0;
    while (fgets(line, sizeof line, f)) {
        char *tab = strchr(line, '\t');
        if (!tab) continue;
        *tab = 0;
        char *want = tab + 1;
        want[strcspn(want, "\n")] = 0;
        out.n = 0; out.buf[0] = 0;
        int rc = vtts_text_to_ids(line, &ws, collect, &out);
        total++;
        if (rc < 0 || strcmp(out.buf, want) != 0) {
            if (bad < 15) printf("MISMATCH: %s\n  want %s\n  got  %s (rc %d)\n", line, want, out.buf, rc);
            bad++;
        }
    }
    printf("%d/%d exact\n", total - bad, total);
    return bad ? 1 : 0;
}
