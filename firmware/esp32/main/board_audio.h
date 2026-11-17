/* SPDX-License-Identifier: Apache-2.0 */
/* board_audio.h -- speaker output for the supported boards: an ES8311 codec (P4 boards) or a
 * PCM5101 I2S DAC (ESP32-S3-Touch-LCD-2.8). */
#pragma once

#include <stdint.h>

#include "sdkconfig.h"

/* Default volume (0..100) and digital gain (dB, before a soft limiter): the model peaks near
 * -8 dBFS, and the NANO's speaker path is quieter than the panel's. */
#if defined(CONFIG_VTTS_BOARD_P4_NANO)
#define BOARD_DEFAULT_VOL 90
#define BOARD_DEFAULT_GAIN_DB 12.0f
#elif defined(CONFIG_VTTS_BOARD_S3_ECHOEAR)
#define BOARD_DEFAULT_VOL 75
#define BOARD_DEFAULT_GAIN_DB 6.0f
#elif defined(CONFIG_VTTS_BOARD_S3_TOUCH_LCD_28)
#define BOARD_DEFAULT_VOL 80
#define BOARD_DEFAULT_GAIN_DB 6.0f
#else
#define BOARD_DEFAULT_VOL 70
#define BOARD_DEFAULT_GAIN_DB 0.0f
#endif

/* Board-level setup that must run first in app_main (e.g. a power self-latch). */
void board_early_init(void);

/* Board name, for the boot log. */
const char *board_name(void);

/* Bring up the speaker path and open it at one of the given rates (tried in order).
 * Returns the rate in use, or 0 if the speaker is unavailable. */
int board_speaker_open(const int *rates, int n_rates);

/* Volume 0..100: codec gain on ES8311 boards, a digital scale on the PCM5101 board. */
void board_speaker_set_vol(int vol);

/* Blocking write of 16-bit mono PCM; may scale the samples in place. */
void board_speaker_write(int16_t *pcm, int n);
