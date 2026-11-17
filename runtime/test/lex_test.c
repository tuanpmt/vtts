/* lex_test BLOB EXPECT_TSV: VLEX lookups and letter-to-sound predictions must match Python. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts_lex.h"
#include "vtts_text_en.h"

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: lex_test BLOB EXPECT\n"); return 2; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    rewind(f);
    uint8_t *blob = malloc((size_t)n);
    if (fread(blob, 1, (size_t)n, f) != (size_t)n) return 2;
    fclose(f);
    vtts_lex lx;
    if (vtts_lex_init(&lx, blob, (size_t)n)) { fprintf(stderr, "bad blob\n"); return 1; }
    FILE *e = fopen(argv[2], "r");
    if (!e) return 2;
    char line[4096];
    int cases = 0, bad = 0;
    while (fgets(line, sizeof line, e)) {
        /* fields may be empty: split on tabs by hand */
        char *kind = line, *word = strchr(line, '\t');
        if (!word) continue;
        *word++ = 0;
        char *ids = strchr(word, '\t');
        if (ids) { *ids++ = 0; ids[strcspn(ids, "\n")] = 0; }
        uint8_t got[256];
        int k = kind[0] == 'L' ? vtts_lex_lookup(&lx, word, got, 256)
              : kind[0] == 'P' ? vtts_lex_predict(&lx, word, got, 256) : vtts_en_g2p(&lx, word, got, 256);
        char buf[2048] = "";
        for (int i = 0; i < k; i++) {
            char t[8];
            snprintf(t, sizeof t, i ? " %d" : "%d", got[i]);
            strcat(buf, t);
        }
        cases++;
        if (strcmp(buf, ids ? ids : "") != 0) {
            if (bad++ < 10) printf("MISMATCH %s %s: want [%s] got [%s]\n", kind, word, ids ? ids : "", buf);
        }
    }
    fclose(e);
    printf("%d/%d exact (blob %ld bytes)\n", cases - bad, cases, n);
    free(blob);
    return bad ? 1 : 0;
}
