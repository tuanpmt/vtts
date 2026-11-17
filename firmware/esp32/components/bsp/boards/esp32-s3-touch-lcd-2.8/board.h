/* Waveshare ESP32-S3-Touch-LCD-2.8: PCM5101 I2S DAC (no control bus, no MCLK), pins from
 * Waveshare's pin table for the board; GPIO7 latches the power (high = on). */
#pragma once
#include "driver/i2s_types.h"
#define BSP_NAME "ESP32-S3-Touch-LCD-2.8"
#define BSP_DEFAULT_VOL 80
#define BSP_DEFAULT_GAIN_DB 6.0f
#define BSP_POWER_HOLD_GPIO 7
#define BSP_I2S_PORT 1
#define BSP_I2S_MCLK I2S_GPIO_UNUSED
#define BSP_I2S_BCLK 48
#define BSP_I2S_WS 38
#define BSP_I2S_DOUT 47
#define BSP_DAC_UPSAMPLE 2
