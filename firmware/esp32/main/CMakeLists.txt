set(RT ${CMAKE_CURRENT_LIST_DIR}/../../../runtime)
set(REQS bsp console esp_timer esp_driver_uart esp_driver_i2c esp_driver_i2s esp_driver_gpio esp_driver_usb_serial_jtag)
if(CMAKE_BUILD_EARLY_EXPANSION) # requirement scan: no board selection yet
    idf_component_register(PRIV_REQUIRES ${REQS})
    return()
endif()
if(IDF_TARGET STREQUAL "esp32s3")
    set(PORT "${RT}/ports/esp32s3/vtts_port_s3.c")
else()
    set(PORT "${RT}/ports/esp32p4/vtts_port_p4.c")
endif()
idf_component_register(
    SRCS "main.c" "synth.c" "speaker.c" "console.c" "selftest.c" "${PORT}"
         "${RT}/ports/freertos/vtts_par_freertos.c"
         "${RT}/src/vtts_model.c" "${RT}/src/vtts_synth.c" "${RT}/src/vtts_kernels_ref.c"
         "${RT}/src/vtts_text.c" "${RT}/src/vtts_text_en.c" "${RT}/src/vtts_lex.c"
    INCLUDE_DIRS "." "${RT}/include" "${RT}/src"
    PRIV_REQUIRES ${REQS}
    EMBED_FILES "model_s.vtts" "model_m.vtts" "lex_en.bin")
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-math-errno -Wno-unused-function -DVTTS_PROFILE
                       -DVTTS_BLOCK=64 -DVTTS_HEAD_BLOCK=16 -DVTTS_STREAM_STEP=64)
