/* SPDX-License-Identifier: Apache-2.0 */
/* text_test.c -- device front-end must produce exactly the Python ids.
 * usage: text_test text_parity.tsv                          (text \t ids;ids...; phoneme set v1)
 *        text_test --lex LEX [--zh ZLEX] text_parity_v2.tsv (mode \t text \t ids...; mode vi|en|auto|zh|ko|hi|ja|es|id|pt|th|fr|de|it|tr|ru|pl|ar|fi|el)
 *        text_test --fuzz [--lex LEX] [--zh ZLEX] [--ja JLEX] (v1; v2, ko, hi, es, id and pt modes with --lex; zh mode
 *                                                       with --zh; ja mode with --ja)
 *        text_test --fuzz-lt [--lex LEX]                    (es, id and pt modes)
 *        text_test --fuzz-th [--lex LEX]                    (th mode)
 *        text_test --fuzz-ar [--lex LEX]                    (ar mode)
 *        text_test --fuzz-fr [--lex LEX]                    (fr mode)
 *        text_test --fuzz-de [--lex LEX]                    (de mode)
 *        text_test --fuzz-ms [--lex LEX]                    (ms mode)
 *        text_test --fuzz-tl [--lex LEX]                    (tl mode)
 *        text_test --fuzz-sw [--lex LEX]                    (sw mode)
 *        text_test --fuzz-it-tr [--lex LEX]                 (it and tr modes, those compiled in)
 *        text_test --fuzz-ru [--lex LEX] [--ru RLEX]        (ru mode; --ru also loads the stress tables for a fixture)
 *        text_test --fuzz-pl [--lex LEX]                    (pl mode)
 *        text_test --fuzz-lo [--lex LEX]                    (lo mode)
 *        text_test --fuzz-da [--lex LEX]                    (da mode)
 *        text_test --fuzz-km [--lex LEX]                    (km mode)
 *        text_test --fuzz-my [--lex LEX]                    (my mode)
 *        text_test --ja JLEX --nfkc ja_nfkc.tsv             (NFKC of the JLEX data against unicodedata)
 *        text_test --ja JLEX --bench [words.tsv]           (reading lookups and ja-mode throughput) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "vtts_text.h"
#include "vtts_text_ja.h"
#include "vtts_text_tl.h" /* VTTS_ENABLE_TL */

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
static vtts_rlex s_ru;
static int s_has_lex, s_has_zh, s_has_ja, s_has_ru;

