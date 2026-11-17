/* en_norm_test FIXTURE: "text<TAB>expected" lines; vtts_en_normalize must give exactly normalize_en. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts_text_en.h"

static int utf8_to_cp(const char *s, uint32_t *out, int cap) {
    int n = 0;
    const unsigned char *p = (const unsigned char *)s;
    while (*p && n < cap) {
        uint32_t c = *p++;
        int extra = c >= 0xF0 ? 3 : c >= 0xE0 ? 2 : c >= 0xC0 ? 1 : 0;
        if (extra) c &= 0x3F >> extra;
        while (extra-- && *p) c = (c << 6) | (*p++ & 0x3F);
        out[n++] = c;
    }
    return n;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "r");
    if (!f) return 2;
    static char line[65536], out[65536];
    static uint32_t cp[16384], a[65536], b[65536];
    int cases = 0, bad = 0;
    while (fgets(line, sizeof line, f)) {
        char *tab = strchr(line, '\t');
        if (!tab) continue;
        *tab = 0;
        char *want = tab + 1;
        want[strcspn(want, "\n")] = 0;
        int n = utf8_to_cp(line, cp, 16384);
        int r = vtts_en_normalize(cp, n, a, b, 65536, out, (int)sizeof out);
        cases++;
        if (r < 0 || strcmp(out, want) != 0) {
            if (bad++ < 15) printf("MISMATCH %s\n  want: %s\n  got:  %s\n", line, want, r < 0 ? "<error>" : out);
        }
    }
    fclose(f);
    printf("%d/%d exact\n", cases - bad, cases);
    return bad ? 1 : 0;
}
