/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_text_en.h -- English pieces of the device front-end (internal). */
#ifndef VTTS_TEXT_EN_H
#define VTTS_TEXT_EN_H

#include <stdint.h>

#include "vtts_lex.h"

/* Token ids (set v2) of one English word (letters, apostrophes, hyphens), like g2p_word_en.
 * Returns the number of ids, or < 0 if cap is too small. lx may be NULL (lexicon-free: only
 * the spelling of short acronyms is available, other words give no ids). */
int vtts_en_g2p(const vtts_lex *lx, const char *word, uint8_t *out, int cap);

#endif
