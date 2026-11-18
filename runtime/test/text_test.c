/* SPDX-License-Identifier: Apache-2.0 */
/* text_test.c -- device front-end must produce exactly the Python ids.
 * usage: text_test text_parity.tsv                          (text \t ids;ids...; phoneme set v1)
 *        text_test --lex LEX [--zh ZLEX] text_parity_v2.tsv (mode \t text \t ids...; mode vi|en|auto|zh|ko|hi|ja)
 *        text_test --fuzz [--lex LEX] [--zh ZLEX] [--ja JLEX] (v1; v2, ko and hi modes with --lex; zh mode with --zh;
 *                                                       ja mode with --ja)
 *        text_test --ja JLEX --nfkc ja_nfkc.tsv             (NFKC of the JLEX data against unicodedata)
 *        text_test --ja JLEX --bench [words.tsv]           (reading lookups and ja-mode throughput) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "vtts_text.h"
#include "vtts_text_ja.h"

typedef struct { char buf[65536]; size_t n; } out_t;

static int collect(const int32_t *ids, int n, void *user) {
    out_t *o = user;
    if (o->n) o->buf[o->n++] = ';';
    for (int i = 0; i < n; i++) o->n += (size_t)snprintf(o->buf + o->n, sizeof(o->buf) - o->n, i ? " %d" : "%d", ids[i]);
    o->buf[o->n] = 0;
    return 0;
}

/* fuzz: every chunk holds BOS ... EOS, at most VTTS_TEXT_MAX_IDS ids, all inside the token set */
static int check_ids(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 171) *bad = 1;
    return 0;
}

static vtts_lex s_lex;
static vtts_zlex s_zh;
static vtts_jlex s_ja;
static int s_has_lex, s_has_zh, s_has_ja;

static int run(const char *text, int mode, vtts_text_ws *ws, vtts_ids_cb cb, void *user) {
    vtts_text_opts o = {(vtts_lang)mode, s_has_lex ? &s_lex : NULL, s_has_zh ? &s_zh : NULL, s_has_ja ? &s_ja : NULL};
    return vtts_text_to_ids_ex(text, ws, &o, cb, user);
}

static uint8_t *load_file(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    rewind(f);
    uint8_t *b = n > 0 ? malloc((size_t)n) : NULL;
    if (!b || fread(b, 1, (size_t)n, f) != (size_t)n) { fclose(f); free(b); return NULL; }
    fclose(f);
    *size = (size_t)n;
    return b;
}

static int load_lex(const char *path) {
    size_t n;
    uint8_t *b = load_file(path, &n);
    s_has_lex = b && vtts_lex_init(&s_lex, b, n) == 0;
    return s_has_lex ? 0 : -1;
}

static int load_zh(const char *path) {
    size_t n;
    uint8_t *b = load_file(path, &n);
    s_has_zh = b && vtts_zlex_init(&s_zh, b, n) == 0;
    return s_has_zh ? 0 : -1;
}

static int load_ja(const char *path) {
    size_t n;
    uint8_t *b = load_file(path, &n);
    s_has_ja = b && vtts_jlex_init(&s_ja, b, n) == 0;
    return s_has_ja ? 0 : -1;
}

/* lines "in<TAB>out", each a space-separated list of hex code points: NFKC(in) == out */
static int nfkc_test(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { printf("cannot open %s\n", path); return 2; }
    static char line[1 << 16];
    static uint32_t in[8192], want[8192], got[8192 * 4];
    int total = 0, bad = 0;
    while (fgets(line, sizeof line, f)) {
        char *tab = strchr(line, '\t');
        if (!tab) continue;
        *tab = 0;
        int ni = 0, nw = 0;
        for (char *p = line; *p && ni < 8192;) {
            char *e;
            unsigned long v = strtoul(p, &e, 16);
            if (e == p) break;
            in[ni++] = (uint32_t)v;
            p = e;
        }
        for (char *p = tab + 1; *p && nw < 8192;) {
            char *e;
            unsigned long v = strtoul(p, &e, 16);
            if (e == p) break;
            want[nw++] = (uint32_t)v;
            p = e;
        }
        int ng = vtts_jlex_nfkc(&s_ja, in, ni, got, 8192 * 4);
        total++;
        if (ng != nw || memcmp(got, want, sizeof *got * (size_t)nw) != 0) {
            if (bad < 10) {
                printf("NFKC MISMATCH:");
                for (int i = 0; i < ni; i++) printf(" %04X", in[i]);
                printf("\n  want");
                for (int i = 0; i < nw; i++) printf(" %04X", want[i]);
                printf("\n  got ");
                for (int i = 0; i < ng; i++) printf(" %04X", got[i]);
                printf("\n");
            }
            bad++;
        }
    }
    fclose(f);
    printf("nfkc: %d/%d exact\n", total - bad, total);
    return bad ? 1 : 0;
}

