/* SPDX-License-Identifier: Apache-2.0 */
/* bsp_common.c -- board-independent parts of the BSP. */
#include "bsp.h"

#include "driver/gpio.h"

const char *bsp_name(void) { return BSP_NAME; }

void bsp_early_init(void) {
#ifdef BSP_POWER_HOLD_GPIO
    gpio_config_t io = {.pin_bit_mask = 1ULL << BSP_POWER_HOLD_GPIO, .mode = GPIO_MODE_OUTPUT};
    gpio_config(&io);
    gpio_set_level(BSP_POWER_HOLD_GPIO, 1);
#endif
}
