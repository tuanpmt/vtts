set(BSP_TARGET esp32s31)
set(BSP_SPEAKER bt_audio)
list(APPEND BSP_EXTRA_SRCS "drivers/tca9555.c")
