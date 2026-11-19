/* SPDX-License-Identifier: Apache-2.0 */
/* token_set_test.c -- the token_set dim of the model header (docs/model-format.md) and the text
 * modes each token set offers (vtts_text_lang_for). Blobs are built in memory: header and dims
 * only, no tensors. usage: token_set_test [--sw-off]  (--sw-off: built with VTTS_ENABLE_SW=0) */
#include <stdio.h>
#include <string.h>

#include "vtts.h"
#include "vtts_text.h"
#include "vtts_text_fr.h" /* VTTS_ENABLE_FR */
#include "vtts_text_tl.h" /* VTTS_ENABLE_TL */
#include "vtts_text_lo.h" /* VTTS_ENABLE_LO */
#include "vtts_text_da.h" /* VTTS_ENABLE_DA */

static int fails;
#define CHECK(c)                                                         \
    do {                                                                 \
        if (!(c)) { printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); fails++; } \
    } while (0)

static const char *REQUIRED[] = {"latent", "hop", "sample_rate", "max_duration", "d_hidden", "d_depth",
                                 "d_kernel", "a_hidden", "a_token_depth", "a_frame_depth", "a_kernel", "decoder"};

static void put_u32(unsigned char *p, uint32_t v) {
    for (int i = 0; i < 4; i++) p[i] = (unsigned char)(v >> (8 * i));
}

static size_t put_dim(unsigned char *p, const char *key, int32_t v) {
    memset(p, 0, 36);
    memcpy(p, key, strlen(key));
    put_u32(p + 32, (uint32_t)v);
    return 36;
}

#define NO_DIM (-1000)

/* header + required dims + vocab, plus token_set unless ts == NO_DIM */
static size_t make_blob(unsigned char *b, int vocab, int ts) {
    size_t n_req = sizeof REQUIRED / sizeof *REQUIRED, pos = 20;
    uint32_t n_dims = (uint32_t)n_req + 1 + (ts != NO_DIM);
    memcpy(b, "VTTS", 4);
    put_u32(b + 4, 1);
    put_u32(b + 8, n_dims);
    put_u32(b + 12, 0);
    for (size_t i = 0; i < n_req; i++) pos += put_dim(b + pos, REQUIRED[i], 1);
    pos += put_dim(b + pos, "vocab", vocab);
    if (ts != NO_DIM) pos += put_dim(b + pos, "token_set", ts);
    put_u32(b + 16, (uint32_t)pos);
    return pos;
}

static int load(int vocab, int ts, vtts_model *m) {
    static unsigned char blob[2048];
    size_t n = make_blob(blob, vocab, ts);
    return vtts_init(m, blob, n);
}

