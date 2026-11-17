set(RT ${CMAKE_CURRENT_LIST_DIR}/../../../runtime)
set(REQS esp_timer esp_driver_uart esp_driver_i2c esp_driver_i2s esp_driver_gpio esp_driver_usb_serial_jtag)
if(CMAKE_BUILD_EARLY_EXPANSION) # requirement scan: no board selection yet
    idf_component_register(PRIV_REQUIRES ${REQS})
    return()
endif()
# Board support: boards/<id>/ (board.h, board.cmake, sdkconfig.defaults); build.sh passes VTTS_BOARD.
if(NOT VTTS_BOARD)
    set(VTTS_BOARD $ENV{VTTS_BOARD})
endif()
if(NOT VTTS_BOARD)
    set(VTTS_BOARD panel)
endif()
set(BOARD_DIR ${CMAKE_CURRENT_LIST_DIR}/../boards/${VTTS_BOARD})
if(NOT EXISTS ${BOARD_DIR}/board.cmake)
    message(FATAL_ERROR "unknown board '${VTTS_BOARD}': no boards/${VTTS_BOARD}/board.cmake")
endif()
include(${BOARD_DIR}/board.cmake)
if(NOT IDF_TARGET STREQUAL BSP_TARGET)
    message(FATAL_ERROR "board '${VTTS_BOARD}' needs target ${BSP_TARGET}, not ${IDF_TARGET}")
endif()
if(IDF_TARGET STREQUAL "esp32s3")
    set(PORT "${RT}/ports/esp32s3/vtts_port_s3.c")
else()
    set(PORT "${RT}/ports/esp32p4/vtts_port_p4.c")
endif()
idf_component_register(
    SRCS "main.c" "bsp/bsp_common.c" "bsp/speaker_${BSP_SPEAKER}.c" "${PORT}"
         "${RT}/ports/freertos/vtts_par_freertos.c"
         "${RT}/src/vtts_model.c" "${RT}/src/vtts_synth.c" "${RT}/src/vtts_kernels_ref.c"
         "${RT}/src/vtts_text.c" "${RT}/src/vtts_text_en.c" "${RT}/src/vtts_lex.c"
    INCLUDE_DIRS "." "bsp" "${BOARD_DIR}" "${RT}/include" "${RT}/src"
    PRIV_REQUIRES ${REQS}
    EMBED_FILES "model_s.vtts" "model_m.vtts")
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-math-errno -Wno-unused-function -DVTTS_PROFILE
                       -DVTTS_BLOCK=64 -DVTTS_HEAD_BLOCK=16 -DVTTS_STREAM_STEP=64)
