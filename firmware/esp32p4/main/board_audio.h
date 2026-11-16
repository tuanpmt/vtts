/* SPDX-License-Identifier: Apache-2.0 */
/* board_audio.h -- speaker output (ES8311 codec + power amplifier) for the supported boards. */
#pragma once

#include "esp_codec_dev.h"

/* Board name, for the boot log. */
const char *board_name(void);

/* Bring up I2C, I2S TX and the ES8311 in DAC mode. Returns NULL if any step fails. */
esp_codec_dev_handle_t board_speaker_init(void);