int main(int argc, char **argv) {
    const int sw_off = argc > 1 && strcmp(argv[1], "--sw-off") == 0;
    static vtts_model m;
    vtts_lang l0;
    /* files without the dim: by vocab, exact sizes first, else the old rule (> 65: vi-en) */
    static const int vocab_map[][2] = {{65, VTTS_TOKSET_V1},    {107, VTTS_TOKSET_VI_EN}, {171, VTTS_TOKSET_ZH_EN},
                                       {153, VTTS_TOKSET_KO_EN}, {144, VTTS_TOKSET_JA_EN}, {157, VTTS_TOKSET_HI_EN},
                                       {138, VTTS_TOKSET_ES_EN}, {141, VTTS_TOKSET_ID_EN}, {150, VTTS_TOKSET_PT_EN},
                                       {176, VTTS_TOKSET_VI_EN}, {160, VTTS_TOKSET_VI_EN}, {100, VTTS_TOKSET_VI_EN},
                                       {256, VTTS_TOKSET_VI_EN}, {40, VTTS_TOKSET_V1}};
    for (size_t i = 0; i < sizeof vocab_map / sizeof *vocab_map; i++) {
        CHECK(load(vocab_map[i][0], NO_DIM, &m) == VTTS_OK);
        CHECK(vtts_token_set(&m) == vocab_map[i][1]);
        CHECK(m.token_set_in_file == 0);
    }
    /* the dim wins over the vocab: a zh-en model may have extra rows */
    CHECK(load(180, VTTS_TOKSET_ZH_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_ZH_EN && m.token_set_in_file);
    CHECK(load(171, VTTS_TOKSET_ZH_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_ZH_EN);
    CHECK(load(107, VTTS_TOKSET_VI_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN);
    CHECK(load(65, VTTS_TOKSET_V1, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_V1);
    /* 0 means "not recorded" */
    CHECK(load(171, 0, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_ZH_EN);
    /* a known set larger than the embedding is a broken file */
    CHECK(load(107, VTTS_TOKSET_ZH_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(load(65, VTTS_TOKSET_VI_EN, &m) == VTTS_ERR_FORMAT);
    /* a code from a newer exporter still loads (raw ids only) */
    CHECK(load(200, 42, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(load(200, -3, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    /* es-en, id-en, pt-en (6..8): known sets */
    static const struct { int ts, size; const char *name; } pairs[] = {
        {VTTS_TOKSET_ES_EN, 138, "es-en"}, {VTTS_TOKSET_ID_EN, 141, "id-en"}, {VTTS_TOKSET_PT_EN, 150, "pt-en"}};
    for (int k = 0; k < 3; k++) {
        CHECK(load(pairs[k].size, pairs[k].ts, &m) == VTTS_OK && vtts_token_set(&m) == pairs[k].ts && m.token_set_in_file);
        CHECK(load(200, pairs[k].ts, &m) == VTTS_OK && vtts_token_set(&m) == pairs[k].ts);
        CHECK(load(pairs[k].size - 1, pairs[k].ts, &m) == VTTS_ERR_FORMAT);
        CHECK(strcmp(vtts_token_set_name(pairs[k].ts), pairs[k].name) == 0 && vtts_token_set_size(pairs[k].ts) == pairs[k].size);
    }

    /* th-en (9): by the dim and by vocab 162; a smaller embedding is a broken file */
    CHECK(load(162, VTTS_TOKSET_TH_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_TH_EN && m.token_set_in_file);
    CHECK(load(162, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_TH_EN && !m.token_set_in_file);
    CHECK(load(153, VTTS_TOKSET_TH_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_TH_EN), "th-en") == 0 && vtts_token_set_size(VTTS_TOKSET_TH_EN) == 162);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_TH_EN, &l0) == 0 && l0 == VTTS_LANG_TH);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_TH_EN, "th", &l0) == 0 && l0 == VTTS_LANG_TH);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_TH_EN, "en", &l0) < 0 && vtts_text_lang_for(VTTS_TOKSET_KO_EN, "th", &l0) < 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_TH_EN), "th") == 0 && strcmp(vtts_text_lang_name(VTTS_LANG_TH), "th") == 0);
    /* km-en (31), my-en (30): by the dim only (176 / 160 without it are vi-en) */
    CHECK(load(176, VTTS_TOKSET_KM_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_KM_EN && m.token_set_in_file);
    CHECK(load(175, VTTS_TOKSET_KM_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(load(160, VTTS_TOKSET_MY_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_MY_EN && m.token_set_in_file);
    CHECK(load(159, VTTS_TOKSET_MY_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(vtts_token_set_size(VTTS_TOKSET_KM_EN) == 176 && strcmp(vtts_token_set_name(VTTS_TOKSET_KM_EN), "km-en") == 0);
    CHECK(vtts_token_set_size(VTTS_TOKSET_MY_EN) == 160 && strcmp(vtts_token_set_name(VTTS_TOKSET_MY_EN), "my-en") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_KM), "km") == 0 && strcmp(vtts_text_lang_name(VTTS_LANG_MY), "my") == 0);
#if VTTS_ENABLE_KM
    CHECK(vtts_text_default_lang(VTTS_TOKSET_KM_EN, &l0) == 0 && l0 == VTTS_LANG_KM);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_KM_EN, "km", &l0) == 0 && l0 == VTTS_LANG_KM);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_KM_EN), "km") == 0);
#endif
#if VTTS_ENABLE_MY
    CHECK(vtts_text_default_lang(VTTS_TOKSET_MY_EN, &l0) == 0 && l0 == VTTS_LANG_MY);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_MY_EN), "my") == 0);
#endif
    CHECK(vtts_token_set_size(20) == 0 && strcmp(vtts_token_set_name(20), "unknown") == 0);

    /* fr-en (11): by the dim only (sets after hi-en are never inferred from the vocab: a file
     * without the dim is vi-en); mode fr when built with VTTS_ENABLE_FR */
    CHECK(load(143, VTTS_TOKSET_FR_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_FR_EN && m.token_set_in_file);
    CHECK(load(143, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
    CHECK(load(142, VTTS_TOKSET_FR_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_FR_EN), "fr-en") == 0 && vtts_token_set_size(VTTS_TOKSET_FR_EN) == 143);
#if VTTS_ENABLE_FR
    CHECK(vtts_text_default_lang(VTTS_TOKSET_FR_EN, &l0) == 0 && l0 == VTTS_LANG_FR);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_FR_EN, "fr", &l0) == 0 && l0 == VTTS_LANG_FR);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_FR_EN), "fr") == 0 && strcmp(vtts_text_lang_name(VTTS_LANG_FR), "fr") == 0);
