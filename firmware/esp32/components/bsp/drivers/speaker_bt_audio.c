/* SPDX-License-Identifier: Apache-2.0 */
/* speaker_bt_audio.c -- speaker behind an external Bluetooth audio chip that owns the I2S link (the
 * Metalio E-INK4-Plus "ble_chip"): the chip is the I2S master at a fixed rate (BSP_I2S_RATE, 16 kHz),
 * takes AT commands on a UART, and plays through an amplifier (NS4150) whose enable pin and the chip's
 * power rail sit on a TCA9555 I/O expander.
 *
 * Bring-up, as the board's own firmware does it (CloudZao/Metalio-E-INK4-Plus:
 * main/boards/metalio-e-ink4-plus/periph/metalio_audio.cc, main/boards/common/audio/bt_audio_codec.cc,
 * docs/ble_chip-audio-protocol.md):
 *   1. expander outputs BSP_IOEXP_OUT_INIT on BSP_IOEXP_OUT_MASK (audio chip rail on, amplifier off)
 *   2. let the chip start (BSP_BT_SETTLE_MS after its rail came up)
 *   3. mode 1 "local audio" (amplifier playback): AT+RX=2, 700 ms, AT+MODE=1, reply "SET MODE 1"
 *      within 1 s; up to 3 retries 1 s apart
 *   4. I2S slave TX: 32-bit stereo Philips slots, the mono sample in both slots
 *   5. amplifier on (BSP_IOEXP_PA_EN)
 * The I2S rate is fixed, so bsp_speaker_open returns BSP_I2S_RATE whatever rates are asked for; the
 * firmware resamples (main/speaker.c). Volume is a digital scale. When the chip sends no clock (not
 * powered, wrong mode) writes time out instead of blocking forever, and playback is skipped for a while.
 *
 * Board macros: BSP_I2C_PORT, BSP_I2C_SDA, BSP_I2C_SCL, BSP_IOEXP_ADDR (0: probe), BSP_IOEXP_OUT_MASK,
 * BSP_IOEXP_OUT_INIT, BSP_IOEXP_PA_EN, BSP_IOEXP_BT_PWR (expander pins 0..15), BSP_I2S_PORT, BSP_I2S_BCLK, BSP_I2S_WS, BSP_I2S_DOUT,
 * BSP_I2S_RATE, BSP_BT_UART_PORT, BSP_BT_UART_TX, BSP_BT_UART_RX; optional BSP_BT_UART_BAUD (115200),
 * BSP_BT_SETTLE_MS (700). */
#include "bsp.h"

#include <math.h>
#include <string.h>

#include "driver/i2c_master.h"
#include "driver/i2s_std.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "tca9555.h"

#ifndef BSP_BT_UART_BAUD
#define BSP_BT_UART_BAUD 115200
#endif
#ifndef BSP_BT_SETTLE_MS
#define BSP_BT_SETTLE_MS 700
#endif
#define BT_RETRIES 3
#define BT_ACK_MS 1000
#define I2S_WRITE_TIMEOUT_MS 200 /* a 128-frame block lasts 8 ms at 16 kHz */
#define NO_CLOCK_BACKOFF_US 2000000

static const char *TAG = "bsp";
static tca9555_t s_io;
static int s_io_ok;
static i2s_chan_handle_t s_tx;
static int32_t s_scale = 1 << 15; /* Q15 digital volume */
static int64_t s_skip_until;      /* no I2S clock: skip writes until then (esp_timer us) */

static void delay_ms(int ms) { vTaskDelay(pdMS_TO_TICKS(ms) ? pdMS_TO_TICKS(ms) : 1); }

/* --- expander: audio rail and amplifier --- */