static double now_s(void) { return (double)clock() / CLOCKS_PER_SEC; }

static const char *const JA_SAMPLES[] = {
    "リビングの電気を消しました。", "空気清浄機は自動モードで運転しています。", "裏口の鍵が開いています。閉めましょうか？",
    "明日の東京は晴れのち曇り、最高気温は18℃の予想です。", "会議は2026年11月18日午前9:30から3時間の予定です。",
    "Wi-Fiの設定を開いて、パスワードを入力してください。", "この商品は1,280円で、税込みだと1,408円になります。",
    "日本人の友達と一緒に京都の寺を見に行きました。", "子供たちは公園で元気に遊んでいます。",
    "iPhoneのBluetoothをオンにしてからESP32-P4に接続します。",
};

static int count_cb(const int32_t *ids, int n, void *user) {
    (void)ids;
    *(long *)user += n;
    return 0;
}

/* lookups of every words.tsv key (hits) and of every key plus one more character (mostly misses),
 * then vtts_text_to_ids_ex in ja mode over sample sentences */
static int bench(const char *words) {
    static vtts_text_ws ws;
    if (words) {
        FILE *f = fopen(words, "rb");
        if (!f) { printf("cannot open %s\n", words); return 2; }
        static char keys[1 << 21];
        static int koff[70000], klen[70000];
        int nk = 0, used = 0;
        char line[512];
        while (fgets(line, sizeof line, f) && nk < 70000) {
            if (line[0] == '#') continue;
            char *tab = strchr(line, '\t');
            if (!tab) continue;
            int l = (int)(tab - line);
            if (used + l + 3 > (int)sizeof keys) break;
            memcpy(keys + used, line, (size_t)l);
            memcpy(keys + used + l, "\xe3\x81\xae", 3); /* + の for the miss lookups */
            koff[nk] = used;
            klen[nk++] = l;
            used += l + 3;
        }
        fclose(f);
        long hits = 0, misses = 0;
        const int reps = 20;
        double t0 = now_s();
        for (int r = 0; r < reps; r++)
            for (int k = 0; k < nk; k++) {
                const uint8_t *rd;
                hits += vtts_jlex_find(&s_ja, VTTS_JLEX_WORDS, (const uint8_t *)keys + koff[k], klen[k], &rd) >= 0;
            }
        double t1 = now_s();
        for (int r = 0; r < reps; r++)
            for (int k = 0; k < nk; k++) {
                const uint8_t *rd;
                misses += vtts_jlex_find(&s_ja, VTTS_JLEX_WORDS, (const uint8_t *)keys + koff[k], klen[k] + 3, &rd) < 0;
            }
        double t2 = now_s();
        printf("lookup: %d keys, %.0f ns per hit, %.0f ns per lookup of key + の (%ld of %ld absent)\n", nk,
               1e9 * (t1 - t0) / ((double)nk * reps), 1e9 * (t2 - t1) / ((double)nk * reps), misses, (long)nk * reps);
        if (hits != (long)nk * reps) { printf("lookup: only %ld of %ld keys found\n", hits, (long)nk * reps); return 1; }
    }
    const int ns = (int)(sizeof JA_SAMPLES / sizeof *JA_SAMPLES);
    long ids = 0, bytes = 0;
    const int reps = 300;
    double t0 = now_s();
    for (int r = 0; r < reps; r++)
        for (int k = 0; k < ns; k++) {
            run(JA_SAMPLES[k], VTTS_LANG_JA, &ws, count_cb, &ids);
            if (!r) bytes += (long)strlen(JA_SAMPLES[k]);
        }
    double t1 = now_s();
    printf("ja text_to_ids: %.1f us per sentence (%d sentences, %ld UTF-8 bytes, %ld ids per pass)\n",
           1e6 * (t1 - t0) / ((double)reps * ns), ns, bytes, ids / reps);
    return 0;
}

