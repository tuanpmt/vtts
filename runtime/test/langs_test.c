/* SPDX-License-Identifier: Apache-2.0 */
/* langs_test.c -- the per-language build switches (vtts_langs.h). Built several times by `make
 * langs_test`: with every optional language off, and with each one alone. A language that is
 * compiled in offers its mode and reads a sentence; one that is not offers no mode and
 * vtts_text_to_ids_ex refuses it (-1). Vietnamese and English always work.
 * usage: langs_test LEX (the English lexicon blob, build/lex_en.bin) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts.h"
#include "vtts_text.h"

static int fails;
#define CHECK(c)                                                                  \
    do {                                                                          \
        if (!(c)) { printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); fails++; } \
    } while (0)

static int count(const int32_t *ids, int n, void *user) {
    (void)ids; (void)n;
    ++*(int *)user;
    return 0;
}

static vtts_lex s_lex;

static int load_lex(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *b = malloc((size_t)n); /* kept for the run */
    int ok = b && fread(b, 1, (size_t)n, f) == (size_t)n && vtts_lex_init(&s_lex, b, (size_t)n) == 0;
    fclose(f);
    return ok ? 0 : -1;
}

int main(int argc, char **argv) {
    static vtts_text_ws ws;
    if (argc < 2 || load_lex(argv[1])) { puts("usage: langs_test LEX"); return 2; }
    static const struct { int ts; vtts_lang lang; const char *mode; int on; const char *text; } L[] = {
        {VTTS_TOKSET_ZH_EN, VTTS_LANG_ZH, "zh", VTTS_ENABLE_ZH, "Netflix 今天 25 度。"},
        {VTTS_TOKSET_KO_EN, VTTS_LANG_KO, "ko", VTTS_ENABLE_KO, "안녕하세요 25도."},
        {VTTS_TOKSET_JA_EN, VTTS_LANG_JA, "ja", VTTS_ENABLE_JA, "Netflix こんにちは 25 度。"},
        {VTTS_TOKSET_HI_EN, VTTS_LANG_HI, "hi", VTTS_ENABLE_HI, "नमस्ते 25 डिग्री।"},
        {VTTS_TOKSET_TH_EN, VTTS_LANG_TH, "th", VTTS_ENABLE_TH, "สวัสดีครับ 25 องศา"},
        {VTTS_TOKSET_ES_EN, VTTS_LANG_ES, "es", VTTS_ENABLE_ES, "Hola, son las 6:30."},
        {VTTS_TOKSET_ID_EN, VTTS_LANG_ID, "id", VTTS_ENABLE_ID, "Halo, jam 6:30."},
        {VTTS_TOKSET_PT_EN, VTTS_LANG_PT, "pt", VTTS_ENABLE_PT, "Olá, são 6:30."},
        {VTTS_TOKSET_FR_EN, VTTS_LANG_FR, "fr", VTTS_ENABLE_FR, "Bonjour, il est 6 h 30."},
        {VTTS_TOKSET_DE_EN, VTTS_LANG_DE, "de", VTTS_ENABLE_DE, "Hallo, am 3. Mai um 6:30 Uhr."},
        {VTTS_TOKSET_IT_EN, VTTS_LANG_IT, "it", VTTS_ENABLE_IT, "Ciao, sono le 6:30 dell'anno."},
        {VTTS_TOKSET_TR_EN, VTTS_LANG_TR, "tr", VTTS_ENABLE_TR, "Merhaba, 5. sınıf İstanbul'da."},
        {VTTS_TOKSET_RU_EN, VTTS_LANG_RU, "ru", VTTS_ENABLE_RU, "Привет, ул. Ленина 5, в 6:30."},
        {VTTS_TOKSET_PL_EN, VTTS_LANG_PL, "pl", VTTS_ENABLE_PL, "Cześć, jest 6:30, ul. Długa 5."},
        {VTTS_TOKSET_AR_EN, VTTS_LANG_AR, "ar", VTTS_ENABLE_AR, "مرحبا، الساعة 6:30؟ نعم."},
        {VTTS_TOKSET_FI_EN, VTTS_LANG_FI, "fi", VTTS_ENABLE_FI, "Hei, kello on 6.30, n. 50 henkeä."},
        {VTTS_TOKSET_EL_EN, VTTS_LANG_EL, "el", VTTS_ENABLE_EL, "Γεια σου; Είναι 6:30, χλμ. σε."},
        {VTTS_TOKSET_MS_EN, VTTS_LANG_MS, "ms", VTTS_ENABLE_MS, "Selamat pagi, pukul 6:30, RM12.50."},
        {VTTS_TOKSET_TL_EN, VTTS_LANG_TL, "tl", VTTS_ENABLE_TL, "Magandang umaga, alas 6:30 na."},
        {VTTS_TOKSET_SW_EN, VTTS_LANG_SW, "sw", VTTS_ENABLE_SW, "Habari, saa 6:30, ng'ombe 3."},
        {VTTS_TOKSET_NL_EN, VTTS_LANG_NL, "nl", VTTS_ENABLE_NL, "Hallo, het is o.a. 6:30 uur."},
        {VTTS_TOKSET_SV_EN, VTTS_LANG_SV, "sv", VTTS_ENABLE_SV, "Hej, klockan är 6.30, t.ex. nu."},
        {VTTS_TOKSET_NO_EN, VTTS_LANG_NO, "no", VTTS_ENABLE_NO, "Hei, 17. mai klokka 6.30."},
    };
    int enabled = 0;
    for (size_t k = 0; k < sizeof L / sizeof *L; k++) {
        vtts_lang l;
        int n = 0, rc;
        vtts_text_opts o = {.lang = L[k].lang, .lex = &s_lex};
        enabled += L[k].on;
        if (L[k].on) {
            CHECK(vtts_text_default_lang(L[k].ts, &l) == 0 && l == L[k].lang);
            CHECK(vtts_text_lang_for(L[k].ts, L[k].mode, &l) == 0 && l == L[k].lang);
            CHECK(strcmp(vtts_text_modes(L[k].ts), L[k].mode) == 0);
            rc = vtts_text_to_ids_ex(L[k].text, &ws, &o, count, &n);
            CHECK(rc > 0 && n == rc);
        } else {
            CHECK(vtts_text_default_lang(L[k].ts, &l) < 0);
            CHECK(vtts_text_lang_for(L[k].ts, L[k].mode, &l) < 0);
            CHECK(strcmp(vtts_text_modes(L[k].ts), "") == 0);
            CHECK(vtts_text_to_ids_ex(L[k].text, &ws, &o, count, &n) == -1 && n == 0);
        }
        CHECK(strcmp(vtts_text_lang_name(L[k].lang), L[k].mode) == 0);
    }
    /* Vietnamese and English are always there */
    vtts_lang l;
    int n = 0;
    vtts_text_opts vi = {.lang = VTTS_LANG_VI, .lex = &s_lex}, en = {.lang = VTTS_LANG_EN, .lex = &s_lex};
    CHECK(vtts_text_default_lang(VTTS_TOKSET_V1, &l) == 0 && l == VTTS_LANG_V1);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_VI_EN, &l) == 0 && l == VTTS_LANG_VI);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_VI_EN), "vi|en|auto") == 0);
    CHECK(vtts_text_to_ids_ex("Xin chào, 25 độ.", &ws, &vi, count, &n) > 0);
    CHECK(vtts_text_to_ids_ex("Plug in the USB cable.", &ws, &en, count, &n) > 0);
    CHECK(vtts_text_to_ids("Xin chào Việt Nam.", &ws, count, &n) > 0);
    printf("langs: %d of %d optional languages compiled in, %s (%d failures)\n", enabled, (int)(sizeof L / sizeof *L),
           fails ? "FAIL" : "ok", fails);
    return fails != 0;
}
