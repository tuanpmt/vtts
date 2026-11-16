/* SPDX-License-Identifier: Apache-2.0 */
/* board_audio.c -- speaker path without a full board support package.
 *
 * P4 boards: ES8311 codec over I2C + I2S, pins from the boards' schematics as published in
 * Waveshare's (Apache-2.0) BSPs esp32_p4_wifi6_touch_lcd_4b and esp32_p4_nano; both boards wire
 * the codec the same way.
 * ESP32-S3-Touch-LCD-2.8: PCM5101 DAC driven straight from I2S (no control bus, no MCLK), pins
 * from Waveshare's published pin table for the board; volume is a digital scale.
 * To add a board, add a Kconfig choice and a pin block below. */
#include "board_audio.h"

#include <math.h>

#include "driver/gpio.h"
#include "driver/i2s_std.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "sdkconfig.h"

static const char *TAG = "board";

#if defined(CONFIG_VTTS_BOARD_S3_TOUCH_LCD_28)
#define BOARD_NAME "ESP32-S3-Touch-LCD-2.8"
#define USE_ES8311 0
#define PIN_I2S_MCLK I2S_GPIO_UNUSED
#define PIN_I2S_BCLK 48
#define PIN_I2S_WS 38
#define PIN_I2S_DOUT 47
#define PIN_PWR_HOLD 7 /* power latch, high = on (as in Waveshare's demo) */
#define I2S_PORT 1
#else
#if defined(CONFIG_VTTS_BOARD_P4_NANO)
#define BOARD_NAME "ESP32-P4-NANO"
#else
#define BOARD_NAME "ESP32-P4-86-Panel"
#endif
/* ES8311 control (I2C), I2S data and amplifier enable: identical on both P4 boards */
#define USE_ES8311 1
#define PIN_I2C_SDA 7
#define PIN_I2C_SCL 8
#define PIN_I2S_MCLK 13
#define PIN_I2S_BCLK 12
#define PIN_I2S_WS 10
#define PIN_I2S_DOUT 9
#define PIN_PA_EN 53
#define I2S_PORT 0
#define I2C_PORT 1
#endif

const char *board_name(void) { return BOARD_NAME; }

static i2s_chan_handle_t i2s_tx(int rate) {
    i2s_chan_handle_t tx = NULL;
    i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_PORT, I2S_ROLE_MASTER);
    chan.auto_clear = true;
    i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(rate),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {.mclk = PIN_I2S_MCLK, .bclk = PIN_I2S_BCLK, .ws = PIN_I2S_WS, .dout = PIN_I2S_DOUT,
                     .din = I2S_GPIO_UNUSED},
    };
#if !USE_ES8311
    std.slot_cfg.slot_mask = I2S_STD_SLOT_BOTH; /* the DAC's amplifier is not on the left slot only */
#endif
    if (i2s_new_channel(&chan, &tx, NULL) != ESP_OK || i2s_channel_init_std_mode(tx, &std) != ESP_OK ||
        i2s_channel_enable(tx) != ESP_OK) {
        ESP_LOGE(TAG, "i2s tx");
        return NULL;
    }
    return tx;
}

#if USE_ES8311
#include "driver/i2c_master.h"
#include "esp_codec_dev.h"
#include "esp_codec_dev_defaults.h"

static esp_codec_dev_handle_t s_dev;