/* mixed Han (common characters, digits-heavy), ASCII, numbers, CJK and ASCII punctuation, symbols */
static int fuzz_zh(vtts_text_ws *ws) {
    static char buf[20000];
    static const char *const parts[] = {
        "中", "国", "银行", "行", "长", "了", "的", "一", "不", "重", "年", "月", "日", "点", "，", "。", "！", "？",
        "；", "：", "、", "“", "”", "（", "）", "《", "》", "…", "—", "·", "　", "％", "￥", "℃", "°", "１", "Ａ",
        "a", "Z", "e", "S", "P", "x", "'", "-", "~", "/", ".", ",", ":", "%", "$", "€", "£", "¥", "+", "&", "@",
        "0", "1", "2", "3", "5", "9", " ", " ", "\t", "ESP32", "Wi-Fi", "iPhone", "2026-11-18", "9:30", "12:00:05",
        "1,234", "3.14", "-5", "99%", "$5", "2024年", "3~5", "10:2", "\xe4\xb8", "\xff", "\x80", "é", "ạ", "한"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4242;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; } /* random byte */
            const char *p = parts[r % (unsigned)np];
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_ZH, ws, check_ids, &bad);
        if (rc < 0 || bad) { printf("fuzz zh: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_ZH, ws, NULL, NULL) != 0 || run("。。，", VTTS_LANG_ZH, ws, NULL, NULL) != 0) {
        puts("fuzz zh: empty input must give 0 chunks");
        return 1;
    }
    return 0;
}

/* Hangul words (rule-heavy syllables, exception entries), jamo, ASCII, numbers with counters, dates,
 * times, units, money, CJK and ASCII punctuation, symbols and random bytes; chunks must stay inside
 * the ko-en set (153 ids, no Vietnamese ids) */
