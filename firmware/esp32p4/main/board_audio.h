/* SPDX-License-Identifier: Apache-2.0 */
/* board_audio.h -- speaker output (ES8311 codec + power amplifier) for the supported boards. */
#pragma once

#include "esp_codec_dev.h"
#include "sdkconfig.h"

/* Default codec volume and digital gain (dB, before a soft limiter): the model peaks near
 * -8 dBFS, and the NANO's speaker path is quieter than the panel's. */
#if defined(CONFIG_VTTS_BOARD_P4_NANO)
#define BOARD_DEFAULT_VOL 90
#define BOARD_DEFAULT_GAIN_DB 12.0f
#else
#define BOARD_DEFAULT_VOL 70
#define BOARD_DEFAULT_GAIN_DB 0.0f
#endif

/* Board name, for the boot log. */
const char *board_name(void);

/* Bring up I2C, I2S TX and the ES8311 in DAC mode. Returns NULL if any step fails. */
esp_codec_dev_handle_t board_speaker_init(void);
