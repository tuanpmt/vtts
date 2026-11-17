/* SPDX-License-Identifier: Apache-2.0 */
/* bsp.h -- board support interface of the vtts firmware.
 *
 * A board is a folder boards/<id>/ with:
 *   board.h            name, speaker pins and defaults (BSP_* macros, see boards/README.md)
 *   board.cmake        target chip and speaker driver (set(BSP_TARGET ...) set(BSP_SPEAKER ...))
 *   sdkconfig.defaults board-level Kconfig (flash size, console, PSRAM mode, ...)
 * Speaker drivers live in main/bsp/speaker_<driver>.c and implement the functions below. */
#pragma once

#include <stdint.h>

#include "board.h" /* boards/<id>/board.h, selected by BOARD=<id> */

#ifndef BSP_DEFAULT_VOL
#define BSP_DEFAULT_VOL 70 /* 0..100 */
#endif
#ifndef BSP_DEFAULT_GAIN_DB
#define BSP_DEFAULT_GAIN_DB 0.0f /* digital gain before the soft limiter */
#endif

/* Board name, for the boot log. */
const char *bsp_name(void);

/* Setup that must run first in app_main: e.g. latch the power (BSP_POWER_HOLD_GPIO). */
void bsp_early_init(void);

/* Bring up the speaker path at one of the given rates (tried in order). Returns the rate in use,
 * or 0 if the speaker is unavailable. */
int bsp_speaker_open(const int *rates, int n_rates);

/* Volume 0..100 (codec gain, or a digital scale for plain DACs). */
void bsp_speaker_set_vol(int vol);

/* Blocking write of 16-bit mono PCM; may scale the samples in place. */
void bsp_speaker_write(int16_t *pcm, int n);
