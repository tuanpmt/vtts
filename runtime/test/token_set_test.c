/* SPDX-License-Identifier: Apache-2.0 */
/* token_set_test.c -- the token_set dim of the model header (docs/model-format.md) and the text
 * modes each token set offers (vtts_text_lang_for). Blobs are built in memory: header and dims
 * only, no tensors. usage: token_set_test */
#include <stdio.h>
#include <string.h>

#include "vtts.h"
#include "vtts_text.h"

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

int main(void) {
    static vtts_model m;
    /* files without the dim: by vocab, exact sizes first, else the old rule (> 65: vi-en) */
    static const int vocab_map[][2] = {{65, VTTS_TOKSET_V1},    {107, VTTS_TOKSET_VI_EN}, {171, VTTS_TOKSET_ZH_EN},
                                       {153, VTTS_TOKSET_KO_EN}, {144, VTTS_TOKSET_JA_EN}, {157, VTTS_TOKSET_HI_EN},
                                       {100, VTTS_TOKSET_VI_EN},
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
    /* es-en, id-en, pt-en (6..8) have Python front-ends only so far, 9 (th-en) is reserved: raw ids */
    for (int ts = 6; ts <= 9; ts++) {
        CHECK(load(200, ts, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
        CHECK(m.token_set_in_file && strcmp(vtts_token_set_name(ts), "unknown") == 0);
    }

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
    CHECK(load(200, 11, &m) == VTTS_OK && vtts_token_set(&m) == VTTS_TOKSET_UNKNOWN);
    CHECK(vtts_token_set_size(VTTS_TOKSET_HI_EN) == 157 && vtts_token_set_size(7) == 0);
    CHECK(vtts_token_set_size(VTTS_TOKSET_ZH_EN) == 171 && vtts_token_set_size(99) == 0);

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

    printf("%s (%d failures)\n", fails ? "FAILED" : "ok", fails);
    return fails != 0;
}
