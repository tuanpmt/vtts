/* EchoEar 2.0: ESP32-S3-WROOM-1 N16R8, ES8311 codec + NS4150B amplifier. GPIO7 (PG2) latches
 * the power and must be driven high right after boot. */
#pragma once
#define BSP_NAME "EchoEar 2.0"
#define BSP_DEFAULT_VOL 75
#define BSP_DEFAULT_GAIN_DB 6.0f
#define BSP_POWER_HOLD_GPIO 7
#define BSP_I2C_PORT 0
#define BSP_I2C_SDA 2
#define BSP_I2C_SCL 1
#define BSP_I2S_PORT 0
#define BSP_I2S_MCLK 42
#define BSP_I2S_BCLK 40
#define BSP_I2S_WS 39
#define BSP_I2S_DOUT 41
#define BSP_PA_EN 4
