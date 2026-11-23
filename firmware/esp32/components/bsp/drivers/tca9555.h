/* SPDX-License-Identifier: Apache-2.0 */
/* tca9555.h -- minimal TCA9555 / PCA9555 16-bit I2C I/O expander driver: outputs only.
 * Pin numbers are 0..15: P0.0..P0.7 are 0..7, P1.0..P1.7 are 8..15. */
#pragma once

#include <stdint.h>

#include "driver/i2c_master.h"
#include "esp_err.h"

typedef struct {
    i2c_master_dev_handle_t dev;
    uint8_t addr;   /* 7-bit address in use */
    uint16_t out;   /* output latch shadow (bit = pin) */
    uint16_t dir;   /* configuration shadow: 1 = input, 0 = output (power-on: all inputs) */
} tca9555_t;

/* Attach to the expander at addr on bus (0: probe 0x20..0x27, the address range of the chip) and read
 * its output and configuration registers into the shadows. Nothing is driven yet. */
esp_err_t tca9555_init(tca9555_t *t, i2c_master_bus_handle_t bus, uint8_t addr);

/* Make the pins in mask outputs with the levels in value (bit = pin); other pins keep their state.
 * The output latch is written before the direction, so a pin never drives its previous level. */
esp_err_t tca9555_set_outputs(tca9555_t *t, uint16_t mask, uint16_t value);

/* Drive one output pin (already made an output by tca9555_set_outputs) high or low. */
esp_err_t tca9555_set_level(tca9555_t *t, int pin, int level);
