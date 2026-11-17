/* SPDX-License-Identifier: Apache-2.0 */
/* speaker_es8311.c -- ES8311 codec (I2C control, I2S data) and an amplifier enable pin.
 * Board pins: BSP_I2C_PORT, BSP_I2C_SDA, BSP_I2C_SCL, BSP_I2S_PORT, BSP_I2S_MCLK, BSP_I2S_BCLK,
 * BSP_I2S_WS, BSP_I2S_DOUT, BSP_PA_EN. */
#include "bsp.h"

#include "driver/i2c_master.h"
#include "driver/i2s_std.h"
#include "esp_codec_dev.h"
#include "esp_codec_dev_defaults.h"
#include "esp_log.h"

static const char *TAG = "bsp";
static esp_codec_dev_handle_t s_dev;

static esp_codec_dev_handle_t es8311_init(void) {
    i2c_master_bus_handle_t i2c = NULL;
    i2c_master_bus_config_t bus = {
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .sda_io_num = BSP_I2C_SDA,
        .scl_io_num = BSP_I2C_SCL,
        .i2c_port = BSP_I2C_PORT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    if (i2c_new_master_bus(&bus, &i2c) != ESP_OK) { ESP_LOGE(TAG, "i2c bus"); return NULL; }
    i2s_chan_handle_t tx = NULL;
    i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(BSP_I2S_PORT, I2S_ROLE_MASTER);
    chan.auto_clear = true;
    i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(22050), /* the codec device reconfigures it on open */
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {.mclk = BSP_I2S_MCLK, .bclk = BSP_I2S_BCLK, .ws = BSP_I2S_WS, .dout = BSP_I2S_DOUT,
                     .din = I2S_GPIO_UNUSED},
    };
    if (i2s_new_channel(&chan, &tx, NULL) != ESP_OK || i2s_channel_init_std_mode(tx, &std) != ESP_OK ||
        i2s_channel_enable(tx) != ESP_OK) {
        ESP_LOGE(TAG, "i2s tx");
        return NULL;
    }
    audio_codec_i2s_cfg_t i2s_cfg = {.port = BSP_I2S_PORT, .tx_handle = tx};
    const audio_codec_data_if_t *data_if = audio_codec_new_i2s_data(&i2s_cfg);
    audio_codec_i2c_cfg_t i2c_cfg = {.port = BSP_I2C_PORT, .addr = ES8311_CODEC_DEFAULT_ADDR, .bus_handle = i2c};
    const audio_codec_ctrl_if_t *ctrl_if = audio_codec_new_i2c_ctrl(&i2c_cfg);
    const audio_codec_gpio_if_t *gpio_if = audio_codec_new_gpio();
    if (!data_if || !ctrl_if || !gpio_if) { ESP_LOGE(TAG, "codec interfaces"); return NULL; }
    es8311_codec_cfg_t es = {
        .ctrl_if = ctrl_if,
        .gpio_if = gpio_if,
        .codec_mode = ESP_CODEC_DEV_WORK_MODE_DAC,
        .pa_pin = BSP_PA_EN,
        .use_mclk = true,
        .hw_gain = {.pa_voltage = 5.0f, .codec_dac_voltage = 3.3f},
    };
    const audio_codec_if_t *codec_if = es8311_codec_new(&es);
    if (!codec_if) { ESP_LOGE(TAG, "es8311"); return NULL; }
    esp_codec_dev_cfg_t dev = {.dev_type = ESP_CODEC_DEV_TYPE_OUT, .codec_if = codec_if, .data_if = data_if};
    return esp_codec_dev_new(&dev);
}

int bsp_speaker_open(const int *rates, int n_rates) {
    if (!s_dev) s_dev = es8311_init();
    if (!s_dev) return 0;
    for (int k = 0; k < n_rates; k++) {
        esp_codec_dev_sample_info_t fs = {.bits_per_sample = 16, .channel = 1, .sample_rate = (uint32_t)rates[k]};
        if (esp_codec_dev_open(s_dev, &fs) == ESP_CODEC_DEV_OK) return rates[k];
    }
    ESP_LOGE(TAG, "codec open failed");
    return 0;
}

void bsp_speaker_set_vol(int vol) {
    if (s_dev) esp_codec_dev_set_out_vol(s_dev, vol);
}

void bsp_speaker_write(int16_t *pcm, int n) {
    if (s_dev) esp_codec_dev_write(s_dev, pcm, n * (int)sizeof(int16_t));
}
