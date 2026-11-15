/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_text.h -- on-device Vietnamese text front-end: UTF-8 text -> phoneme id chunks.
 *
 * Mirrors src/vtts/frontend (normalize -> split_sentences -> g2p -> encode) for the
 * device subset: Vietnamese words, letters/acronyms, loanwords, abbreviations, numbers
 * (integers, decimals, thousands separators, negatives), percent, dates (d/m, d/m/yyyy),
 * times (8:30, 8h30, 8h), punctuation. Not supported on device: e-mail, URLs, phone
 * numbers, ISO dates, currency and units (the host front-end handles them).
 *
 * No malloc: the caller provides a workspace (~40 KB). Not re-entrant per workspace.
 */
#ifndef VTTS_TEXT_H
#define VTTS_TEXT_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define VTTS_TEXT_MAX_CP 4096     /* code points per call */
#define VTTS_TEXT_MAX_WORDS 1536  /* normalized words per sentence */
#define VTTS_TEXT_WORD_BYTES 16384
#define VTTS_TEXT_MAX_IDS 320     /* ids per chunk: 40 syllables x <= 7 tokens + BOS/EOS */

typedef struct {
    uint32_t cp[VTTS_TEXT_MAX_CP];
    uint8_t date_start[VTTS_TEXT_MAX_CP]; /* dates are found before numbers, like Python */
    int n_cp;
    char words[VTTS_TEXT_WORD_BYTES]; /* normalized words of the current sentence, NUL separated */
    int word_off[VTTS_TEXT_MAX_WORDS];
    int n_words, words_used;
    int32_t ids[VTTS_TEXT_MAX_IDS];
} vtts_text_ws;

/* Called once per chunk (<= 40 syllables) with ids including BOS ... EOS.
 * Return non-zero to stop. */
typedef int (*vtts_ids_cb)(const int32_t *ids, int n, void *user);

/* Returns the number of chunks emitted (0 for empty/punctuation-only text) or < 0 on error. */
int vtts_text_to_ids(const char *utf8, vtts_text_ws *ws, vtts_ids_cb cb, void *user);

#ifdef __cplusplus
}
#endif
#endif
