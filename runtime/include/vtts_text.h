/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_text.h -- on-device text front-end: UTF-8 text -> phoneme id chunks.
 *
 * vtts_text_to_ids: Vietnamese, phoneme set v1 (the released Vietnamese models).
 * vtts_text_to_ids_ex: bilingual Vietnamese + English, phoneme set v2, like text_to_ids(text, lang)
 * in src/vtts/frontend/text.py (sentence split, language per word, Vietnamese or English
 * normalization per run, English G2P with the VLEX lexicon, chunks of <= 40 words / 318 tokens).
 *
 * Mirrors src/vtts/frontend (normalize -> split_sentences -> g2p -> encode) for the
 * device subset: Vietnamese words, letters/acronyms, loanwords, abbreviations, numbers
 * (integers, decimals, thousands separators, negatives), percent, dates (d/m, d/m/yyyy),
 * times (8:30, 8h30, 8h), punctuation. Not supported on device: e-mail, URLs, phone
 * numbers, ISO dates, currency and units (the host front-end handles them).
 *
 * VTTS_LANG_ZH: Mandarin + English, token set zh-en (ids 0..106 = v2, Mandarin from 107), like
 * text_to_ids(text, "zh"): Chinese normalization (numbers, dates, times, money, percent, product
 * codes), readings from the ZLEX blob (vtts_zlex.h), English words with the VLEX lexicon.
 *
 * VTTS_LANG_KO: Korean + English, token set ko-en (ids 0..106 = v2, Korean from 107), like
 * text_to_ids(text, "ko"): Korean normalization (Sino-Korean and native numbers with counters, dates,
 * times, money, units, phone numbers, product codes), the exception table and the standard
 * pronunciation rules (tables compiled in, no blob), English words with the VLEX lexicon.
 *
 * VTTS_LANG_HI: Hindi + English, token set hi-en (ids 0..106 = v2, Hindi from 107), like
 * text_to_ids(text, "hi"): Hindi normalization (numbers 0-99 from a table with sau, hazaar, lakh and
 * crore, decimals, dates, years, times, rupees and paise, units, percentages, phone numbers, ordinals,
 * product codes, Devanagari digits; the danda ends a sentence), the Devanagari letter, nasal and
 * schwa-deletion rules with the exception table (tables compiled in, no blob), English words with
 * the VLEX lexicon.
 *
 * No malloc: the caller provides a workspace (about 145 KB with the v2, zh and ko scratch; PSRAM is fine).
 * Not re-entrant per workspace.
 */
#ifndef VTTS_TEXT_H
#define VTTS_TEXT_H

#include <stdint.h>

#include "vtts_lex.h"
#include "vtts_zlex.h"

