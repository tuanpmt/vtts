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
# lex_zh.bin (ZLEX, Mandarin readings for zh-en models, ~116 KB) is embedded when present;
# build.sh builds it with scripts/frontend/build_zh_blob.py
set(EMBED "model_s.vtts" "model_m.vtts" "lex_en.bin")
set(EMBED_ZH 0)
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/lex_zh.bin")
    list(APPEND EMBED "lex_zh.bin")
    set(EMBED_ZH 1)
endif()
# lex_ja.bin (JLEX, Japanese readings and NFKC data for ja-en models, ~720 KB) likewise;
# build.sh builds it with scripts/frontend/build_ja_blob.py
set(EMBED_JA 0)
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/lex_ja.bin")
    list(APPEND EMBED "lex_ja.bin")
    set(EMBED_JA 1)
endif()
idf_component_register(
    SRCS "main.c" "synth.c" "speaker.c" "console.c" "selftest.c" "${PORT}"
         "${RT}/ports/freertos/vtts_par_freertos.c"
         "${RT}/src/vtts_model.c" "${RT}/src/vtts_synth.c" "${RT}/src/vtts_kernels_ref.c"
         "${RT}/src/vtts_text.c" "${RT}/src/vtts_text_en.c" "${RT}/src/vtts_text_zh.c" "${RT}/src/vtts_text_ko.c"
         "${RT}/src/vtts_text_hi.c" "${RT}/src/vtts_text_ja.c" "${RT}/src/vtts_lex.c"
    INCLUDE_DIRS "." "${RT}/include" "${RT}/src"
    PRIV_REQUIRES ${REQS}
    EMBED_FILES ${EMBED})
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-math-errno -Wno-unused-function -DVTTS_PROFILE
                       -DVTTS_EMBED_ZH=${EMBED_ZH} -DVTTS_EMBED_JA=${EMBED_JA} -DVTTS_BLOCK=64 -DVTTS_HEAD_BLOCK=16 -DVTTS_STREAM_STEP=64)
