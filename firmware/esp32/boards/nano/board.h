/* Waveshare ESP32-P4-NANO: ES8311 codec wired like the 86-Panel (Waveshare BSP esp32_p4_nano);
 * its speaker path is quieter, hence the higher default volume and gain. */
#pragma once
#define BSP_NAME "ESP32-P4-NANO"
#define BSP_DEFAULT_VOL 90
#define BSP_DEFAULT_GAIN_DB 12.0f
#define BSP_I2C_PORT 1
#define BSP_I2C_SDA 7
#define BSP_I2C_SCL 8
#define BSP_I2S_PORT 0
#define BSP_I2S_MCLK 13
#define BSP_I2S_BCLK 12
#define BSP_I2S_WS 10
#define BSP_I2S_DOUT 9
#define BSP_PA_EN 53