#else
    CHECK(vtts_text_default_lang(VTTS_TOKSET_FR_EN, &l0) < 0 && strcmp(vtts_text_modes(VTTS_TOKSET_FR_EN), "") == 0);
#endif

    /* de-en (12): by the dim only (vocab 167 without it is vi-en) */
    CHECK(load(167, VTTS_TOKSET_DE_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_DE_EN && m.token_set_in_file);
    CHECK(load(167, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
    CHECK(load(162, VTTS_TOKSET_DE_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_DE_EN), "de-en") == 0 && vtts_token_set_size(VTTS_TOKSET_DE_EN) == 167);
#if VTTS_ENABLE_DE
    CHECK(vtts_text_default_lang(VTTS_TOKSET_DE_EN, &l0) == 0 && l0 == VTTS_LANG_DE);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_DE_EN, "de", &l0) == 0 && l0 == VTTS_LANG_DE);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_DE_EN, "en", &l0) < 0 && vtts_text_lang_for(VTTS_TOKSET_PT_EN, "de", &l0) < 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_DE_EN), "de") == 0 && strcmp(vtts_text_lang_name(VTTS_LANG_DE), "de") == 0);
#endif
    /* ru-en (16): by the dim only (vocab 154 without it is vi-en) */
    CHECK(load(154, VTTS_TOKSET_RU_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_RU_EN && m.token_set_in_file);
    CHECK(load(154, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
    CHECK(load(153, VTTS_TOKSET_RU_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_RU_EN), "ru-en") == 0 && vtts_token_set_size(VTTS_TOKSET_RU_EN) == 154);
#if VTTS_ENABLE_RU
    CHECK(vtts_text_default_lang(VTTS_TOKSET_RU_EN, &l0) == 0 && l0 == VTTS_LANG_RU);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_RU_EN, "ru", &l0) == 0 && l0 == VTTS_LANG_RU);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_RU_EN, "en", &l0) < 0 && vtts_text_lang_for(VTTS_TOKSET_HI_EN, "ru", &l0) < 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_RU_EN), "ru") == 0 && strcmp(vtts_text_lang_name(VTTS_LANG_RU), "ru") == 0);
#endif

    /* pl-en (17): by the dim only (vocab 151 without it is vi-en) */
    CHECK(load(151, VTTS_TOKSET_PL_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_PL_EN && m.token_set_in_file);
    CHECK(load(151, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
    CHECK(load(150, VTTS_TOKSET_PL_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_PL_EN), "pl-en") == 0 && vtts_token_set_size(VTTS_TOKSET_PL_EN) == 151);
#if VTTS_ENABLE_PL
    CHECK(vtts_text_default_lang(VTTS_TOKSET_PL_EN, &l0) == 0 && l0 == VTTS_LANG_PL);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_PL_EN, "pl", &l0) == 0 && l0 == VTTS_LANG_PL);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_PL_EN, "es", &l0) < 0 && vtts_text_lang_for(VTTS_TOKSET_ES_EN, "pl", &l0) < 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_PL_EN), "pl") == 0 && strcmp(vtts_text_lang_name(VTTS_LANG_PL), "pl") == 0);
