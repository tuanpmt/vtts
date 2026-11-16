/* SPDX-License-Identifier: Apache-2.0 */
/* board_audio.c -- ES8311 speaker path without a full board support package.
 *
 * Pin numbers come from the boards' schematics as published in Waveshare's (Apache-2.0) BSPs
 * esp32_p4_wifi6_touch_lcd_4b and esp32_p4_nano; both boards wire the codec the same way.
 * To add a board, add a Kconfig choice and a pin block below. */
#include "board_audio.h"

#include "driver/i2c_master.h"
#include "driver/i2s_std.h"
#include "esp_codec_dev_defaults.h"
#include "esp_log.h"
#include "sdkconfig.h"

#if defined(CONFIG_VTTS_BOARD_P4_NANO)
#define BOARD_NAME "ESP32-P4-NANO"
#else
#define BOARD_NAME "ESP32-P4-86-Panel"
#endif

/* ES8311 control (I2C), I2S data and amplifier enable: identical on both supported boards */
#define PIN_I2C_SDA 7
#define PIN_I2C_SCL 8
#define PIN_I2S_MCLK 13
#define PIN_I2S_BCLK 12
#define PIN_I2S_WS 10
#define PIN_I2S_DOUT 9
#define PIN_PA_EN 53
#define I2S_PORT 0
#define I2C_PORT 1
#define I2S_INIT_RATE 22050 /* the codec device reconfigures the clock on open */

static const char *TAG = "board";

const char *board_name(void) { return BOARD_NAME; }

esp_codec_dev_handle_t board_speaker_init(void) {
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

    i2s_chan_handle_t tx = NULL;
    i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_PORT, I2S_ROLE_MASTER);
    chan.auto_clear = true;
    i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(I2S_INIT_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {.mclk = PIN_I2S_MCLK, .bclk = PIN_I2S_BCLK, .ws = PIN_I2S_WS, .dout = PIN_I2S_DOUT,
                     .din = I2S_GPIO_UNUSED},
    };
    if (i2s_new_channel(&chan, &tx, NULL) != ESP_OK || i2s_channel_init_std_mode(tx, &std) != ESP_OK ||
        i2s_channel_enable(tx) != ESP_OK) {
        ESP_LOGE(TAG, "i2s tx");
        return NULL;
    }

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