static void ioexp_init(void) {
    i2c_master_bus_handle_t bus = NULL;
    i2c_master_bus_config_t cfg = {
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .sda_io_num = BSP_I2C_SDA,
        .scl_io_num = BSP_I2C_SCL,
        .i2c_port = BSP_I2C_PORT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    if (i2c_new_master_bus(&cfg, &bus) != ESP_OK) { ESP_LOGE(TAG, "i2c bus"); return; }
    esp_err_t err = tca9555_init(&s_io, bus, BSP_IOEXP_ADDR);
    if (err != ESP_OK) { ESP_LOGE(TAG, "TCA9555 not found: %s", esp_err_to_name(err)); return; }
    /* was the chip's rail already driven on (a soft reset keeps the expander's state)? */
    const uint16_t rail = (uint16_t)(1u << BSP_IOEXP_BT_PWR);
    const int was_on = (s_io.dir & rail) == 0 && (s_io.out & rail) != 0;
    err = tca9555_set_outputs(&s_io, (uint16_t)BSP_IOEXP_OUT_MASK, (uint16_t)(BSP_IOEXP_OUT_INIT & ~(1u << BSP_IOEXP_PA_EN)));
    if (err != ESP_OK) { ESP_LOGE(TAG, "TCA9555 at 0x%02x: %s", s_io.addr, esp_err_to_name(err)); return; }
    s_io_ok = 1;
    printf("bsp: TCA9555 at 0x%02x, outputs 0x%04x of 0x%04x, audio rail %s\n", s_io.addr, s_io.out,
           (unsigned)BSP_IOEXP_OUT_MASK, was_on ? "was on" : "switched on");
    int64_t since_ms = was_on ? esp_timer_get_time() / 1000 : 0; /* time the chip has been running, at least */
    if (since_ms < BSP_BT_SETTLE_MS) delay_ms(BSP_BT_SETTLE_MS - (int)since_ms);
}

static void amp_enable(int on) {
    if (s_io_ok && tca9555_set_level(&s_io, BSP_IOEXP_PA_EN, on) != ESP_OK) ESP_LOGW(TAG, "amplifier enable");
}

/* --- audio chip: AT commands on the UART --- */

static char s_line[128];
static int s_line_n;

/* Read for up to ms and return 1 at a line that contains want (exact: followed by the end or a space),
 * -1 at a line with ERROR or FAIL, 0 at the timeout. The matching line is copied to got (if given). */
static int bt_wait(const char *want, int exact, int ms, char *got, size_t got_n) {
    const int64_t end = esp_timer_get_time() + (int64_t)ms * 1000;
    uint8_t c;
    while (esp_timer_get_time() < end) {
        if (uart_read_bytes(BSP_BT_UART_PORT, &c, 1, pdMS_TO_TICKS(10)) != 1) continue;
        if (c != '\r' && c != '\n') {
            if (c >= 32 && c < 127 && s_line_n + 1 < (int)sizeof s_line) s_line[s_line_n++] = (char)c;
            continue;
        }
        s_line[s_line_n] = 0;
        int n = s_line_n;
        s_line_n = 0;
        if (!n) continue;
        if (strstr(s_line, "ERROR") || strstr(s_line, "FAIL")) return -1;
        const char *p = want ? strstr(s_line, want) : NULL;
        if (p && (!exact || p[strlen(want)] == 0 || p[strlen(want)] == ' ')) {
            if (got && got_n) { strncpy(got, p, got_n - 1); got[got_n - 1] = 0; }
            return 1;
        }
    }
    return 0;
}

static void bt_send(const char *cmd) { uart_write_bytes(BSP_BT_UART_PORT, cmd, strlen(cmd)); }

static int bt_init(void) {
    uart_config_t cfg = {
        .baud_rate = BSP_BT_UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    if (uart_driver_install(BSP_BT_UART_PORT, 1024, 0, 0, NULL, 0) != ESP_OK ||
        uart_param_config(BSP_BT_UART_PORT, &cfg) != ESP_OK ||
        uart_set_pin(BSP_BT_UART_PORT, BSP_BT_UART_TX, BSP_BT_UART_RX, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE) != ESP_OK) {
        ESP_LOGE(TAG, "audio chip uart");
        return 0;
    }
    for (int attempt = 0; attempt <= BT_RETRIES; attempt++) {
        if (attempt) delay_ms(1000);
        uart_flush_input(BSP_BT_UART_PORT);
        s_line_n = 0;
        bt_send("AT+RX=2\r\n");
        if (bt_wait(NULL, 0, 700, NULL, 0) < 0) continue; /* the chip needs 700 ms before the mode command */
        bt_send("AT+MODE=1\r\n");
        if (bt_wait("SET MODE 1", 1, BT_ACK_MS, NULL, 0) == 1) {
            char ver[64] = "";
            bt_send("AT+GVER=1\r\n");
            bt_wait("AT+GVER=V", 0, 300, ver, sizeof ver); /* the reply is "AT+GVER=V<version>" */
            printf("bsp: audio chip in mode 1 (local audio)%s%s\n", ver[0] ? ", " : "", ver);
            return 1;
        }
        ESP_LOGW(TAG, "audio chip: no SET MODE 1 (attempt %d of %d)", attempt + 1, BT_RETRIES + 1);
    }
    return 0;
}

/* --- I2S (slave: the audio chip drives BCLK and WS) --- */

static int i2s_init(void) {
    i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(BSP_I2S_PORT, I2S_ROLE_SLAVE);
    chan.auto_clear = true; /* silence when the stream runs dry */
    i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(BSP_I2S_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {.mclk = I2S_GPIO_UNUSED, .bclk = BSP_I2S_BCLK, .ws = BSP_I2S_WS, .dout = BSP_I2S_DOUT,
                     .din = I2S_GPIO_UNUSED},
    };
    if (i2s_new_channel(&chan, &s_tx, NULL) != ESP_OK) { s_tx = NULL; return 0; }
    if (i2s_channel_init_std_mode(s_tx, &std) != ESP_OK || i2s_channel_enable(s_tx) != ESP_OK) {
        i2s_del_channel(s_tx);
        s_tx = NULL;
        return 0;
    }
    return 1;
}

int bsp_speaker_open(const int *rates, int n_rates) {
    (void)rates;
    (void)n_rates;
    if (s_tx) return BSP_I2S_RATE;
    ioexp_init();
    if (!bt_init()) ESP_LOGW(TAG, "audio chip did not confirm mode 1; trying I2S anyway");
    if (!i2s_init()) { ESP_LOGE(TAG, "i2s tx"); return 0; }
    amp_enable(1);
    return BSP_I2S_RATE;
}

void bsp_speaker_set_vol(int vol) {
    vol = vol < 0 ? 0 : vol > 100 ? 100 : vol;
    /* 40 dB of range in even dB steps (like speaker_i2s_dac.c) */
    s_scale = vol ? (int32_t)lrintf(32768.0f * powf(10.0f, (vol - 100) * 0.4f / 20.0f)) : 0;
    if (s_scale > 32768) s_scale = 32768;
}

void bsp_speaker_write(int16_t *pcm, int n) {
    if (!s_tx || esp_timer_get_time() < s_skip_until) return;
    static int32_t frames[2 * 128];
    for (int i = 0; i < n;) {
        int k = 0;
        for (; k < 128 && i < n; k++, i++) {
            int32_t v = (int32_t)((int64_t)pcm[i] * s_scale * 2); /* 16-bit sample, Q15 scale -> top of 32 bits */
            frames[2 * k] = frames[2 * k + 1] = v;
        }
        size_t done = 0;
        esp_err_t err = i2s_channel_write(s_tx, frames, (size_t)k * 2 * sizeof(int32_t), &done, pdMS_TO_TICKS(I2S_WRITE_TIMEOUT_MS));
        if (err == ESP_ERR_TIMEOUT) {
            ESP_LOGW(TAG, "no I2S clock from the audio chip: playback skipped for 2 s");
            s_skip_until = esp_timer_get_time() + NO_CLOCK_BACKOFF_US;
            return;
        }
    }
}
