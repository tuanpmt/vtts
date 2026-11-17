/* SPDX-License-Identifier: Apache-2.0 */
/* speaker_i2s_dac.c -- a plain I2S DAC with its own amplifier (e.g. PCM5101): no control bus,
 * volume as a digital scale. The DAC runs at BSP_DAC_UPSAMPLE times the requested rate and the
 * samples are interpolated linearly (2x gives 44.1 kHz for the models' 22.05 kHz).
 * Board pins: BSP_I2S_PORT, BSP_I2S_MCLK (or I2S_GPIO_UNUSED), BSP_I2S_BCLK, BSP_I2S_WS,
 * BSP_I2S_DOUT. Both slots carry the sample (some amplifiers do not listen to the left one). */
#include "bsp.h"

#include <math.h>

#include "driver/i2s_std.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"

#ifndef BSP_DAC_UPSAMPLE
#define BSP_DAC_UPSAMPLE 2
#endif

static const char *TAG = "bsp";
static i2s_chan_handle_t s_tx;
static int32_t s_scale = 1 << 15; /* Q15 digital volume */
static int16_t s_prev;            /* last input sample, for the interpolation */

int bsp_speaker_open(const int *rates, int n_rates) {
    if (!s_tx && n_rates > 0) {
        i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(BSP_I2S_PORT, I2S_ROLE_MASTER);
        chan.auto_clear = true;
        i2s_std_config_t std = {
            .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(BSP_DAC_UPSAMPLE * rates[0]),
            .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
            .gpio_cfg = {.mclk = BSP_I2S_MCLK, .bclk = BSP_I2S_BCLK, .ws = BSP_I2S_WS, .dout = BSP_I2S_DOUT,
                         .din = I2S_GPIO_UNUSED},
        };
        std.slot_cfg.slot_mask = I2S_STD_SLOT_BOTH;
        if (i2s_new_channel(&chan, &s_tx, NULL) != ESP_OK || i2s_channel_init_std_mode(s_tx, &std) != ESP_OK ||
            i2s_channel_enable(s_tx) != ESP_OK) {
            ESP_LOGE(TAG, "i2s tx");
            s_tx = NULL;
        }
    }
    return s_tx ? rates[0] : 0;
}

void bsp_speaker_set_vol(int vol) {
    vol = vol < 0 ? 0 : vol > 100 ? 100 : vol;
    /* 40 dB of range in even dB steps */
    s_scale = vol ? (int32_t)lrintf(32768.0f * powf(10.0f, (vol - 100) * 0.4f / 20.0f)) : 0;
    if (s_scale > 32768) s_scale = 32768;
}

void bsp_speaker_write(int16_t *pcm, int n) {
    if (!s_tx) return;
    static int16_t up[BSP_DAC_UPSAMPLE * 256];
    for (int i = 0; i < n;) {
        int k = 0;
        for (; k < 256 && i < n; k++, i++) {
            int16_t v = (int16_t)(((int32_t)pcm[i] * s_scale) >> 15);
            for (int u = 0; u < BSP_DAC_UPSAMPLE; u++)
                up[BSP_DAC_UPSAMPLE * k + u] = (int16_t)(s_prev + ((int32_t)(v - s_prev) * (u + 1)) / BSP_DAC_UPSAMPLE);
            s_prev = v;
        }
        size_t done;
        i2s_channel_write(s_tx, up, (size_t)k * BSP_DAC_UPSAMPLE * sizeof(int16_t), &done, portMAX_DELAY);
    }
}