#endif
    /* ar-en (19): by the dim only (vocab 149 without it is vi-en); 18 and 20 are unused */
    CHECK(load(149, VTTS_TOKSET_AR_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_AR_EN && m.token_set_in_file);
    CHECK(load(149, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
    CHECK(load(148, VTTS_TOKSET_AR_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(load(200, 18, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(load(200, 20, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_AR_EN), "ar-en") == 0 && vtts_token_set_size(VTTS_TOKSET_AR_EN) == 149);
#if VTTS_ENABLE_AR
    CHECK(vtts_text_default_lang(VTTS_TOKSET_AR_EN, &l0) == 0 && l0 == VTTS_LANG_AR);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_AR_EN, "ar", &l0) == 0 && l0 == VTTS_LANG_AR);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_AR_EN), "ar") == 0);
#else
    CHECK(vtts_text_default_lang(VTTS_TOKSET_AR_EN, &l0) < 0 && strcmp(vtts_text_modes(VTTS_TOKSET_AR_EN), "") == 0);
#endif
    CHECK(vtts_text_lang_for(VTTS_TOKSET_AR_EN, "en", &l0) < 0 && vtts_text_lang_for(VTTS_TOKSET_HI_EN, "ar", &l0) < 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_AR), "ar") == 0);

    /* ms-en (28): by the dim and by vocab 145; codes 11..27 stay unknown; mode ms with VTTS_ENABLE_MS */
    CHECK(load(145, VTTS_TOKSET_MS_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_MS_EN && m.token_set_in_file);
    CHECK(load(145, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
    CHECK(load(144, VTTS_TOKSET_MS_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(load(200, 27, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_MS_EN), "ms-en") == 0 && vtts_token_set_size(VTTS_TOKSET_MS_EN) == 145);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_MS), "ms") == 0);
#if VTTS_ENABLE_MS
    CHECK(vtts_text_default_lang(VTTS_TOKSET_MS_EN, &l0) == 0 && l0 == VTTS_LANG_MS);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_MS_EN, "ms", &l0) == 0 && l0 == VTTS_LANG_MS);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_MS_EN, "id", &l0) < 0 && vtts_text_lang_for(VTTS_TOKSET_ID_EN, "ms", &l0) < 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_MS_EN), "ms") == 0);
#else
    CHECK(vtts_text_default_lang(VTTS_TOKSET_MS_EN, &l0) < 0 && strcmp(vtts_text_modes(VTTS_TOKSET_MS_EN), "") == 0);
#endif

    /* nl-en (21), sv-en (23), no-en (24): by the dim only (159 / 155 / 156 without it are vi-en); 22 is da-en */
    {
        static const struct { int code, vocab; const char *name, *mode; vtts_lang lang; } NX[] = {
            {VTTS_TOKSET_NL_EN, 159, "nl-en", "nl", VTTS_LANG_NL}, {VTTS_TOKSET_SV_EN, 155, "sv-en", "sv", VTTS_LANG_SV},
            {VTTS_TOKSET_NO_EN, 156, "no-en", "no", VTTS_LANG_NO}};
        for (int k = 0; k < 3; k++) {
            CHECK(load(NX[k].vocab, NX[k].code, &m) == VTTS_OK && vtts_token_set(&m) == NX[k].code && m.token_set_in_file);
            CHECK(load(NX[k].vocab, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
            CHECK(load(107, NX[k].code, &m) == VTTS_ERR_FORMAT);
            CHECK(strcmp(vtts_token_set_name(NX[k].code), NX[k].name) == 0 && vtts_token_set_size(NX[k].code) == NX[k].vocab);
            CHECK(strcmp(vtts_text_lang_name(NX[k].lang), NX[k].mode) == 0);
            CHECK(vtts_text_lang_for(NX[k].code, "en", &l0) < 0 && vtts_text_lang_for(VTTS_TOKSET_PT_EN, NX[k].mode, &l0) < 0);
#if VTTS_ENABLE_NL && VTTS_ENABLE_SV && VTTS_ENABLE_NO
            CHECK(vtts_text_default_lang(NX[k].code, &l0) == 0 && l0 == NX[k].lang);
            CHECK(vtts_text_lang_for(NX[k].code, NX[k].mode, &l0) == 0 && l0 == NX[k].lang);
            CHECK(strcmp(vtts_text_modes(NX[k].code), NX[k].mode) == 0);
#endif
        }
        CHECK(load(200, 27, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    }

    /* lo-en (32): known to the loader in every build; its mode only with VTTS_ENABLE_LO */
    CHECK(load(163, VTTS_TOKSET_LO_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_LO_EN && m.token_set_in_file);
    CHECK(load(162, VTTS_TOKSET_LO_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_LO_EN), "lo-en") == 0 && vtts_token_set_size(VTTS_TOKSET_LO_EN) == 163);
    CHECK(load(200, 34, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_LO), "lo") == 0);
#if VTTS_ENABLE_LO
    CHECK(vtts_text_default_lang(VTTS_TOKSET_LO_EN, &l0) == 0 && l0 == VTTS_LANG_LO);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_LO_EN, "lo", &l0) == 0 && l0 == VTTS_LANG_LO);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_LO_EN), "lo") == 0);