static int run(const char *text, int mode, vtts_text_ws *ws, vtts_ids_cb cb, void *user) {
    vtts_text_opts o = {(vtts_lang)mode, s_has_lex ? &s_lex : NULL, s_has_zh ? &s_zh : NULL, s_has_ja ? &s_ja : NULL,
                        s_has_ru ? &s_ru : NULL};
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

static int load_ru(const char *path) {
    size_t n;
    uint8_t *b = load_file(path, &n);
    s_has_ru = b && vtts_rlex_init(&s_ru, b, n) == 0;
    return s_has_ru ? 0 : -1;
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

/* Thai words (clusters, preposed vowels, tone marks, ์, ฤ, ๆ, ฯ, abbreviations), Thai digits,
 * ASCII, numbers, dates, times, units, money, Latin words, punctuation and random bytes, runs
 * without spaces longer than VTTS_TH_MAX_RUN; chunks must stay inside the th-en set (162 ids, no
 * Vietnamese ids) */
static int check_th(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 162 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_th(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "ภาษาไทย", "สวัสดี", "ครับ", "ค่ะ", "กรุงเทพฯ", "ฯลฯ", "ๆ", "ต่างๆ", "เด็กๆ", "จันทร์", "ศาสตร์", "รัฐบาล", "พฤษภาคม",
        "ฤดู", "ฦๅ", "เสมอ", "แสดง", "สนุก", "ขนม", "อร่อย", "ปฏิบัติการ", "บุตร", "เมตร", "ทราย", "จริง", "ได้รับ", "น้ำ",
        "พ.ศ.", "ค.ศ.", "จ.", "ดร.", "ม.ค.", "น.", "์", "ั", "ิ", "ุ", "่", "้", "๊", "๋", "ะ", "า", "ำ", "เ", "แ", "โ",
        "ใ", "ไ", "ก", "ร", "ห", "ฺ", "๎", "ๅ", "฿", "๐", "๕", "๙", "，", "。", "！", "？", "“", "”", "（", "）", "…",
        "—", "–", "·", "％", "１", "Ａ", "a", "Z", "e", "S", "P", "x", "'", "-", "/", ".", ",", ":", "%", "$", "€", "£",
        "¥", "+", "=", "&", "@", "×", "0", "1", "2", "3", "5", "9", " ", " ", "\t", "ESP32", "Wi-Fi", "iPhone",
        "19/11/2569", "2026-11-19", "14:30", "14.30 น.", "081-234-5678", "+66 81 234 5678", "0812345678", "1,234",
        "3.14", "-5", "99%", "฿500", "$5", "5km", "16GB", "30°C", "10-20", "12345678", "\xe0\xb8", "\xff", "\x80",
        "é", "中", "한", "ạ"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4244;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 5 == 0; /* long Thai runs: segmentation and the run limit */
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
        int rc = run(buf, VTTS_LANG_TH, &ws, check_th, &bad);
        if (rc < 0 || bad) { printf("fuzz th: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_TH, &ws, NULL, NULL) != 0 || run("。。，", VTTS_LANG_TH, &ws, NULL, NULL) != 0) {
        puts("fuzz th: empty input must give 0 chunks");
        return 1;
    }
    puts("fuzz th: ok");
    return 0;
}

/* ru mode: chunks inside the ru-en set (154 ids, no Vietnamese ids) */
static int check_ru(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 154 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_ru(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "Москва", "привет", "ещё", "еще", "её", "ёлка", "Ёж", "сделать", "вокзал", "здравствуйте", "солнце", "чувство",
        "счастье", "учиться", "его", "нового", "сегодня", "что", "конечно", "объём", "семья", "ь", "ъ", "й", "е\xcc\x88",
        "и\xcc\x86", "\xcc\x81", "в", "к", "с", "В", "К", "С", "т. е.", "т.е.", "и т. д.", "и т. п.", "г.", "гг.", "ул.",
        "руб.", "р.", "млн", "млрд", "тыс.", "км", "кг", "°C", "°", "%", "₽", "$", "€", "₴", "XX", "XXI", "IV", "век",
        "веке", "в.", "вв.", "Пётр", "I", "II", "C", "L", "года", "году", "год", "г", "мая", "марта", "1-й", "3-го",
        "-м", "-х", "-е", "-летие", "-этажный", "СССР", "НАТО", "МГУ", "ПК", "ESP32", "Wi-Fi", "iPhone", "GB", "km",
        "USD", "15.03.2026", "2026-03-15", "14:30", "9:05:07", "+7 (495) 123-45-67", "8 800 555 35 35", "123-45-67",
        "1 000 000", "1\302\240500", "3,5", "3.14", "2,25", "1.500", "1,500", "-5", "21", "2", "1", "11", "12", "100",
        "1000", "2000", "1990", "99999999999999999999", "000", "0", "до", "от", "около", "с", "к", "ко", "в", "во",
        "книга", "книги", "окно", "стол", "дня", "\xd9\xa3", "\xe0\xa5\xa8", "١٢", "…", "—", "–", "-", " - ", "«", "»",
        "(", ")", ".", ",", ":", ";", "!", "?", "&", "+", "=", "@", "#", "№", "§", "×", "/", "'", " ", " ", " ", "\t",
        "\n", "İ", "Київ", "ґ", "ѐ", "Ѐ", "ӣ", "é", "ä", "ß", "中", "한", "ạ", "\xe0\xb8", "\xff", "\x80"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 1607;
    int bad = 0;
    long chunks = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long Cyrillic runs: the word limit */
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 11 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; } /* random byte */
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_RU, &ws, check_ru, &bad);
        if (rc < 0 || bad) { printf("fuzz ru: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
        chunks += rc;
    }
    if (run("", VTTS_LANG_RU, &ws, NULL, NULL) != 0 || run("..., !", VTTS_LANG_RU, &ws, NULL, NULL) != 0) {
        puts("fuzz ru: empty input must give 0 chunks");
        return 1;
    }
    printf("fuzz ru: ok (%ld chunks%s)\n", chunks, s_has_ru ? ", with the stress tables" : "");
    return 0;
}

/* pl mode: chunks inside the pl-en set (151 ids, no Vietnamese ids) */
static int check_pl(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 151 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_pl(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "Kraków", "cześć", "chrząszcz", "szczęście", "dziewczyna", "dżem", "dźwięk", "źle", "rzeka", "przy",
        "kiedy", "historii", "linii", "Europa", "nauka", "muzeum", "muzyka", "muzyce", "byliśmy", "zrobilibyśmy",
        "uniwersytet", "wziął", "idę", "są", "w", "z", "W", "Z", "np.", "Np.", "itd.", "tzn.", "ul.", "dr", "r.", "roku",
        "rok", "wieku", "wiek", "w.", "maja", "o", "do", "od", "około", "zł", "gr", "mln", "tys.", "km", "kg", "°C",
        "%", "$", "€", "XX", "XIX", "IV", "PKP", "NATO", "USB", "ESP32", "Wi-Fi", "iPhone", "update", "smartphone",
        "15.12.2026", "2026-12-15", "14:30", "9:05:07", "+48 123 456 789", "600 123 456", "1 000 000", "3,5",
        "23,99", "1.500", "1,500", "-5", "21", "2", "1", "12", "100", "1000", "2000", "1990",
        "99999999999999999999", "książka", "okno", "muzeum", "¿", "¡", "…", "—", "–", "-", " - ", "«", "»", "(",
        ")", ".", ",", ":", ";", "!", "?", "&", "+", "=", "@", "#", "§", "×", "/", "'", " ", " ", " ", "\t", "\n",
        "İ", "Škoda", "é", "ß", "ø", "中", "Москва", "ạ", "\xe0\xb8", "\xff", "\x80"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 1717;
    int bad = 0;
    long chunks = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0;
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 11 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; }
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_PL, &ws, check_pl, &bad);
        if (rc < 0 || bad) { printf("fuzz pl: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
        chunks += rc;
    }
    if (run("", VTTS_LANG_PL, &ws, NULL, NULL) != 0 || run("..., !", VTTS_LANG_PL, &ws, NULL, NULL) != 0) {
        puts("fuzz pl: empty input must give 0 chunks");
        return 1;
    }
    printf("fuzz pl: ok (%ld chunks)\n", chunks);
    return 0;
}

/* Arabic words (vowel marks, shadda, tanwin, hamza forms, sun letters, clitics, tatweel, Persian
 * letters, presentation forms), Arabic-Indic and Eastern digits, ، ؛ ؟, numbers, dates, times,
 * money, units, Latin words and random bytes; chunks must stay inside the ar-en set (149 ids, no
 * Vietnamese ids) */
static int check_ar(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 149 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_ar(void) {
#if VTTS_ENABLE_AR
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "العربية", "الكتاب", "والشمس", "بالله", "للمدرسة", "هذا", "ذلك", "لكن", "مدرستنا", "حكومات", "الدولية",
        "كتبوا", "فيسبوك", "سوريا", "الوطنى", "اكثر", "مِنْ", "كِتَابٌ", "شُكْرًا", "عَرَبِيّ", "هُوَ", "اِسْتِخْدَام",
        "َ", "ُ", "ِ", "ْ", "ّ", "ً", "ٌ", "ٍ", "ٰ", "ٓ", "ٔ", "ٕ", "ـ", "ء", "أ", "إ", "آ", "ؤ", "ئ", "ى", "ة",
        "ا", "و", "ي", "ل", "ک", "ی", "ٱ", "ۀ", "ﻻ", "ﷲ", "ﷺ", "﷼", "ۖ", "ؐ", "٠", "١", "٢", "٥", "٩", "۰", "۴",
        "۹", "٫", "٬", "٪", "،", "؛", "؟", "۔", "عام", "سنة", "العام", "من", "هـ", "م", "ص", "صباحا", "مساء",
        "ر.س", "د.إ", "د.ك", "ج.م", "كم", "سم", "كغ", "د.", "إلخ", "ق.م", "ص.ب", "a", "Z", "e", "S", "P", "x",
        "'", "-", "/", ".", ",", ":", "%", "$", "€", "£", "+", "=", "&", "@", "×", "#", "0", "1", "2", "3", "5",
        "9", " ", " ", "\t", "ESP32", "Wi-Fi", "iPhone", "km", "GB", "USD", "15/08/1947", "2026-11-19",
        "2024/1/5", "10:30", "7:15 ص", "1445 هـ", "+966 50 123 4567", "0501234567", "1,250", "3.14", "-5",
        "15%", "$100", "5 $", "50 ر.س", "5 km", "128GB", "30°C", "10-20", "من 10-20", "\xd8", "\xff", "\x80",
        "é", "中", "한", "ạ", "ش"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 1919;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 12000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words: the word cut */
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 11 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; } /* random byte */
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_AR, &ws, check_ar, &bad);
        if (rc < 0 || bad) { printf("fuzz ar: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_AR, &ws, NULL, NULL) != 0 || run("،؟", VTTS_LANG_AR, &ws, NULL, NULL) != 0) {
        puts("fuzz ar: empty input must give 0 chunks");
        return 1;
    }
    puts("fuzz ar: ok");
#else
    puts("fuzz ar: not compiled (VTTS_ENABLE_AR=0)");
#endif
    return 0;
}

/* Khmer words (clusters, subscripts, shifters, bantoc, robat, ៍, independent vowels, ៗ, abbreviations),
 * Khmer digits, numbers, dates, times, riel, units, Latin words, punctuation, zero-width spaces and
 * random bytes, runs without spaces longer than VTTS_KM_MAX_RUN; chunks must stay inside the km-en set
 * (176 ids, no Vietnamese ids) */
static int check_km(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 176 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_km(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "ខ្ញុំ", "ប្រទេស", "កម្ពុជា", "សង្គម", "ចិត្ត", "របស់", "នគរ", "ទីក្រុង", "ពុទ្ធ", "ផ្ទះ", "ធម៌", "ភូមិ",
        "ទាំង", "ស្រ្តី", "ក្ដី", "ឲ្យ", "ស៊ី", "ប៉ុន្តែ", "ព្រះ", "ៗ", "ផ្ទះៗ", "ព.ស.", "គ.ស.", "គ.ម.", "ល.រ.",
        "ឥ", "ឯក", "ឱ្យ", "ឫ", "្", "៉", "៊", "់", "៌", "៍", "៎", "៏", "័", "៑", "ំ", "ះ", "ៈ", "ា", "ិ", "ី", "ុ",
        "ូ", "េ", "ែ", "ោ", "ៅ", "ក", "ង", "រ", "ស", "អ", "ញ", "ប", "៛", "០", "៥", "៩", "។", "៕", "៖", "\xe2\x80\x8b",
        "，", "。", "“", "”", "（", "）", "…", "—", "–", "·", "％", "１", "Ａ", "a", "Z", "e", "S", "P", "x", "'", "-",
        "/", ".", ",", ":", "%", "$", "€", "£", "¥", "฿", "+", "=", "&", "@", "×", "0", "1", "2", "3", "5", "9", " ",
        " ", "\t", "ESP32", "Wi-Fi", "iPhone", "19/11/2026", "2026-11-19", "14:30", "14:30:05", "012-345-678",
        "+855 12 345 678", "0123456789", "1,234", "3.14", "-5", "99%", "5000៛", "៛500", "$5", "5km", "16GB",
        "30°C", "10-20", "12345678", "ថ្ងៃទី", "ម៉ោង", "\xe1\x9e", "\xff", "\x80", "é", "中", "ไทย", "ạ"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4245;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 5 == 0;
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; }
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_KM, &ws, check_km, &bad);
        if (rc < 0 || bad) { printf("fuzz km: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_KM, &ws, NULL, NULL) != 0 || run("។។៖", VTTS_LANG_KM, &ws, NULL, NULL) != 0) {
        puts("fuzz km: empty input must give 0 chunks");
        return 1;
    }
    puts("fuzz km: ok");
    return 0;
}

/* Burmese syllables (medials, stacks, kinzi, asat, tone marks, independent vowels, ၌ ၍ ၏ ၎), Zawgyi
 * text and code points, Burmese digits and the letter wa for zero, numbers, dates, times, kyat, units,
 * Latin words, punctuation and random bytes; chunks must stay inside the my-en set (160 ids) */
static int check_my(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 160 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_my(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "မြန်မာ", "ကျွန်တော်", "မင်္ဂလာပါ", "ကမ္ဘာ", "ကလေး", "သူက", "ကိုယ်", "ကြောင်း", "တိုက်", "ရှိ", "နှင့်", "ပြည်",
        "လည်း", "ဝန်", "ကျွန်ုပ်", "ယောက်ျား", "၌", "၍", "၏", "၎င်း", "၎", "ဿ", "ဣ", "ဥ", "ဦး", "ဩ", "ဪ", "ါ", "ာ",
        "ိ", "ီ", "ု", "ူ", "ေ", "ဲ", "ံ", "့", "း", "်", "္", "ျ", "ြ", "ွ", "ှ", "က", "င", "ည", "ဝ", "သ",
        "ေျပာပါတယ္", "ႏိုင္ငံ", "ၾကည့္", "ၿမိဳ႕", "၀န္", "ၤ", "ၠ", "ႀ", "ၚ", "႔", "ဳ", "\xe2\x80\x8b",
        "၀", "၅", "၉", "၁၉၅၄ဝဝဝ", "၊", "။", "，", "。", "“", "”", "（", "）", "…", "—", "–", "·", "％", "１", "Ａ",
        "a", "Z", "e", "S", "P", "x", "'", "-", "/", ".", ",", ":", "%", "$", "€", "£", "¥", "฿", "+", "=", "&",
        "@", "×", "0", "1", "2", "3", "5", "9", " ", " ", "\t", "ESP32", "Wi-Fi", "iPhone", "19/11/2026",
        "2026-11-19", "14:30", "14:30:05", "09 4512 3456", "+95 9 123 4567", "0123456789", "1,234", "3.14",
        "-5", "99%", "5000 Ks", "$5", "5km", "16GB", "30°C", "10-20", "12345678", "\xe1\x80", "\xff", "\x80", "é",
        "中", "ไทย", "ខ្មែរ", "ạ"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4246;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 5 == 0;
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; }
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_MY, &ws, check_my, &bad);
        if (rc < 0 || bad) { printf("fuzz my: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_MY, &ws, NULL, NULL) != 0 || run("။။၊", VTTS_LANG_MY, &ws, NULL, NULL) != 0) {
        puts("fuzz my: empty input must give 0 chunks");
        return 1;
    }
    puts("fuzz my: ok");
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
            for (int m = VTTS_LANG_ES; m <= VTTS_LANG_PT; m++) {
                rc = run(buf, m, &ws, NULL, NULL);
                if (rc < 0) { printf("fuzz lt: error %d\n", rc); return 1; }
            }
            rc = run(buf, VTTS_LANG_TH, &ws, NULL, NULL);
            if (rc < 0) { printf("fuzz th: error %d\n", rc); return 1; }
#if VTTS_ENABLE_TL
            rc = run(buf, VTTS_LANG_TL, &ws, NULL, NULL);
            if (rc < 0) { printf("fuzz tl: error %d\n", rc); return 1; }
#endif
            rc = run(buf, VTTS_LANG_KM, &ws, NULL, NULL);
            if (rc < 0) { printf("fuzz km: error %d\n", rc); return 1; }
            rc = run(buf, VTTS_LANG_MY, &ws, NULL, NULL);
            if (rc < 0) { printf("fuzz my: error %d\n", rc); return 1; }
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

/* Spanish, Indonesian, Portuguese: words with the languages' letters, numbers, dates, times, money,
 * units, ordinals, phone numbers, codes, acronyms, abbreviations, English words, punctuation of every
 * normalizer pass and random bytes; chunks must stay inside the mode's token set (no Vietnamese ids) */
static int s_lt_vocab;

static int check_lt(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= s_lt_vocab || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_lt(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "canción", "año", "pingüino", "México", "queso", "guerra", "chico", "llave", "xilófono", "ciudad", "muy",
        "hielo", "enak", "kereta", "besar", "anak2", "pantai", "ma'af", "tinggal", "menyanyi", "mejanya", "canção",
        "mão", "pães", "bem", "falam", "ainda", "rainha", "táxi", "exemplo", "quer", "janela", "famosa", "ÑANDÚ",
        "Ação", "İstanbul", "straße", "Œuvre", "ﬁn", "ｈｏｌａ", "𝐡𝐨𝐥𝐚", "ǅ", "Ⅻ", "²", "½", "º", "ª", "٣", "١٢",
        "Netflix", "iPhone", "GitHub", "Wi-Fi", "smart", "weekend", "update", "USB", "GPS", "ONU", "KTP", "ESP32",
        "ESP32-P4", "RTX3060", "A1", "Sr.", "Sra.", "EE. UU.", "EE.UU.", "etc.", "n.º", "nº", "dll.", "Jl.",
        "No.", "yg", "a.n.", "s.d.", "PT.", "vc", "pq", "Ltda.", "Dr.", "Prof.", "D.", "Rp", "Rp.", "R$", "US$",
        "$", "€", "£", "¥", "%", "°C", "℃", "°", "km", "km/h", "km/jam", "kWh", "mAh", "GB", "ml", "L", "h", "hs",
        "hrs", "min", "s", "m", "g", "ha", "ribu", "juta", "miliar", "mil", "milhões", "milhão", "º", "ª", "er",
        "ke-", "Ke", "pukul ", "PUKUL ", "jam ", "Jam ", "pu\xe2\x84\xaaul ", "0", "1", "2", "3", "5", "7", "9",
        "00", "12", "21", "100", "1001", "2026", "1.000", "1,5", "3,14", "1.234,56", "1,234.56", "1.234.567", "0,05",
        "-5", "+34", "(11)", " 91234-5678", "600 123 456", "0812", "14:30", "7:00 h", "14h30", "14h", "8.15",
        "5/3/2026", "05/03/26", "2026-03-05", "2026-13-45", "10-20", "10 – 20", "1.º", "2.ª", "3.er", "1º", "ke-3",
        "ke3", "…", "...", "—", "–", " - ", "¿", "¡", "?", "!", ",", ".", ";", ":", "'", "\"", "“", "”", "«", "»",
        "(", ")", "[", "]", "<", ">", "*", "_", "~", "|", "&", "+", "=", "@", "#", "×", "/", "-", " ", " ", "  ",
        "\t", "\n", "\xc2\x85", "\x1c", "।", "。", "\xe1\xba", "\xff", "\x80", "é", "ạ", "中", "한"};
    const int np = (int)(sizeof parts / sizeof *parts);
    static const int vocab[3] = {138, 141, 150};
    unsigned seed = 4244;
    int bad = 0;
    long chunks = 0;
    for (int it = 0; it < 9000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words */
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
        int m = it % 3;
        s_lt_vocab = vocab[m];
        int rc = run(buf, VTTS_LANG_ES + m, &ws, check_lt, &bad);
        if (rc < 0 || bad) { printf("fuzz lt: mode %d rc %d, bad chunk %d (iteration %d)\n", m, rc, bad, it); return 1; }
        chunks += rc;
    }
    for (int m = VTTS_LANG_ES; m <= VTTS_LANG_PT; m++)
        if (run("", m, &ws, NULL, NULL) != 0 || run("¿¡...,", m, &ws, NULL, NULL) != 0) {
            puts("fuzz lt: empty input must give 0 chunks");
            return 1;
        }
    printf("fuzz lt: ok (es, id, pt; %ld chunks)\n", chunks);
    return 0;
}

/* fr mode: French words, elision, liaison triggers, numbers, Roman numerals, money, times, phone
 * numbers, abbreviations, inverted verbs, English words, random bytes, very long words */
static int fuzz_fr(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "les", "des", "un", "une", "mon", "en", "on", "nous", "ils", "petit", "grand", "bon", "ancien", "six",
        "dix", "huit", "vingt", "neuf", "cent", "tous", "est", "l'est", "nord", "quatre", "ami", "amis", "enfant",
        "héros", "haricot", "homme", "onze", "oui", "yeux", "yaourt", "l'", "d'", "qu'", "jusqu'", "aujourd'hui",
        "quelqu'un", "L'iPhone", "l’école", "c'est", "z'", "''", "'", "-t-il", "a-t-elle", "dit-il", "allez-y",
        "vas-en", "-T-IL", "ſ-y", "parlent", "moment", "client", "souvent", "évidemment", "premier", "hiver",
        "fille", "ville", "travail", "soleil", "feuille", "accueil", "œil", "cœur", "Œuvre", "ñandú", "straße",
        "İstanbul", "ø", "ﬁn", "ã", "ﬀ", "Ⅻ", "²", "½", "º", "٣", "١٢", "science", "patiente", "bientôt", "temps",
        "Netflix", "iPhone", "GitHub", "Wi-Fi", "weekend", "update", "USB", "SNCF", "ONU", "ESP32", "ESP32-P4",
        "M.", "Mme", "MM.", "Dr", "etc.", "J.-C.", "av. J.-C.", "n°", "qqn", "svp", "c.-à-d.", "XIXe", "Ier",
        "XIV", "Louis ", "Henri IV", "Le", "Ce", "Ve", "LIe", "1er", "1re", "2e", "2nd", "2nde", "3èmes", "0", "1",
        "2", "7", "9", "00", "12", "21", "71", "80", "81", "91", "99", "100", "200", "1000", "80000", "2026",
        "1 000", "10 000 000", "1,5", "3,14", "1.234,56", "0,05", "-5", "+33", "+33 6 12 34 56 78", "0612345678",
        "06.12.34.56.78", "0033", "(0)", "+1 234 567 89", "14 h 30", "14h30", "8 h", "21:15", "1 h", "h", "min",
        "12,50 €", "0,50 €", "1 000 000 €", "€", "EUR", "CHF", "$", "US$", "£", "¥", "million", "millions",
        "milliard", "mille", "%", "°C", "km", "km/h", "Go", "m²", "t", "s", "14/07/1789", "2026-11-19", "1.5.24",
        "10-20", "10 – 20", "heures", "pages", "minute", "…", "...", "—", "–", " - ", "¿", "¡", "?", "!", ",",
        ".", ";", ":", "\"", "“", "”", "«", "»", "(", ")", "[", "]", "*", "&", "+", "=", "@", "#", "×", "/", "§",
        "-", " ", " ", "  ", "\t", "\n", "\xc2\xa0", "\xe2\x80\xaf", "\xc2\x85", "\x1c", "।", "。", "ᵉʳ", "ʳᵉ",
        "ᵉ", "ᵈ", "\xe1\xba", "\xff", "\x80", "é", "ạ", "中", "한"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4711;
    int bad = 0;
    long chunks = 0;
    for (int it = 0; it < 9000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words */
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
        s_lt_vocab = 143;
        int rc = run(buf, VTTS_LANG_FR, &ws, check_lt, &bad);
        if (rc < 0 || bad) { printf("fuzz fr: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
        chunks += rc;
    }
    if (run("", VTTS_LANG_FR, &ws, NULL, NULL) != 0 || run("¿¡...,", VTTS_LANG_FR, &ws, NULL, NULL) != 0) {
        puts("fuzz fr: empty input must give 0 chunks");
        return 1;
    }
    printf("fuzz fr: ok (%ld chunks)\n", chunks);
    return 0;
}

/* German: words with umlauts and ß, compounds, prefixes, foreign endings, numbers, ordinals with a
 * dot, dates, times, money, units, phone numbers, abbreviations, codes, English words, punctuation of
 * every normalizer pass and random bytes; chunks must stay inside de-en (167 ids, no Vietnamese ids) */
static int check_de(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 167 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_de(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "Straße", "Größe", "Bäckerei", "Häuschen", "Bahnhofstraße", "Universität", "studieren", "verstehen",
        "beachten", "Ausstellung", "übersetzen", "Unterricht", "Familie", "Energie", "Musik", "Technik",
        "politisch", "Gymnasium", "König", "königlich", "Ewigkeit", "sechs", "Chor", "Chef", "Chemie", "Vater",
        "Video", "Klavier", "Nation", "speziell", "Patient", "zweitausendsechsundzwanzig", "einundzwanzig",
        "Nordosten", "Café", "Qualle", "Pizza", "xylophon", "ÄÖÜ", "ẞ", "ﬁn", "𝐡𝐚𝐥𝐥𝐨", "ǅ", "Ⅻ", "²", "½", "٣",
        "Netflix", "iPhone", "GitHub", "Wi-Fi", "Update", "Laptop", "Meeting", "USB", "NATO", "ESP32", "ESP32-P4",
        "A1", "z. B.", "z.B.", "d. h.", "u. a.", "usw.", "bzw.", "ca.", "Dr.", "Prof.", "Nr.", "Mio.", "v. Chr.",
        "E-Mail", "WLAN", "Lkw", "GmbH", "km/h", "€", "EUR", "Euro", "US$", "$", "£", "CHF", "¥", "%", "‰", "°C",
        "℃", "°", "km", "m²", "kWh", "mAh", "GB", "ml", "L", "h", "min", "Min.", "s", "t", "A", "Uhr", " Uhr",
        "am ", "im ", "der ", "die ", "Mai", "Januar", "Jänner", "0", "1", "2", "3", "5", "7", "9", "00", "12",
        "21", "100", "1001", "1999", "2026", "1.000", "1,5", "3,14", "1.234,56", "1,234.56", "1.234.567",
        "0,05", "0,99", "5,50", "5,-", "-5", "−3", "+49", "(030)", " 1234567", "030 1234567", "0171/1234567",
        "0123456", "14:30", "14.30", "9:05", "7 Uhr", "3.5.", "03.05.2026", "3.5.26", "2026-05-03", "2026-13-45",
        "10-20", "10 – 20", "3. ", "1. ", "…", "...", "—", "–", " - ", "¿", "¡", "?", "!", ",", ".", ";", ":",
        "'", "\"", "“", "”", "«", "»", "(", ")", "[", "]", "*", "_", "&", "+", "=", "@", "#", "×", "/", "§",
        "-", " ", " ", "  ", "\t", "\n", "\xc2\x85", "\x1c", "।", "。", "\xe1\xba", "\xff", "\x80", "é",
        "ạ", "中", "한"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4245;
    int bad = 0;
    long chunks = 0;
    for (int it = 0; it < 6000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words */
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
        int rc = run(buf, VTTS_LANG_DE, &ws, check_de, &bad);
        if (rc < 0 || bad) { printf("fuzz de: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
        chunks += rc;
    }
    if (run("", VTTS_LANG_DE, &ws, NULL, NULL) != 0 || run("¿¡...,", VTTS_LANG_DE, &ws, NULL, NULL) != 0) {
        puts("fuzz de: empty input must give 0 chunks");
        return 1;
    }
    printf("fuzz de: ok (%ld chunks)\n", chunks);
    return 0;
}

/* Italian and Turkish (each when compiled in): elision, suffixes after apostrophes, Turkish casing,
 * numbers, dates, times, money, units, ordinals, phone numbers, codes, English words, every normalizer
 * pass and random bytes; chunks must stay inside the mode's token set (no Vietnamese ids) */
static int fuzz_lt2(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "l'acqua", "L’acqua", "sull'", "dell'", "c'è", "po'", "quest'", "'", "’", "ʼ", "ˈ", "perché", "città",
        "gnocchi", "figlio", "scienza", "pizzeria", "ventisei", "geologia", "amico", "è", "İstanbul'da", "Ankara'ya",
        "iPhone'u", "Google'da", "'da", "'inci", "'üncü", "4'üncü", "IŞIK", "İLK", "ılık", "ağaç", "değil", "hâlâ",
        "kâr", "rüzgâr", "gelmiyor", "şehirdir", "amacıyla", "mısınız", "masada", "straße", "Œuvre", "ﬁn", "ｈｏｌａ",
        "ǅ", "Ⅻ", "²", "½", "º", "ª", "°", "°C", "٣", "Netflix", "iPhone", "GitHub", "Wi-Fi", "smart", "weekend",
        "USB", "NATO", "THY", "ESP32", "ESP32-P4", "Sig.ra", "Dott.ssa", "S.p.A.", "ecc.", "Dr.", "Prof.", "vb.",
        "M.Ö.", "T.C.", "TL", "₺", "US$", "EUR", "CHF", "$", "€", "£", "%", "km", "km/h", "km/sa", "kWh", "mAh",
        "GB", "alle ", "Alle ", "ore ", "saat ", "Saat ", "0", "1", "2", "3", "5", "7", "9", "00", "12", "21",
        "101", "2026", "1.000", "1,5", "12,50", "1.234.567", "-5", "+39", "+90", "333 1234567", "0532 123 45 67",
        "14:30", "9.15", "5/3/2026", "19.11.2026", "2026-03-05", "10-20", "5. ", "…", "...", "—", "–", " - ",
        "¿", "¡", "?", "!", ",", ".", ";", ":", "\"", "“", "”", "(", ")", "*", "&", "+", "=", "@", "#", "×", "/",
        "-", " ", " ", "  ", "\t", "\n", "\xc2\x85", "\xe1\xba", "\xff", "\x80", "ạ", "中", "한"};
    const int np = (int)(sizeof parts / sizeof *parts);
    static const struct { int lang, vocab; } modes[] = {
#if VTTS_ENABLE_IT
        {VTTS_LANG_IT, 142},
#endif
#if VTTS_ENABLE_TR
        {VTTS_LANG_TR, 146},
#endif
        {-1, 0}};
    const int nm = (int)(sizeof modes / sizeof *modes) - 1;
    if (!nm) { puts("fuzz it/tr: not compiled in"); return 0; }
    unsigned seed = 1913;
    int bad = 0;
    long chunks = 0;
    for (int it = 0; it < 9000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0;
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; }
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int m = it % nm;
        s_lt_vocab = modes[m].vocab;
        int rc = run(buf, modes[m].lang, &ws, check_lt, &bad);
        if (rc < 0 || bad) { printf("fuzz it/tr: mode %d rc %d, bad chunk %d (iteration %d)\n", modes[m].lang, rc, bad, it); return 1; }
        chunks += rc;
    }
    for (int m = 0; m < nm; m++)
        if (run("", modes[m].lang, &ws, NULL, NULL) != 0 || run("¿¡...,", modes[m].lang, &ws, NULL, NULL) != 0) {
            puts("fuzz it/tr: empty input must give 0 chunks");
            return 1;
        }
    printf("fuzz it/tr: ok (%d modes; %ld chunks)\n", nm, chunks);
    return 0;
}

/* Finnish and Greek (fuzz_pair): words of the language, numbers, dates, times, money, units,
 * ordinals, ranges, phone numbers, codes, acronyms, abbreviations, English words, punctuation of
 * every normalizer pass and random bytes; chunks must stay inside the mode's token set */
static int s_pair_vocab;

static int check_pair(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= s_pair_vocab || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static const char *const FI_PARTS[] = {
    "kukka", "saari", "kengät", "Helsinki", "kansanpuolue", "hengityshäiriö", "pizza", "taxi", "cirkus", "show",
    "shakki", "Åbo", "yö", "öljy", "Zürich", "straße", "ja", "on", "he", "home", "tie", "Turn", "the", "Spotify",
    "update", "kaksisataakolme", "kahdeskymmenes", "toista", "km", "kWh", "klo", "kello", "Kello", "esim.", "jne.",
    "n.", "mm.", "ns.", "eKr.", "jKr.", "kpl", "milj.", "s.", "v.", "Oy", "ry", "tri", "USB", "Nato", "YLE", "ESP32",
    "ESP32-P4", "iPhone", "GitHub", "Wi-Fi", "toukokuuta", "3.", "1.", "21.", "3.5.2026", "3.5.", "15.12.", "2026-11-19",
    "19/11/2026", "14.30", "9.05", "14:30", "7:00:15", "klo 14.30", "kello 9", "040 123 4567", "+358 40 123 4567",
    "09 123 456", "0401234567", "1 000 000", "10 000", "1 250", "12,50 €", "1 €", "€5", "$20", "EUR", "15 %", "1 %",
    "3,5", "-5", "25 °C", "5 km", "1 km", "120 km/h", "1939–1945", "10-20", "10 – 20", "1.000", "1,234.5", "²", "٣",
    "0", "1", "2", "3", "5", "9", "00", "12", "21", "100", "2026", "…", "...", "—", "–", " - ", "¿", "¡", "?", "!",
    ",", ".", ";", ":", "'", "\"", "“", "”", "«", "»", "(", ")", "[", "]", "*", "&", "+", "=", "@", "#", "×", "/",
    "-", "%", "°", " ", " ", "  ", "\t", "\n", "\xc2\xa0", "\xe2\x80\xaf", "\xe1\xba", "\xff", "\x80", "é", "ạ", "中",
    "Σ", "ά"};

static const char *const EL_PARTS[] = {
    "Αθήνα", "είναι", "παιδιά", "χωριό", "ήλιος", "δημιουργία", "για", "γιατί", "ποιος", "μπαμπάς", "ντομάτα",
    "πέντε", "άγκυρα", "άγγελος", "άγχος", "αύριο", "ευχαριστώ", "Εύβοια", "λαϊκός", "τσάι", "τζάμι", "κόσμος",
    "Έλληνας", "ψάρι", "ξένος", "άνθρωπός", "ΑΘΗΝΑ", "ΟΔΟΣ", "ΣΑΣ", "Σ", "σ", "ς", "και", "το", "φως", "διακόσια",
    "βιολί", "ἄνθρωπος", "ᾠδή", "α\xcc\x81", "\xcc\x88", "ΐ", "ΰ", "Ά", "Ώ", "Ϊ", "ϊ", "ΔΕΗ", "ΟΤΕ", "ΚΚΕ", "ΑΒΓ",
    "ΗΠΑ", "ΕΕ", "π.χ.", "κ.λπ.", "κλπ.", "δηλ.", "μ.Χ.", "π.μ.", "τηλ.", "Τηλ.", "κ.", "κα", "Δρ", "χλμ.", "χλμ",
    "τ.μ.", "εκ.", "γρ.", "μ.", "Μαΐου", "μαΐου", "ώρες", "ώρα", "φίλους", "αδελφές", "θέσεις", "γυναίκες", "άνθρωποι",
    "στις ", "Στις ", "1ος", "2η", "3ο", "20ός", "21ο", "11ης", "3-η", "Netflix", "Wi-Fi", "iPhone", "ESP32",
    "ESP32-P4", "Turn", "the", "km", "GB", "kWh", "EUR", "€", "$", "£", "¥", "US$", "%", "°C", "°", "3/5/1990",
    "3.5.2024", "2026-11-19", "14:30", "9.15", "7:00:15", "210 1234567", "+30 6912345678", "6912345678",
    "2101234567", "+30 210 123 4567", "1.000.000", "1.250", "12,50", "3,5", "-5", "10-20", "10 – 20", "0", "1",
    "2", "3", "4", "13", "14", "100", "101", "200", "1000", "2026", "3000", "²", "٣", "…", "...", "—", "–",
    " - ", "?", "!", ",", ".", ";", "\xcd\xbe", "\xce\x87", "\xc2\xb7", ":", "'", "\"", "“", "”", "«", "»", "(",
    ")", "&", "+", "=", "@", "#", "×", "/", "-", " ", " ", "  ", "\t", "\n", "\xe1\xba", "\xff", "\x80", "é",
    "İ", "ı", "ǅ", "ạ", "中", "Москва"};

static int fuzz_pair(int lang, const char *const *parts, int np, int vocab, const char *name) {
    static vtts_text_ws ws;
    static char buf[20000];
    unsigned seed = 4244;
    int bad = 0;
    long chunks = 0;
    s_pair_vocab = vocab;
    for (int it = 0; it < 6000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words */
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
        int rc = run(buf, lang, &ws, check_pair, &bad);
        if (rc < 0 || bad) { printf("fuzz %s: rc %d, bad chunk %d (iteration %d)\n", name, rc, bad, it); return 1; }
        chunks += rc;
    }
    if (run("", lang, &ws, NULL, NULL) != 0 || run("¿¡...,;", lang, &ws, NULL, NULL) != 0) {
        printf("fuzz %s: empty input must give 0 chunks\n", name);
        return 1;
    }
    printf("fuzz %s: ok (%ld chunks)\n", name, chunks);
    return 0;
}

/* Malay: words of the Malay rules (digraphs gh dh th sh ch, ngg, ke-/se- before a vowel, e table),
 * Malay numbers, months and their abbreviations (also with re.IGNORECASE look-alikes ſ İ ı K), times
 * with day parts, ringgit and sen, units, abbreviations, English words and random bytes; chunks must
 * stay inside ms-en (145 ids, no Vietnamese ids) */
static int fuzz_ms(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "besar", "seorang", "keadaan", "tinggi", "Inggeris", "mangga", "ghaib", "Ramadhan", "Mahathir", "syarikat",
        "Shah", "chef", "universiti", "televisyen", "nenek", "teksi", "mejanya", "kereta", "daripada", "kepada", "anak2",
        "pantai", "ma'af", "quran", "xilofon", "km", "dll", "KTM", "UMNO", "ASEAN", "ESP32", "Wi-Fi", "iPhone", "update",
        "Jln.", "En.", "Pn.", "Sdn. Bhd.", "Sdn Bhd", "Kg.", "m.s.", "YB", "YAB", "No.", "drpd", "RM", "RM ", "US$", "S$",
        "Rp", "$", "€", "£", "¥", "sen", " sen", "ribu", "juta", "bilion", "trilion", "%", "°C", "℃", "°", "km/j",
        "km/jam", "kWj", "mAh", "GB", "Jan", "jan.", "Feb", "Mac", "Ogos", "Sept", "sep", "Dis", "Disember", "januari",
        "ſep", "julaİ", "\xe2\x84\xaaok", "okt", "Okt.", "ı", "pukul ", "jam ", "Pukul ", " pagi", " PAGI", " tengah hari",
        " tengah malam", " petang", " malam", " waktu", " Waktu", "0", "1", "2", "5", "8", "9", "00", "12", "19", "24",
        "31", "32", "100", "2026", "20261", "1,250.50", "1.000.000", "1,500.300.200", "3.14", "3,5", "0.50", "12.50",
        "8.30", "14:30", "7:00:15", "5/3/2026", "2026-03-05", "ke-3", "ke3", "Ke-1", "10-20", "10 – 20", "-5",
        "+60", "012-345 6789", "0312345678", "…", "...", "—", " - ", "?", "!", ",", ".", ";", ":", "'", "\"", "(", ")",
        "&", "+", "=", "@", "#", "×", "/", "-", " ", " ", "  ", "\t", "\n", "\xc2\x85", "\xe1\xba", "\xff", "é", "ạ",
        "中", "한"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 2828;
    int bad = 0;
    long chunks = 0;
    s_lt_vocab = 145;
    for (int it = 0; it < 6000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0;
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; }
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_MS, &ws, check_lt, &bad);
        if (rc < 0 || bad) { printf("fuzz ms: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
        chunks += rc;
    }
    if (run("", VTTS_LANG_MS, &ws, NULL, NULL) != 0 || run("...,", VTTS_LANG_MS, &ws, NULL, NULL) != 0) {
        puts("fuzz ms: empty input must give 0 chunks");
        return 1;
    }
    printf("fuzz ms: ok (%ld chunks)\n", chunks);
    return 0;
}

#if VTTS_ENABLE_TL
/* Tagalog: words with ñ and accent marks, affixes, clitics, reduplication, glottal hyphens, numbers
 * with the linker, clock times, peso prices, dates, units, phone numbers, codes, English words,
 * punctuation of every normalizer pass and random bytes; chunks must stay inside tl-en (139 ids) */
static int fuzz_tl(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "bata", "batà", "hindî", "akó", "mabilis", "Niño", "Villa", "kumain", "kinain", "nagluluto", "pinakamaganda",
        "maaari", "tao", "kain", "mag-aral", "mag-Aral", "pag-ibig", "araw-araw", "Araw-ARAW", "isa-isa", "i-share",
        "nag-email", "na-update", "dalawampu't", "ako'y", "isáng", "mga", "ng", "nang", "ngayon", "ngipin", "sanggol",
        "tsinelas", "dyip", "Hosé", "jose", "rehiyon", "nasyonal", "siyudad", "doktor", "papel", "loob", "doon", "kalooban",
        "ÑANDÚ", "İka", "ıka", "ſet.", "Diſyembre", "\xe2\x84\xaa", "ǹ", "ấ", "a\xcc\x81", "n\xcc\x83", "̃", "́", "ﬁn",
        "ｈｏｌａ", "Ⅻ", "²", "½", "٣", "١٢", "Netflix", "iPhone", "GitHub", "Wi-Fi", "smart", "weekend", "update", "USB",
        "DOH", "NATO", "PAGASA", "ESP32", "RTX3060", "A1", "Gng.", "Bb.", "Dr.", "Dra.", "Sto.", "Brgy.", "atbp.", "Jr.",
        "Engr.", "Atty.", "pp.", "₱", "PHP", "Php", "US$", "$", "€", "£", "¥", "%", "°C", "℃", "°", "km", "km/h", "kph",
        "kWh", "mAh", "GB", "ml", "L", "m", "g", "ha", "libo", "milyon", "bilyon", "trilyon", "ika-", "Ika", "ika",
        "alas ", "ALAS-", "ala ", "ng ", "NG ", "umaga", "tanghali", "hapon", "gabi", "gabİ", "madaling araw",
        "hatinggabi", "am", "p.m.", "A.M", "pM", "Enero ", "Peb. ", "may.", "Mayo ", "Nob.", "nobyembre", "Set.", "dis.",
        "0", "1", "2", "3", "5", "7", "9", "00", "12", "21", "30", "100", "400", "1001", "2026", "1,000", "1.5",
        "3.14", "1,234.56", "1.234,5", "21,234.5", "1.234.567", "0.05", "-5", "+63", " 917 123 4567", "0917", "13:45",
        "0:15", "23:59", "24:00", "3:30", "10:05:30", "11/19/2026", "19/11/26", "2026-11-19", "2026-13-45", "10-20",
        "10 – 20", "…", "...", "—", "–", " - ", "-", "¿", "¡", "?", "!", ",", ".", ";", ":", "'", "\"", "“", "”",
        "(", ")", "[", "]", "<", ">", "*", "_", "~", "|", "&", "+", "=", "@", "#", "×", "/", " ", " ", "  ", "\t",
        "\n", "\xc2\x85", "\x1c", "。", "\xe1\xba", "\xff", "\x80", "é", "ạ", "中", "한"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 2911;
    int bad = 0;
    long chunks = 0;
    s_lt_vocab = 139;
    for (int it = 0; it < 9000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words */
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
        int rc = run(buf, VTTS_LANG_TL, &ws, check_lt, &bad);
        if (rc < 0 || bad) { printf("fuzz tl: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
        chunks += rc;
    }
    if (run("", VTTS_LANG_TL, &ws, NULL, NULL) != 0 || run("¿¡...,", VTTS_LANG_TL, &ws, NULL, NULL) != 0) {
        puts("fuzz tl: empty input must give 0 chunks");
        return 1;
    }
    printf("fuzz tl: ok (%ld chunks)\n", chunks);
    return 0;
}
#endif

/* Swahili: words with ng', digraphs, syllabic nasals, accents, numbers, dates, times, money before and
 * after the amount, percent, units before and after the number, ordinals, phone numbers, codes,
 * acronyms, abbreviations, English words, punctuation of every normalizer pass and random bytes;
 * chunks must stay inside sw-en (no Vietnamese ids) */
static int fuzz_sw(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "ng'ombe", "ng\xe2\x80\x99ombe", "Ng'ambo", "ngoma", "mtoto", "mtu", "nchi", "nne", "mmea", "nyumba", "shule",
        "chakula", "thelathini", "dhahabu", "ghali", "khamsini", "mbwa", "ndizi", "njaa", "nzuri", "kiatu", "kaa",
        "lazima", "Lázima", "ALLAH", "Allah", "habari", "kitabu", "kwa", "na", "ya", "wa", "Kwa", "WA", "\xe2\x84\xaawa",
        "cha", "vya", "mwa", "taxi", "quiz", "single", "table", "klabu", "takriban", "rasmi", "ḿ", "é", "à", "ǘ",
        "\xcc\x81", "\xcd\x81", "Å", "İ", "ı", "ſaa", "\xe2\x84\xaaKK", "Netflix", "iPhone", "GitHub", "Wi-Fi",
        "smart", "weekend", "update", "USB", "GPS", "CCM", "TANESCO", "NSSF", "ESP32", "ESP32-P4", "A1", "n.k.",
        "nk.", "k.m.", "Bw.", "Bi.", "Dkt.", "Dk.", "Prof.", "Mh.", "Mhe.", "S.L.P.", "Mt.", "Na.", "Nam.", "BK",
        "KK", "TSh", "TZS", "KSh", "KES", "USh", "UGX", "Sh.", "Sh", "US$", "$", "€", "£", "¥", "/=", "shilingi",
        "%", "asilimia ", "ASILIMIA ", "°C", "℃", "°", "km", "km/h", "km/saa", "kWh", "kW", "mAh", "GB", "ml", "L",
        "m", "g", "ha", "tarehe ", "Tarehe ", "saa ", "SAA ", "0", "1", "2", "3", "5", "7", "9", "00", "12", "21",
        "100", "1001", "2026", "1.000", "1,5", "3.14", "1,250.50", "1,234,567", "1.234.567", "0.05", "-5", "+255",
        " 712 345 678", "0712345678", "14:30", "9:15", "7:00", "24:00", "8.15", "19/11/2026", "05/03/26",
        "2026-03-05", "2026-13-45", "10-20", "10 – 20", "…", "...", "—", "–", " - ", "¿", "¡", "?", "!", ",", ".",
        ";", ":", "'", "\"", "“", "”", "‘", "’", "«", "»", "(", ")", "[", "]", "<", ">", "*", "_", "~", "|", "&",
        "+", "=", "@", "#", "×", "/", "-", " ", " ", "  ", "\t", "\n", "\xc2\x85", "\x1c", "।", "。", "\xe1\xba",
        "\xff", "\x80", "ạ", "中", "한", "١٢", "²", "½"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4245;
    int bad = 0;
    long chunks = 0;
    s_lt_vocab = 147;
    for (int it = 0; it < 6000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words */
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
        int rc = run(buf, VTTS_LANG_SW, &ws, check_lt, &bad);
        if (rc < 0 || bad) { printf("fuzz sw: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
        chunks += rc;
    }
    if (run("", VTTS_LANG_SW, &ws, NULL, NULL) != 0 || run("¿¡...,", VTTS_LANG_SW, &ws, NULL, NULL) != 0) {
        puts("fuzz sw: empty input must give 0 chunks");
        return 1;
    }
    printf("fuzz sw: ok (%ld chunks)\n", chunks);
    return 0;
}

/* Dutch, Swedish, Norwegian: words with their letters, compounds, prefixes, number words, numbers,
 * ordinals (1e 2:a 17.), dates, times, money (5,- 50:- kr), units, phone numbers, abbreviations, codes,
 * English words, every mark of the scanner and random bytes; chunks must stay inside the mode's token
 * set (no Vietnamese ids) */
typedef struct { int vocab, bad; } nx_check_t;

static int check_nx(const int32_t *ids, int n, void *user) {
    nx_check_t *c = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) c->bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= c->vocab || (ids[i] >= 10 && ids[i] <= 64)) c->bad = 1;
    return 0;
}

static int fuzz_nx(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "huis", "vrouwen", "eenentwintig", "tweeëntwintig", "één", "België", "ruïne", "geïnstalleerd", "vereniging",
        "gemakkelijk", "historisch", "functie", "informatie", "universiteit", "'s", "'t", "auto's", "zo'n", "sjuk",
        "kyrka", "stjärna", "tjugotvå", "tvåtusentjugosex", "förstå", "betala", "frihet", "kärlek", "kjøre", "skjære",
        "hvem", "gård", "holde", "hyggelig", "tjueen", "Tromsø", "Ærlig", "Åsa", "Göteborg", "øy", "nei", "ei",
        "Netflix", "iPhone", "GitHub", "Wi-Fi", "update", "software", "USB", "NATO", "NAVO", "ESP32", "ESP32-P4",
        "4G", "3D", "bijv.", "o.a.", "d.w.z.", "t/m", "v. Chr.", "t.ex.", "bl.a.", "osv.", "kl.", "Kl.", "f.eks.",
        "ca", "nr", "kr", "kr.", "€", "EUR", "SEK", "NOK", "US$", "$", "£", "¥", "ƒ", "%", "‰", "°C", "℃", "°", "km",
        "km/h", "m²", "kWh", "mAh", "GB", "min", "s", "st", "stk", "uur", " uur", "klockan", "klokka", " mai", " maj",
        " mei", "januari", "0", "1", "2", "3", "7", "9", "00", "12", "17", "21", "100", "105", "1001", "1250", "1999",
        "2026", "1.000", "1 000", ("1\xc2\xa0" "000"), "1,5", "3,14", "3.14", "1.234,56", "1 250 000", "0,05", "5,50",
        "5,-", "50:-", "-5", "−3", "+31", "+47", " 1234567", "06-12345678", "08-123 45 67", "22 12 34 56", "0123456",
        "14:30", "14.30", "9:05", "9:05:10", "3-5-2026", "2026-05-03", "03.05.2026", "3/5/26", "2026-13-45", "10-20",
        "10–20", "1e", "2de", "8ste", "1:a", "3:e", "3. ", "17. ", "…", "...", "—", "–", " - ", "¿", "¡", "?", "!",
        ",", ".", ";", ":", "'", "\"", "“", "”", "«", "»", "(", ")", "[", "]", "*", "_", "&", "+", "=", "@", "#",
        "×", "/", "§", "-", " ", "  ", "\t", "\n", "\xc2\x85", "\x1c", "।", "。", "\xe1\xba", "\xff", "\x80",
        "é", "ạ", "中", "한", "İ", "²", "ǅ", "Ⅻ", "ﬁ", "𝐡"};
    static const struct { int mode, vocab; const char *name; } MODES[] = {
        {VTTS_LANG_NL, 159, "nl"}, {VTTS_LANG_SV, 155, "sv"}, {VTTS_LANG_NO, 156, "no"}};
    const int np = (int)(sizeof parts / sizeof *parts);
    for (int m = 0; m < 3; m++) {
        vtts_lang l0;
        int ts = MODES[m].mode == VTTS_LANG_NL ? 21 /* nl-en */ : MODES[m].mode == VTTS_LANG_SV ? 23 /* sv-en */
                                                                                                    : 24 /* no-en */;
        if (vtts_text_lang_for(ts, MODES[m].name, &l0) < 0) continue; /* not compiled in */
        unsigned seed = 4321u + (unsigned)m;
        nx_check_t chk = {MODES[m].vocab, 0};
        long chunks = 0;
        for (int it = 0; it < 4000; it++) {
            seed = seed * 1103515245u + 12345u;
            int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
            int no_space = it % 7 == 0;
            while (n < target) {
                seed = seed * 1103515245u + 12345u;
                unsigned r = seed >> 16;
                if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; }
                const char *p = parts[r % (unsigned)np];
                if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
                size_t l = strlen(p);
                if (n + (int)l >= (int)sizeof buf - 1) break;
                memcpy(buf + n, p, l);
                n += (int)l;
            }
            buf[n] = 0;
            int rc = run(buf, MODES[m].mode, &ws, check_nx, &chk);
            if (rc < 0 || chk.bad) { printf("fuzz %s: rc %d, bad chunk %d (iteration %d)\n", MODES[m].name, rc, chk.bad, it); return 1; }
            chunks += rc;
        }
        if (run("", MODES[m].mode, &ws, NULL, NULL) != 0 || run("¿¡...,", MODES[m].mode, &ws, NULL, NULL) != 0) {
            printf("fuzz %s: empty input must give 0 chunks\n", MODES[m].name);
            return 1;
        }
        printf("fuzz %s: ok (%ld chunks)\n", MODES[m].name, chunks);
    }
    return 0;
}

/* Lao words (clusters, preposed vowels, tone marks, ໌, ໆ, ຯ, ໜ ໝ ຫຼ, ໍາ written apart,
 * abbreviations), Lao and other digits, ASCII, numbers, dates, times, units, money, Latin words,
 * punctuation and random bytes, runs without spaces longer than VTTS_LO_MAX_RUN; chunks must stay
 * inside the lo-en set (163 ids, no Vietnamese ids) */
static int check_lo(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 163 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_lo(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "ພາສາລາວ", "ສະບາຍດີ", "ຂອບໃຈ", "ຄວາມ", "ກວ່າ", "ສວນ", "ໜຶ່ງ", "ໝາ", "ຫຼາຍ", "ເຂົ້າ", "ພໍ່", "ນ້ຳ", "ນ້ໍາ", "ນໍ້າ",
        "ຄົນ", "ເມືອງ", "ຂຽນ", "ໄປ", "ໃຫຍ່", "ໂປຣແກຣມ", "ກອລ໌ຟ", "ຄ.ສ.", "ພ.ສ.", "ກມ.", "ສ.ປ.ປ.", "ຯລຯ", "ຯ", "ໆ",
        "ໄວໆ", "ທຸກໆ", "ພຣະ", "ແລະ", "໌", "ັ", "ິ", "ຸ", "່", "້", "໊", "໋", "ະ", "າ", "ຳ", "ໍ", "ົ", "ຼ", "ຽ", "ເ",
        "ແ", "ໂ", "ໃ", "ໄ", "ກ", "ຫ", "ວ", "ຣ", "຺", "໎", "໐", "໕", "໙", "ໞ", "ໟ", "₭", "฿", "，", "。", "！",
        "？", "“", "”", "（", "）", "…", "—", "–", "·", "％", "１", "Ａ", "a", "Z", "e", "S", "P", "x", "'", "-", "/",
        ".", ",", ":", "%", "$", "€", "£", "¥", "+", "=", "&", "@", "×", "0", "1", "2", "3", "5", "9", " ", " ", "\t",
        "ESP32", "Wi-Fi", "iPhone", "19/11/2026", "2026-11-19", "14:30", "8:05:09", "020 5512 3456", "+856 20 5512 3456",
        "0812345678", "1,234", "3.14", "-5", "99%", "₭5,000", "$5", "5km", "16GB", "30°C", "10-20", "12345678",
        "\xe0\xba", "\xff", "\x80", "é", "中", "한", "ไทย", "١٢", "ạ"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4245;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 5 == 0; /* long Lao runs: segmentation and the run limit */
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
        int rc = run(buf, VTTS_LANG_LO, &ws, check_lo, &bad);
        if (rc < 0 || bad) { printf("fuzz lo: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_LO, &ws, NULL, NULL) != 0 || run("。。，", VTTS_LANG_LO, &ws, NULL, NULL) != 0) {
        puts("fuzz lo: empty input must give 0 chunks");
        return 1;
    }
    puts("fuzz lo: ok");
    return 0;
}

/* Danish words (lexicon, compounds, rules: sj sch ch tion, ng nk, doubled letters, x q c z w, é),
 * other Latin letters, numbers, dates, times, kroner and øre, units, phone numbers, abbreviations,
 * acronyms, English words, punctuation and random bytes, long words; chunks must stay inside the
 * da-en set (158 ids, no Vietnamese ids) */
static int check_da(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 158 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_da(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    static const char *const parts[] = {
        "hus", "huset", "fodboldspiller", "arbejdsplads", "København", "Århus", "Ærø", "øl", "ål", "idé", "café",
        "Müller", "straße", "İstanbul", "naïve", "sjov", "schæfer", "nation", "chokolade", "ingen", "tænke", "quiz",
        "xylofon", "zoo", "whisky", "hvad", "hjem", "ikke", "lytte", "bedre", "studere", "politisk", "musik",
        "hm", "pst", "og", "i", "at", "den", "kl.", "ca.", "nr.", "f.eks.", "bl.a.", "osv.", "e.Kr.", "A/S",
        "maj", "Marts", "december", "kr.", "kr", "DKK", "øre", ",-", "€", "$", "£", "°C", "km/t", "m²", "%", "§",
        "+45", "12 34 56 78", "14.30", "14:30", "5.", "5. maj", "2026", "1984", "5/3/2026", "5.3.2026", "2026-03-05",
        "1.250,50", "3,5", "-4", "10-20", "Klokken", "klokken", "USB", "NATO", "ESP32", "iPhone", "Wi-Fi", "weekend",
        "update", "the", "time", "to", "¿", "¡", "，", "。", "！", "“", "”", "（", "）", "…", "—", "–", "·", "％", "１",
        "Ａ", "a", "Z", "e", "S", "P", "x", "'", "-", "/", ".", ",", ":", "&", "@", "#", "×", "=", "+", "0", "1", "2",
        "5", "9", " ", " ", "\t", "\xc3", "\xff", "\x80", "中", "ไทย", "١٢", "ạ", "ﬁ", "²", "Ⅻ", "\xe2\x84\xaa"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4246;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words: compounds and the word limit */
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
        int rc = run(buf, VTTS_LANG_DA, &ws, check_da, &bad);
        if (rc < 0 || bad) { printf("fuzz da: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_DA, &ws, NULL, NULL) != 0 || run("¿¡...,", VTTS_LANG_DA, &ws, NULL, NULL) != 0) {
        puts("fuzz da: empty input must give 0 chunks");
        return 1;
    }
    puts("fuzz da: ok");
    return 0;
}

static int mode_of(const char *m) {
    if (strcmp(m, "tl") == 0) return VTTS_LANG_TL;
    if (strcmp(m, "sw") == 0) return VTTS_LANG_SW;
    if (strcmp(m, "en") == 0) return VTTS_LANG_EN;
    if (strcmp(m, "auto") == 0) return VTTS_LANG_AUTO;
    if (strcmp(m, "zh") == 0) return VTTS_LANG_ZH;
    if (strcmp(m, "ko") == 0) return VTTS_LANG_KO;
    if (strcmp(m, "hi") == 0) return VTTS_LANG_HI;
    if (strcmp(m, "ja") == 0) return VTTS_LANG_JA;
    if (strcmp(m, "es") == 0) return VTTS_LANG_ES;
    if (strcmp(m, "id") == 0) return VTTS_LANG_ID;
    if (strcmp(m, "pt") == 0) return VTTS_LANG_PT;
    if (strcmp(m, "th") == 0) return VTTS_LANG_TH;
    if (strcmp(m, "nl") == 0) return VTTS_LANG_NL;
    if (strcmp(m, "sv") == 0) return VTTS_LANG_SV;
    if (strcmp(m, "no") == 0) return VTTS_LANG_NO;
    if (strcmp(m, "fr") == 0) return VTTS_LANG_FR;
    if (strcmp(m, "de") == 0) return VTTS_LANG_DE;
    if (strcmp(m, "it") == 0) return VTTS_LANG_IT;
    if (strcmp(m, "tr") == 0) return VTTS_LANG_TR;
    if (strcmp(m, "ru") == 0) return VTTS_LANG_RU;
    if (strcmp(m, "pl") == 0) return VTTS_LANG_PL;
    if (strcmp(m, "ar") == 0) return VTTS_LANG_AR;
    if (strcmp(m, "fi") == 0) return VTTS_LANG_FI;
    if (strcmp(m, "el") == 0) return VTTS_LANG_EL;
    if (strcmp(m, "ms") == 0) return VTTS_LANG_MS;
    if (strcmp(m, "lo") == 0) return VTTS_LANG_LO;
    if (strcmp(m, "da") == 0) return VTTS_LANG_DA;
    if (strcmp(m, "km") == 0) return VTTS_LANG_KM;
    if (strcmp(m, "my") == 0) return VTTS_LANG_MY;
    return VTTS_LANG_VI;
}

int main(int argc, char **argv) {
    const char *file = NULL, *nfkc = NULL;
    int do_fuzz = 0, do_bench = 0, do_fuzz_lt = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fuzz") == 0) do_fuzz = 1;
        else if (strcmp(argv[i], "--fuzz-lt") == 0) do_fuzz_lt = 1;
        else if (strcmp(argv[i], "--fuzz-th") == 0) do_fuzz = 2;
        else if (strcmp(argv[i], "--fuzz-nx") == 0) do_fuzz = 13;
        else if (strcmp(argv[i], "--fuzz-fr") == 0) do_fuzz = 3;
        else if (strcmp(argv[i], "--fuzz-de") == 0) do_fuzz = 4;
        else if (strcmp(argv[i], "--fuzz-it-tr") == 0) do_fuzz = 5;
        else if (strcmp(argv[i], "--fuzz-ru") == 0) do_fuzz = 6;
        else if (strcmp(argv[i], "--fuzz-pl") == 0) do_fuzz = 7;
        else if (strcmp(argv[i], "--fuzz-ar") == 0) do_fuzz = 8;
        else if (strcmp(argv[i], "--fuzz-fi") == 0) do_fuzz = 9;
        else if (strcmp(argv[i], "--fuzz-el") == 0) do_fuzz = 10;
        else if (strcmp(argv[i], "--fuzz-ms") == 0) do_fuzz_lt = 2;
        else if (strcmp(argv[i], "--fuzz-tl") == 0) do_fuzz = 11;
        else if (strcmp(argv[i], "--fuzz-sw") == 0) do_fuzz = 12;
        else if (strcmp(argv[i], "--ru") == 0 && i + 1 < argc) {
            if (load_ru(argv[++i])) { puts("bad ru blob"); return 2; }
        }
        else if (strcmp(argv[i], "--fuzz-lo") == 0) do_fuzz = 14;
        else if (strcmp(argv[i], "--fuzz-da") == 0) do_fuzz = 15;
        else if (strcmp(argv[i], "--fuzz-km") == 0) do_fuzz = 16;
        else if (strcmp(argv[i], "--fuzz-my") == 0) do_fuzz = 17;
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
    if (do_fuzz == 2) return fuzz_th();
    if (do_fuzz == 13) return fuzz_nx();
    if (do_fuzz == 3) return fuzz_fr();
    if (do_fuzz == 4) return fuzz_de();
    if (do_fuzz == 5) return fuzz_lt2();
    if (do_fuzz == 6) return fuzz_ru();
    if (do_fuzz == 7) return fuzz_pl();
    if (do_fuzz == 8) return fuzz_ar();
    if (do_fuzz == 9) return fuzz_pair(VTTS_LANG_FI, FI_PARTS, (int)(sizeof FI_PARTS / sizeof *FI_PARTS), 142, "fi");
    if (do_fuzz == 10) return fuzz_pair(VTTS_LANG_EL, EL_PARTS, (int)(sizeof EL_PARTS / sizeof *EL_PARTS), 139, "el");
#if VTTS_ENABLE_TL
    if (do_fuzz == 11) return fuzz_tl();
    if (do_fuzz == 12) return fuzz_sw();
#endif
    if (do_fuzz == 14) return fuzz_lo();
    if (do_fuzz == 15) return fuzz_da();
    if (do_fuzz == 16) return fuzz_km();
    if (do_fuzz == 17) return fuzz_my();
    if (do_fuzz) return fuzz();
    if (do_fuzz_lt == 2) return fuzz_ms();
    if (do_fuzz_lt) return fuzz_lt();
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
