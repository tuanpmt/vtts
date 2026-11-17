set(RT ${CMAKE_CURRENT_LIST_DIR}/../../../runtime)
if(IDF_TARGET STREQUAL "esp32s3")
    set(PORT "${RT}/ports/esp32s3/vtts_port_s3.c")
else()
    set(PORT "${RT}/ports/esp32p4/vtts_port_p4.c")
endif()
idf_component_register(
    SRCS "main.c" "board_audio.c" "${PORT}" "${RT}/ports/freertos/vtts_par_freertos.c"
         "${RT}/src/vtts_model.c" "${RT}/src/vtts_synth.c" "${RT}/src/vtts_kernels_ref.c"
         "${RT}/src/vtts_text.c"
    INCLUDE_DIRS "." "${RT}/include" "${RT}/src"
    PRIV_REQUIRES esp_timer esp_driver_uart esp_driver_i2c esp_driver_i2s esp_driver_gpio
                  esp_driver_usb_serial_jtag
    EMBED_FILES "model_s.vtts" "model_m.vtts")
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-math-errno -Wno-unused-function -DVTTS_PROFILE
                       -DVTTS_BLOCK=64 -DVTTS_HEAD_BLOCK=16 -DVTTS_STREAM_STEP=64)
