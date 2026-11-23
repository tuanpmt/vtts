/* Metalio E-INK4-Plus (CloudZao): ESP32-S31, 16 MB flash, octal PSRAM at 200 MHz. The speaker sits
 * behind an external Bluetooth audio chip ("ble_chip", I2S master at a fixed 16 kHz, AT commands on
 * UART1) with an NS4150 amplifier; the amplifier enable (P0.4) and the chip's power rail (P1.4) are on
 * a TCA9555 at 0x20 on I2C1 (shared with the FT6336U touch at 0x38, the TPS65185 e-paper PMIC, ...).
 * Pins from github.com/CloudZao/Metalio-E-INK4-Plus main/boards/metalio-e-ink4-plus/config.h (hardware
 * 1.4); expander use from display/epd_board_metalio_eink4_plus.c there. Speaker path tested on a rev v0.0 board. */
#pragma once
#define BSP_NAME "Metalio E-INK4-Plus"
#define BSP_DEFAULT_VOL 90
#define BSP_DEFAULT_GAIN_DB 0.0f
/* ANA_SW: high routes the USB-C port to the chip's USB-Serial-JTAG (the console); low = USB HS (MSC) */
#define BSP_USB_SWITCH_GPIO 36
#define BSP_USB_SWITCH_LEVEL 1
/* I2C1 and the TCA9555 (0: probe 0x20..0x27; the board firmware finds it at 0x20) */
#define BSP_I2C_PORT 1
#define BSP_I2C_SDA 0
#define BSP_I2C_SCL 1
#define BSP_IOEXP_ADDR 0
/* expander pins (P0.n = n, P1.n = 8 + n): P0.0-P0.2 TPS65185 VCOM_CTRL / PWRUP / WAKEUP (low: panel
 * power off), P0.3 vibration motor, P0.4 PA_EN (NS4150), P0.5 camera / screen power, P1.2 touch and 4G
 * reset (high: run), P1.3 power-off pulse (low), P1.4 power of the 4G modem, audio chip and amplifier.
 * The same outputs and levels as the board firmware's start-up, with the amplifier switched on last. */
#define BSP_IOEXP_PA_EN 4
#define BSP_IOEXP_BT_PWR 12
#define BSP_IOEXP_OUT_MASK 0x1C3F
#define BSP_IOEXP_OUT_INIT ((1u << 5) | (1u << 4) | (1u << 10) | (1u << 12))
/* I2S0 as slave of the audio chip (BCLK and WS come from it), playback only */
#define BSP_I2S_PORT 0
#define BSP_I2S_BCLK 42
#define BSP_I2S_WS 43
#define BSP_I2S_DOUT 44
#define BSP_I2S_RATE 16000
/* audio chip control: UART1 115200 8N1 (ESP TX = GPIO39, RX = GPIO38) */
#define BSP_BT_UART_PORT 1
#define BSP_BT_UART_TX 39
#define BSP_BT_UART_RX 38
#define BSP_BT_SETTLE_MS 700