static int check_ko(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 153 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_ko(vtts_text_ws *ws) {
    static char buf[20000];
    static const char *const parts[] = {
        "한국어", "학교", "국물", "같이", "좋다", "앉아", "닭", "읽고", "넓다", "신라", "희망", "가져", "물고기", "김밥",
        "솜이불", "밟다", "값을", "흙", "의", "를", "에서", "은", "ㅋ", "ㆍ", "개", "명", "번째", "시", "분", "월", "년",
        "일", "살", "개월", "，", "。", "！", "？", "；", "：", "、", "“", "”", "（", "）", "《", "》", "…", "—", "·",
        "　", "％", "￦", "₩", "℃", "°", "°C", "１", "Ａ", "a", "Z", "e", "S", "P", "x", "'", "-", "~", "/", ".", ",",
        ":", "%", "$", "€", "£", "¥", "+", "&", "@", "0", "1", "2", "3", "5", "9", " ", " ", "\t", "ESP32", "Wi-Fi",
        "iPhone", "2026-11-18", "2026. 6. 10.", "9:30", "12:00:05", "010-1234-5678", "0123", "1,234", "3.14", "-5",
        "99%", "$5", "5km", "16GB", "3~5", "10:2", "\xea\xb0", "\xff", "\x80", "é", "中", "か", "ạ"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4243;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words: split into syllables, item and pool limits */
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; } /* random byte */
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_KO, ws, check_ko, &bad);
        if (rc < 0 || bad) { printf("fuzz ko: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_KO, ws, NULL, NULL) != 0 || run("。。，", VTTS_LANG_KO, ws, NULL, NULL) != 0) {
        puts("fuzz ko: empty input must give 0 chunks");
        return 1;
    }
    return 0;
}

/* Devanagari words (conjuncts, nukta letters decomposed and precomposed, anusvara, chandrabindu,
 * visarga, exception entries), stray signs, Devanagari digits and dandas, ASCII, numbers, dates, times,
 * money, units, Latin-1 letters and random bytes; chunks must stay inside the hi-en set (157 ids, no
 * Vietnamese ids) */
static int check_hi(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 157 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_hi(vtts_text_ws *ws) {
    static char buf[20000];
    static const char *const parts[] = {
        "हिंदी", "नमस्ते", "कमला", "समझना", "ठंडा", "दांत", "संसार", "में", "हूँ", "ज्ञान", "क्षमा", "मित्र", "सत्य",
        "उदाहरण", "असफल", "ज़", "क़", "\xe0\xa5\x98", "ड़", "ढ़", "ऋषि", "कृष्ण", "दुःख", "ॐ", "ऑफ़िस", "ॅ", "ा", "ि",
        "्", "़", "ं", "ँ", "ः", "ऽ", "\xe2\x80\x8d", "\xe2\x80\x8c", "।", "॥", "॰", "०", "१", "५", "९", "डॉ.",
        "कि.मी.", "रु.", "₹", "Rs", "Rs.", "INR", "$", "€", "£", "सन्", "सन", "ईस्वी", "बजे", "हज़ार", "लाख", "करोड़",
        "वाँ", "वीं", "वें", "km", "GB", "°C", "℃", "°", "%", "+", "&", "@", "×", "=", "/", "-", "–", "—", "…", ",",
        ".", "?", "!", ";", ":", "'", "\"", "(", ")", "“", "”", "0", "1", "2", "5", "9", " ", " ", "\t", "ESP32",
        "Wi-Fi", "iPhone", "2026-11-18", "15/08/1947", "7:30", "12:00:05", "+91 98765 43210", "1,25,000",
        "3.14", "-5", "99%", "10-20", "a", "Z", "é", "Ǆ", "ß", "Ω", "中", "한", "ạ", "\xe0\xa4", "\xff", "\x80"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4244;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words: token and item limits */
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; } /* random byte */
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_HI, ws, check_hi, &bad);
        if (rc < 0 || bad) { printf("fuzz hi: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_HI, ws, NULL, NULL) != 0 || run("।।, ॥", VTTS_LANG_HI, ws, NULL, NULL) != 0) {
        puts("fuzz hi: empty input must give 0 chunks");
        return 1;
    }
    return 0;
}

/* kanji (table words, context keys, 々), hiragana, katakana (long runs, ー, small kana), half-width
 * katakana, iteration marks, numbers with counters, dates, times, units, money, big units, ASCII,
 * NFKC-heavy symbols, CJK and ASCII punctuation and random bytes; chunks must stay inside the ja-en
 * set (144 ids, no Vietnamese ids) */
static int check_ja(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 144 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_ja(vtts_text_ws *ws) {
    static char buf[20000];
    static const char *const parts[] = {
        "日本", "人", "東京", "後", "川", "今日", "一日", "々", "〆", "時々", "人々", "の", "は", "を", "に", "が", "です",
        "ました", "きゃ", "ゃ", "っ", "ん", "ー", "ゝ", "ゞ", "ヽ", "ヾ", "ア", "メ", "リ", "カ", "コンピューター", "ヴァ",
        "ティ", "ウィ", "ファ", "ヶ", "ヷ", "ｶﾞ", "ｱｲｳ", "ﾊﾟ", "か\xe3\x82\x99", "゛", "本", "匹", "分", "分の", "個", "階",
        "日", "日間", "月", "年", "円", "時", "時間", "つ", "歳", "か月", "ヶ国", "万", "億", "兆", "，", "。", "！", "？",
        "；", "：", "、", "「", "」", "（", "）", "『", "』", "【", "】", "…", "‥", "—", "―", "・", "　", "％", "￥", "℃",
        "°", "°C", "①", "㍻", "㌔", "ⅷ", "ﬁ", "１", "Ａ", "a", "Z", "e", "S", "P", "x", "'", "-", "~", "〜", "～", "/", ".",
        ",", ":", "%", "$", "€", "£", "¥", "+", "&", "@", "=", "×", "\xe2\x81\xa0", "0", "1", "2", "3", "5", "9", "٣",
        " ", " ", "\t", "ESP32", "Wi-Fi", "iPhone", "2026-11-18", "9:30", "12:00:05", "03-1234-5678", "1,234", "3.14",
        "-5", "99%", "$5", "5km", "16GB", "3~5", "1.5万", "3億2000万", "\xe4\xb8", "\xff", "\x80", "é", "中", "한", "ạ"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4244;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long runs: item and pool limits */
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; } /* random byte */
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_JA, ws, check_ja, &bad);
        if (rc < 0 || bad) { printf("fuzz ja: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_JA, ws, NULL, NULL) != 0 || run("。。、", VTTS_LANG_JA, ws, NULL, NULL) != 0) {
        puts("fuzz ja: empty input must give 0 chunks");
        return 1;
    }
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
        if (s_has_lex) {
            for (int m = VTTS_LANG_VI; m <= (s_has_zh ? VTTS_LANG_ZH : VTTS_LANG_AUTO); m++) {
                rc = run(buf, m, &ws, NULL, NULL);
                if (rc < 0) { printf("fuzz v2: error %d\n", rc); return 1; }
            }
            rc = run(buf, VTTS_LANG_KO, &ws, NULL, NULL);
            if (rc < 0) { printf("fuzz ko: error %d\n", rc); return 1; }
            rc = run(buf, VTTS_LANG_HI, &ws, NULL, NULL);
            if (rc < 0) { printf("fuzz hi: error %d\n", rc); return 1; }
            rc = run(buf, VTTS_LANG_JA, &ws, NULL, NULL);
            if (rc < 0) { printf("fuzz ja: error %d\n", rc); return 1; }
        }
    }
    if (vtts_text_to_ids("", &ws, NULL, NULL) != 0 || vtts_text_to_ids("...", &ws, NULL, NULL) != 0) {
        puts("fuzz: empty input must give 0 chunks");
        return 1;
    }
    if (s_has_zh && fuzz_zh(&ws)) return 1;
    if (s_has_lex && fuzz_ko(&ws)) return 1;
    if (s_has_lex && fuzz_hi(&ws)) return 1;
    if (s_has_ja && fuzz_ja(&ws)) return 1;
    printf("fuzz: ok%s%s%s\n", s_has_lex ? " (with ko) (with hi)" : "", s_has_zh ? " (with zh)" : "",
           s_has_ja ? " (with ja)" : "");
    return 0;
}

static int mode_of(const char *m) {
    if (strcmp(m, "en") == 0) return VTTS_LANG_EN;
    if (strcmp(m, "auto") == 0) return VTTS_LANG_AUTO;
    if (strcmp(m, "zh") == 0) return VTTS_LANG_ZH;
    if (strcmp(m, "ko") == 0) return VTTS_LANG_KO;
    if (strcmp(m, "hi") == 0) return VTTS_LANG_HI;
    if (strcmp(m, "ja") == 0) return VTTS_LANG_JA;
    return VTTS_LANG_VI;
}

int main(int argc, char **argv) {
    const char *file = NULL, *nfkc = NULL;
    int do_fuzz = 0, do_bench = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fuzz") == 0) do_fuzz = 1;
        else if (strcmp(argv[i], "--lex") == 0 && i + 1 < argc) {
            if (load_lex(argv[++i])) { puts("bad lexicon"); return 2; }
        } else if (strcmp(argv[i], "--zh") == 0 && i + 1 < argc) {
            if (load_zh(argv[++i])) { puts("bad zh blob"); return 2; }
        } else if (strcmp(argv[i], "--ja") == 0 && i + 1 < argc) {
            if (load_ja(argv[++i])) { puts("bad ja blob"); return 2; }
        } else if (strcmp(argv[i], "--nfkc") == 0 && i + 1 < argc) nfkc = argv[++i];
        else if (strcmp(argv[i], "--bench") == 0) do_bench = 1;
        else file = argv[i];
    }
    if (nfkc) return s_has_ja ? nfkc_test(nfkc) : 2;
    if (do_bench) return s_has_ja ? bench(file) : 2;
    if (do_fuzz) return fuzz();
    if (!file) return 2;
    FILE *f = fopen(file, "rb");
    if (!f) return 2;
    static char line[1 << 16];
    static vtts_text_ws ws;
    static out_t out;
    int total = 0, bad = 0;
    while (fgets(line, sizeof line, f)) {
        char *tab = strchr(line, '\t');
        if (!tab) continue;
        *tab = 0;
        char *text = line, *want = tab + 1;
        int mode = VTTS_LANG_V1;
        if (s_has_lex) { /* v2 fixture: mode \t text \t ids */
            mode = mode_of(line);
            text = want;
            char *t2 = strchr(text, '\t');
            if (!t2) continue;
            *t2 = 0;
            want = t2 + 1;
        }
        want[strcspn(want, "\n")] = 0;
        out.n = 0; out.buf[0] = 0;
        int rc = run(text, mode, &ws, collect, &out);
        total++;
        if (rc < 0 || strcmp(out.buf, want) != 0) {
            if (bad < 15) printf("MISMATCH [%d]: %s\n  want %s\n  got  %s (rc %d)\n", mode, text, want, out.buf, rc);
            bad++;
        }
    }
    fclose(f);
    printf("%d/%d exact\n", total - bad, total);
    return bad ? 1 : 0;
}
