/* SPDX-License-Identifier: Apache-2.0 */
/* tca9555.c -- minimal TCA9555 / PCA9555 I/O expander driver (tca9555.h). Registers: 0/1 input,
 * 2/3 output latch, 4/5 polarity inversion, 6/7 configuration (1 = input), port 0 then port 1. */
#include "tca9555.h"

#define REG_OUT0 2
#define REG_CFG0 6
#define I2C_HZ 100000
#define I2C_TIMEOUT_MS 50

static esp_err_t write_pair(tca9555_t *t, uint8_t reg, uint16_t v) {
    uint8_t b[3] = {reg, (uint8_t)(v & 0xff), (uint8_t)(v >> 8)}; /* the register pointer advances to port 1 */
    return i2c_master_transmit(t->dev, b, sizeof b, I2C_TIMEOUT_MS);
}

/* pointer write, STOP, then the read (the board's own firmware reads this way, not with a repeated START) */
static esp_err_t read_pair(tca9555_t *t, uint8_t reg, uint16_t *v) {
    uint8_t b[2];
    esp_err_t err = i2c_master_transmit(t->dev, &reg, 1, I2C_TIMEOUT_MS);
    if (err == ESP_OK) err = i2c_master_receive(t->dev, b, sizeof b, I2C_TIMEOUT_MS);
    if (err == ESP_OK) *v = (uint16_t)(b[0] | b[1] << 8);
    return err;
}

esp_err_t tca9555_init(tca9555_t *t, i2c_master_bus_handle_t bus, uint8_t addr) {
    t->dev = NULL;
    uint8_t lo = addr ? addr : 0x20, hi = addr ? addr : 0x27;
    for (uint8_t a = lo; a <= hi; a++) {
        if (i2c_master_probe(bus, a, I2C_TIMEOUT_MS) != ESP_OK) continue;
        i2c_device_config_t cfg = {.dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = a, .scl_speed_hz = I2C_HZ};
        esp_err_t err = i2c_master_bus_add_device(bus, &cfg, &t->dev);
        if (err != ESP_OK) return err;
        t->addr = a;
        if ((err = read_pair(t, REG_OUT0, &t->out)) != ESP_OK || (err = read_pair(t, REG_CFG0, &t->dir)) != ESP_OK) {
            i2c_master_bus_rm_device(t->dev);
            t->dev = NULL;
            return err;
        }
        return ESP_OK;
    }
    return ESP_ERR_NOT_FOUND;
}

esp_err_t tca9555_set_outputs(tca9555_t *t, uint16_t mask, uint16_t value) {
    if (!t->dev) return ESP_ERR_INVALID_STATE;
    uint16_t out = (uint16_t)((t->out & ~mask) | (value & mask)), dir = (uint16_t)(t->dir & ~mask);
    esp_err_t err = write_pair(t, REG_OUT0, out);
    if (err == ESP_OK) t->out = out;
    if (err == ESP_OK && dir != t->dir && (err = write_pair(t, REG_CFG0, dir)) == ESP_OK) t->dir = dir;
    return err;
}

esp_err_t tca9555_set_level(tca9555_t *t, int pin, int level) {
    if (pin < 0 || pin > 15) return ESP_ERR_INVALID_ARG;
    uint16_t bit = (uint16_t)(1u << pin);
    if (!t->dev) return ESP_ERR_INVALID_STATE;
    uint16_t out = (uint16_t)(level ? t->out | bit : t->out & ~bit);
    esp_err_t err = out == t->out ? ESP_OK : write_pair(t, REG_OUT0, out);
    if (err == ESP_OK) t->out = out;
    return err;
}