#else
    {
        static vtts_text_ws ws;
        vtts_text_opts o = {VTTS_LANG_LO, NULL, NULL, NULL};
        CHECK(vtts_text_default_lang(VTTS_TOKSET_LO_EN, &l0) < 0 && vtts_text_lang_for(VTTS_TOKSET_LO_EN, "lo", &l0) < 0);
        CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_LO_EN), "") == 0);
        CHECK(vtts_text_to_ids_ex("ສະບາຍດີ", &ws, &o, NULL, NULL) < 0);
    }
#endif
    CHECK(vtts_text_lang_for(VTTS_TOKSET_TH_EN, "lo", &l0) < 0);

    /* da-en (22): known to the loader in every build; its mode only with VTTS_ENABLE_DA */
    CHECK(load(158, VTTS_TOKSET_DA_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_DA_EN && m.token_set_in_file);
    CHECK(load(157, VTTS_TOKSET_DA_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_DA_EN), "da-en") == 0 && vtts_token_set_size(VTTS_TOKSET_DA_EN) == 158);
    CHECK(load(200, 20, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_DA), "da") == 0);
#if VTTS_ENABLE_DA
    CHECK(vtts_text_default_lang(VTTS_TOKSET_DA_EN, &l0) == 0 && l0 == VTTS_LANG_DA);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_DA_EN, "da", &l0) == 0 && l0 == VTTS_LANG_DA);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_DA_EN), "da") == 0);
#else
    {
        static vtts_text_ws ws;
        vtts_text_opts o = {VTTS_LANG_DA, NULL, NULL, NULL};
        CHECK(vtts_text_default_lang(VTTS_TOKSET_DA_EN, &l0) < 0 && vtts_text_lang_for(VTTS_TOKSET_DA_EN, "da", &l0) < 0);
        CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_DA_EN), "") == 0);
        CHECK(vtts_text_to_ids_ex("Hej med dig", &ws, &o, NULL, NULL) < 0);
    }
