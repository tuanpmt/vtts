# Board support package: shared speaker drivers (drivers/) and one folder per board (boards/<id>/).
# The board comes from VTTS_BOARD (build.sh: BOARD=<id>); see README.md.
set(REQS esp_driver_gpio esp_driver_i2s esp_driver_i2c)
if(CMAKE_BUILD_EARLY_EXPANSION) # requirement scan: no board selection yet
    idf_component_register(INCLUDE_DIRS "include" REQUIRES ${REQS})
    return()
endif()
if(NOT VTTS_BOARD)
    set(VTTS_BOARD $ENV{VTTS_BOARD})
endif()
if(NOT VTTS_BOARD)
    set(VTTS_BOARD panel)
endif()
set(BOARD_DIR ${CMAKE_CURRENT_LIST_DIR}/boards/${VTTS_BOARD})
if(NOT EXISTS ${BOARD_DIR}/board.cmake)
    message(FATAL_ERROR "unknown board '${VTTS_BOARD}': no boards/${VTTS_BOARD}/board.cmake")
endif()
include(${BOARD_DIR}/board.cmake)
if(NOT IDF_TARGET STREQUAL BSP_TARGET)
    message(FATAL_ERROR "board '${VTTS_BOARD}' needs target ${BSP_TARGET}, not ${IDF_TARGET}")
endif()
idf_component_register(
    SRCS "bsp_common.c" "drivers/speaker_${BSP_SPEAKER}.c"
    INCLUDE_DIRS "include" "${BOARD_DIR}"
    REQUIRES ${REQS})