#ifdef __cplusplus
extern "C" {
#endif

#define VTTS_TEXT_MAX_CP 4096     /* code points per call */
#define VTTS_TEXT_MAX_WORDS 1536  /* normalized words per sentence */
#define VTTS_TEXT_WORD_BYTES 16384
#define VTTS_TEXT_MAX_IDS 320     /* ids per chunk: 40 syllables x <= 7 tokens + BOS/EOS */
#define VTTS_TEXT_EN_CAP 6144     /* code points of an English run after expansion (v2) */
#define VTTS_TEXT_MAX_ITEMS 2048  /* words and marks per sentence (v2) */
#define VTTS_TEXT_POOL 16384      /* token ids of one sentence (v2) */

typedef struct {
    uint32_t cp[VTTS_TEXT_MAX_CP];
    uint8_t date_start[VTTS_TEXT_MAX_CP]; /* bit 0: a date starts here; bit 1: digit of a product code */
    int n_cp;
    char words[VTTS_TEXT_WORD_BYTES]; /* normalized words of the current sentence, NUL separated */
    int word_off[VTTS_TEXT_MAX_WORDS];
    int n_words, words_used;
    int32_t ids[VTTS_TEXT_MAX_IDS];
    /* v2 (bilingual) scratch; the whole workspace is about 145 KB, so place it in PSRAM */
    uint32_t run[VTTS_TEXT_MAX_CP];                     /* one language run, words joined by spaces */
    uint32_t en_a[VTTS_TEXT_EN_CAP], en_b[VTTS_TEXT_EN_CAP];
    char en_out[VTTS_TEXT_EN_CAP];
    uint16_t item_off[VTTS_TEXT_MAX_ITEMS];
    uint16_t item_len[VTTS_TEXT_MAX_ITEMS]; /* a Korean word may be one item of up to 318 tokens */
    uint8_t item_punct[VTTS_TEXT_MAX_ITEMS];
    uint8_t item_join[VTTS_TEXT_MAX_ITEMS]; /* 1: a syllable joined to the previous one without SPACE (zh) */
    uint8_t pool[VTTS_TEXT_POOL];
    int n_items, pool_used;
} vtts_text_ws;

typedef enum { VTTS_LANG_V1 = 0, VTTS_LANG_VI, VTTS_LANG_EN, VTTS_LANG_AUTO, VTTS_LANG_ZH, VTTS_LANG_KO,
               VTTS_LANG_HI } vtts_lang;

/* lang: VTTS_LANG_V1 is vtts_text_to_ids; VI, EN and AUTO select the mode of text_to_ids(text,
 * "vi" | "en" | "auto") with phoneme set v2; ZH selects text_to_ids(text, "zh") with token set
 * zh-en; KO selects text_to_ids(text, "ko") with token set ko-en; HI selects text_to_ids(text, "hi") with
 * token set hi-en. lex: the English lexicon (NULL: English words are not pronounced, only acronyms are
 * spelled). zh: the Mandarin reading tables (NULL: Han characters are not pronounced; only used
 * by VTTS_LANG_ZH). */
typedef struct { vtts_lang lang; const vtts_lex *lex; const vtts_zlex *zh; } vtts_text_opts;

/* Called once per chunk (<= 40 syllables) with ids including BOS ... EOS.
 * Return non-zero to stop. */
typedef int (*vtts_ids_cb)(const int32_t *ids, int n, void *user);

/* Returns the number of chunks emitted (0 for empty/punctuation-only text) or < 0 on error. */
int vtts_text_to_ids(const char *utf8, vtts_text_ws *ws, vtts_ids_cb cb, void *user);

/* Same, with options (NULL or VTTS_LANG_V1: vtts_text_to_ids). v2 chunks hold <= 40 words and
 * <= 318 tokens plus BOS/EOS. */
int vtts_text_to_ids_ex(const char *utf8, vtts_text_ws *ws, const vtts_text_opts *o, vtts_ids_cb cb,
                        void *user);

/* Text modes per model token set (token_set: vtts_token_set_t from vtts.h), the modes of
 * MODE_LANGS in src/vtts/frontend/lang.py that the device front-end implements:
 *   v1    "vi" (VTTS_LANG_V1)                  default vi
 *   vi-en "vi" | "en" | "auto"                 default vi
 *   zh-en "zh" (Han -> Mandarin, Latin -> English, numbers in Mandarin)   default zh
 *   ko-en "ko" (Hangul -> Korean, Latin -> English, numbers in Korean)    default ko
 *   hi-en "hi" (Devanagari -> Hindi, Latin -> English, numbers in Hindi)  default hi
 *   ja-en, unknown: no device front-end (token ids from a host front-end only).
 * vtts_text_lang_for: 0 and *out set when `mode` is valid for the set, else < 0.
 * vtts_text_default_lang: 0 and *out set, or < 0 when the set has no device front-end. */
int vtts_text_lang_for(int token_set, const char *mode, vtts_lang *out);
int vtts_text_default_lang(int token_set, vtts_lang *out);
const char *vtts_text_modes(int token_set); /* "vi", "vi|en|auto", "zh", "ko", "hi" or "" */
const char *vtts_text_lang_name(vtts_lang lang); /* "vi" (V1 and VI), "en", "auto", "zh", "ko", "hi" */

#ifdef __cplusplus
}
#endif
#endif