#endif
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ES_EN, "da", &l0) < 0);

    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_V1), "v1") == 0);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_VI_EN), "vi-en") == 0);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_ZH_EN), "zh-en") == 0);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_KO_EN), "ko-en") == 0);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_JA_EN), "ja-en") == 0);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_HI_EN), "hi-en") == 0);
    CHECK(strcmp(vtts_token_set_name(99), "unknown") == 0);
    /* hi-en (code 10): the dim and its size */
    CHECK(load(157, VTTS_TOKSET_HI_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_HI_EN && m.token_set_in_file);
    CHECK(load(153, VTTS_TOKSET_HI_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(load(200, 98, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(vtts_token_set_size(VTTS_TOKSET_HI_EN) == 157 && vtts_token_set_size(98) == 0);
    CHECK(vtts_token_set_size(VTTS_TOKSET_ZH_EN) == 171 && vtts_token_set_size(99) == 0);
    /* it-en (13), tr-en (15): by the dim only (142 and 146 without it are vi-en); code 14 is unused */
    CHECK(load(142, VTTS_TOKSET_IT_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_IT_EN);
    CHECK(load(146, VTTS_TOKSET_TR_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_TR_EN);
    CHECK(load(142, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN);
    CHECK(load(146, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN);
    CHECK(load(141, VTTS_TOKSET_IT_EN, &m) == VTTS_ERR_FORMAT && load(145, VTTS_TOKSET_TR_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_IT_EN), "it-en") == 0 && strcmp(vtts_token_set_name(15), "tr-en") == 0);
    CHECK(vtts_token_set_size(14) == 0 && strcmp(vtts_token_set_name(14), "unknown") == 0);
    CHECK(load(200, 14, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
#if VTTS_ENABLE_IT
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_IT_EN), "it") == 0);
#endif
#if VTTS_ENABLE_TR
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_TR_EN), "tr") == 0);
#endif
    /* fi-en (code 25; 142 ids like it-en, so by the dim only): its size and the text mode */
    CHECK(load(142, VTTS_TOKSET_FI_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_FI_EN && m.token_set_in_file);
    CHECK(load(142, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
    CHECK(load(138, VTTS_TOKSET_FI_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(load(200, 27, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
#if VTTS_ENABLE_FI && VTTS_ENABLE_EL
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_FI_EN), "fi-en") == 0 && vtts_token_set_size(VTTS_TOKSET_FI_EN) == 142);
    CHECK(strcmp(vtts_token_set_name(20), "unknown") == 0 && vtts_token_set_size(20) == 0);
    {
        vtts_lang lf;
        CHECK(vtts_text_default_lang(VTTS_TOKSET_FI_EN, &lf) == 0 && lf == VTTS_LANG_FI);
        CHECK(vtts_text_lang_for(VTTS_TOKSET_FI_EN, "fi", &lf) == 0 && lf == VTTS_LANG_FI);
        CHECK(vtts_text_lang_for(VTTS_TOKSET_FI_EN, "en", &lf) < 0);
        CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_FI_EN), "fi") == 0 && strcmp(vtts_text_lang_name(VTTS_LANG_FI), "fi") == 0);
        /* el-en (code 26) */
        CHECK(load(139, VTTS_TOKSET_EL_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_EL_EN && m.token_set_in_file);
        CHECK(load(139, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN); /* tl-en is 139 too */
        CHECK(load(138, VTTS_TOKSET_EL_EN, &m) == VTTS_ERR_FORMAT);
        CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_EL_EN), "el-en") == 0 && vtts_token_set_size(VTTS_TOKSET_EL_EN) == 139);
        CHECK(vtts_text_default_lang(VTTS_TOKSET_EL_EN, &lf) == 0 && lf == VTTS_LANG_EL);
        CHECK(vtts_text_lang_for(VTTS_TOKSET_EL_EN, "el", &lf) == 0 && vtts_text_lang_for(VTTS_TOKSET_EL_EN, "fi", &lf) < 0);
        CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_EL_EN), "el") == 0 && strcmp(vtts_text_lang_name(VTTS_LANG_EL), "el") == 0);
    }
#endif

    /* text modes per token set (consistent with MODE_LANGS in src/vtts/frontend/lang.py) */
    vtts_lang l;
    CHECK(vtts_text_default_lang(VTTS_TOKSET_V1, &l) == 0 && l == VTTS_LANG_V1);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_VI_EN, &l) == 0 && l == VTTS_LANG_VI);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_ZH_EN, &l) == 0 && l == VTTS_LANG_ZH);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_KO_EN, &l) == 0 && l == VTTS_LANG_KO);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_HI_EN, &l) == 0 && l == VTTS_LANG_HI);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_JA_EN, &l) == 0 && l == VTTS_LANG_JA);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_UNKNOWN, &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_V1, "vi", &l) == 0 && l == VTTS_LANG_V1);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_V1, "en", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_VI_EN, "vi", &l) == 0 && l == VTTS_LANG_VI);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_VI_EN, "en", &l) == 0 && l == VTTS_LANG_EN);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_VI_EN, "auto", &l) == 0 && l == VTTS_LANG_AUTO);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_VI_EN, "zh", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ZH_EN, "zh", &l) == 0 && l == VTTS_LANG_ZH);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ZH_EN, "vi", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ZH_EN, "en", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_KO_EN, "ko", &l) == 0 && l == VTTS_LANG_KO);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_KO_EN, "zh", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_KO_EN, "en", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ZH_EN, "ko", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_VI_EN, "ko", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_JA_EN, "ko", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_HI_EN, "hi", &l) == 0 && l == VTTS_LANG_HI);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_HI_EN, "en", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_KO_EN, "hi", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_VI_EN, "hi", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_JA_EN, "ja", &l) == 0 && l == VTTS_LANG_JA);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_JA_EN, "en", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ZH_EN, "ja", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_KO_EN, "ja", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ZH_EN, NULL, &l) < 0);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_ES_EN, &l) == 0 && l == VTTS_LANG_ES);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_ID_EN, &l) == 0 && l == VTTS_LANG_ID);
    CHECK(vtts_text_default_lang(VTTS_TOKSET_PT_EN, &l) == 0 && l == VTTS_LANG_PT);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ES_EN, "es", &l) == 0 && l == VTTS_LANG_ES);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ID_EN, "id", &l) == 0 && l == VTTS_LANG_ID);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_PT_EN, "pt", &l) == 0 && l == VTTS_LANG_PT);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ES_EN, "pt", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_PT_EN, "es", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ID_EN, "en", &l) < 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_VI_EN, "es", &l) < 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_ES_EN), "es") == 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_ID_EN), "id") == 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_PT_EN), "pt") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_ES), "es") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_ID), "id") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_PT), "pt") == 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_V1), "vi") == 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_VI_EN), "vi|en|auto") == 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_ZH_EN), "zh") == 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_KO_EN), "ko") == 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_HI_EN), "hi") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_HI), "hi") == 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_JA_EN), "ja") == 0);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_UNKNOWN), "") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_JA), "ja") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_KO), "ko") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_ZH), "zh") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_V1), "vi") == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_AUTO), "auto") == 0);

    /* tl-en (code 29): known to the model loader in every build; the text mode only with VTTS_ENABLE_TL */
    CHECK(load(139, VTTS_TOKSET_TL_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_TL_EN && m.token_set_in_file);
    CHECK(load(139, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
    CHECK(load(138, VTTS_TOKSET_TL_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(load(200, 27, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN && vtts_token_set_size(27) == 0);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_TL_EN), "tl-en") == 0 && vtts_token_set_size(VTTS_TOKSET_TL_EN) == 139);
    CHECK(strcmp(vtts_token_set_name(20), "unknown") == 0 && strcmp(vtts_token_set_name(34), "unknown") == 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_ES_EN, "tl", &l) < 0 && vtts_text_lang_for(VTTS_TOKSET_TL_EN, "en", &l) < 0);
#if VTTS_ENABLE_TL
    CHECK(vtts_text_default_lang(VTTS_TOKSET_TL_EN, &l) == 0 && l == VTTS_LANG_TL);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_TL_EN, "tl", &l) == 0 && l == VTTS_LANG_TL);
    CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_TL_EN), "tl") == 0 && strcmp(vtts_text_lang_name(VTTS_LANG_TL), "tl") == 0);