static esp_codec_dev_handle_t es8311_init(void) {
    i2c_master_bus_handle_t i2c = NULL;
    i2c_master_bus_config_t bus = {
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .sda_io_num = PIN_I2C_SDA,
        .scl_io_num = PIN_I2C_SCL,
        .i2c_port = I2C_PORT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    if (i2c_new_master_bus(&bus, &i2c) != ESP_OK) { ESP_LOGE(TAG, "i2c bus"); return NULL; }
    i2s_chan_handle_t tx = i2s_tx(22050); /* the codec device reconfigures the clock on open */
    if (!tx) return NULL;
    audio_codec_i2s_cfg_t i2s_cfg = {.port = I2S_PORT, .tx_handle = tx};
    const audio_codec_data_if_t *data_if = audio_codec_new_i2s_data(&i2s_cfg);
    audio_codec_i2c_cfg_t i2c_cfg = {.port = I2C_PORT, .addr = ES8311_CODEC_DEFAULT_ADDR, .bus_handle = i2c};
    const audio_codec_ctrl_if_t *ctrl_if = audio_codec_new_i2c_ctrl(&i2c_cfg);
    const audio_codec_gpio_if_t *gpio_if = audio_codec_new_gpio();
    if (!data_if || !ctrl_if || !gpio_if) { ESP_LOGE(TAG, "codec interfaces"); return NULL; }
    es8311_codec_cfg_t es = {
        .ctrl_if = ctrl_if,
        .gpio_if = gpio_if,
        .codec_mode = ESP_CODEC_DEV_WORK_MODE_DAC,
        .pa_pin = PIN_PA_EN,
        .use_mclk = true,
        .hw_gain = {.pa_voltage = 5.0f, .codec_dac_voltage = 3.3f},
    };
    const audio_codec_if_t *codec_if = es8311_codec_new(&es);
    if (!codec_if) { ESP_LOGE(TAG, "es8311"); return NULL; }
    esp_codec_dev_cfg_t dev = {.dev_type = ESP_CODEC_DEV_TYPE_OUT, .codec_if = codec_if, .data_if = data_if};
    return esp_codec_dev_new(&dev);
}

int board_speaker_open(const int *rates, int n_rates) {
    if (!s_dev) s_dev = es8311_init();
    if (!s_dev) return 0;
    for (int k = 0; k < n_rates; k++) {
        esp_codec_dev_sample_info_t fs = {.bits_per_sample = 16, .channel = 1, .sample_rate = (uint32_t)rates[k]};
        if (esp_codec_dev_open(s_dev, &fs) == ESP_CODEC_DEV_OK) return rates[k];
    }
    ESP_LOGE(TAG, "codec open failed");
    return 0;
}

void board_speaker_set_vol(int vol) {
    if (s_dev) esp_codec_dev_set_out_vol(s_dev, vol);
}

void board_speaker_write(int16_t *pcm, int n) {
    if (s_dev) esp_codec_dev_write(s_dev, pcm, n * (int)sizeof(int16_t));
}

#else /* plain I2S DAC */

static i2s_chan_handle_t s_tx;
static int32_t s_scale = 1 << 15; /* Q15 digital volume */
static int16_t s_prev;            /* last input sample, for the 2x interpolation */

/* The DAC runs at twice the requested rate (44.1 kHz for the models' 22.05 kHz, as in
 * Waveshare's demo) and board_speaker_write interpolates 2x. */
int board_speaker_open(const int *rates, int n_rates) {
    if (!s_tx && n_rates > 0) {
        gpio_config_t io = {.pin_bit_mask = 1ULL << PIN_PWR_HOLD, .mode = GPIO_MODE_OUTPUT};
        gpio_config(&io);
        gpio_set_level(PIN_PWR_HOLD, 1);
        s_tx = i2s_tx(2 * rates[0]);
    }
    return s_tx ? rates[0] : 0;
}

void board_speaker_set_vol(int vol) {
    vol = vol < 0 ? 0 : vol > 100 ? 100 : vol;
    /* 40 dB of range in even dB steps */
    s_scale = vol ? (int32_t)lrintf(32768.0f * powf(10.0f, (vol - 100) * 0.4f / 20.0f)) : 0;
    if (s_scale > 32768) s_scale = 32768;
}

void board_speaker_write(int16_t *pcm, int n) {
    if (!s_tx) return;
    static int16_t up[2 * 256];
    for (int i = 0; i < n;) {
        int k = 0;
        for (; k < 256 && i < n; k++, i++) {
            int16_t v = (int16_t)(((int32_t)pcm[i] * s_scale) >> 15);
            up[2 * k] = (int16_t)(((int32_t)s_prev + v) / 2);
            up[2 * k + 1] = v;
            s_prev = v;
        }
        size_t done;
        i2s_channel_write(s_tx, up, (size_t)k * 2 * sizeof(int16_t), &done, portMAX_DELAY);
    }
}
#endif