#else
    {
        static vtts_text_ws ws;
        vtts_text_opts o = {VTTS_LANG_TL, NULL, NULL, NULL};
        CHECK(vtts_text_default_lang(VTTS_TOKSET_TL_EN, &l) < 0 && vtts_text_lang_for(VTTS_TOKSET_TL_EN, "tl", &l) < 0);
        CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_TL_EN), "") == 0);
        CHECK(vtts_text_to_ids_ex("Kumain ka na ba?", &ws, &o, NULL, NULL) < 0);
    }
#endif

    /* sw-en (code 33): known to the loader in every build; its text mode only with VTTS_ENABLE_SW */
    CHECK(load(147, VTTS_TOKSET_SW_EN, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_SW_EN && m.token_set_in_file);
    CHECK(load(147, NO_DIM, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_VI_EN && !m.token_set_in_file);
    CHECK(load(146, VTTS_TOKSET_SW_EN, &m) == VTTS_ERR_FORMAT);
    CHECK(load(200, 14, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(load(200, 18, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(load(200, 34, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(strcmp(vtts_token_set_name(VTTS_TOKSET_SW_EN), "sw-en") == 0 && vtts_token_set_size(VTTS_TOKSET_SW_EN) == 147);
    CHECK(strcmp(vtts_token_set_name(20), "unknown") == 0 && vtts_token_set_size(20) == 0);
    CHECK(strcmp(vtts_text_lang_name(VTTS_LANG_SW), "sw") == 0);
    CHECK(vtts_text_lang_for(VTTS_TOKSET_SW_EN, "en", &l) < 0 && vtts_text_lang_for(VTTS_TOKSET_ES_EN, "sw", &l) < 0);
    if (sw_off) { /* no Swahili front-end: like a token set without a device front-end */
        static vtts_text_ws ws;
        vtts_text_opts o = {.lang = VTTS_LANG_SW};
        CHECK(vtts_text_default_lang(VTTS_TOKSET_SW_EN, &l) < 0);
        CHECK(vtts_text_lang_for(VTTS_TOKSET_SW_EN, "sw", &l) < 0);
        CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_SW_EN), "") == 0);
        CHECK(vtts_text_to_ids_ex("Habari yako?", &ws, &o, NULL, NULL) < 0);
    } else {
        CHECK(vtts_text_default_lang(VTTS_TOKSET_SW_EN, &l) == 0 && l == VTTS_LANG_SW);
        CHECK(vtts_text_lang_for(VTTS_TOKSET_SW_EN, "sw", &l) == 0 && l == VTTS_LANG_SW);
        CHECK(strcmp(vtts_text_modes(VTTS_TOKSET_SW_EN), "sw") == 0);
    }

    printf("%s (%d failures)\n", fails ? "FAILED" : "ok", fails);
    return fails != 0;
}
