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
# LANGS: the optional languages of the embedded models (or VTTS_LANGS), LANG_DEFS: -DVTTS_ENABLE_<L>=0|1
include(${CMAKE_CURRENT_LIST_DIR}/vtts_langs.cmake)
set(EMBED "model_s.vtts" "model_m.vtts" "lex_en.bin")
# Blobs of the blob-backed languages, embedded only when the language is compiled in (build.sh builds
# them): lex_zh.bin (ZLEX, Mandarin readings, ~116 KB), lex_ja.bin (JLEX, Japanese readings and NFKC
# data, ~720 KB), lex_ru.bin (RLEX, Russian stress, ~358 KB)
set(EMBED_DEFS "")
foreach(l zh ja ru)
    string(TOUPPER ${l} L)
    if(l IN_LIST LANGS AND EXISTS "${CMAKE_CURRENT_LIST_DIR}/lex_${l}.bin")
        list(APPEND EMBED "lex_${l}.bin")
        list(APPEND EMBED_DEFS "-DVTTS_EMBED_${L}=1")
    else()
        if(l IN_LIST LANGS)
            message(WARNING "vtts: ${l} is compiled in but main/lex_${l}.bin is missing (build.sh builds it)")
        endif()
        list(APPEND EMBED_DEFS "-DVTTS_EMBED_${L}=0")
    endif()
endforeach()
# Every language module is listed; one that is not enabled compiles to an empty unit (vtts_langs.h)
idf_component_register(
    SRCS "main.c" "synth.c" "speaker.c" "console.c" "selftest.c" "${PORT}"
         "${RT}/ports/freertos/vtts_par_freertos.c"
         "${RT}/src/vtts_model.c" "${RT}/src/vtts_synth.c" "${RT}/src/vtts_kernels_ref.c"
         "${RT}/src/vtts_text.c" "${RT}/src/vtts_text_en.c" "${RT}/src/vtts_text_zh.c" "${RT}/src/vtts_text_ko.c"
         "${RT}/src/vtts_text_hi.c" "${RT}/src/vtts_text_ja.c" "${RT}/src/vtts_text_lt.c" "${RT}/src/vtts_text_th.c"
         "${RT}/src/vtts_text_fr.c" "${RT}/src/vtts_text_de.c" "${RT}/src/vtts_text_it.c" "${RT}/src/vtts_text_tr.c"
         "${RT}/src/vtts_re.c" "${RT}/src/vtts_text_ru.c" "${RT}/src/vtts_text_pl.c"
         "${RT}/src/vtts_text_ar.c" "${RT}/src/vtts_text_fi.c" "${RT}/src/vtts_text_el.c"
         "${RT}/src/vtts_text_tl.c" "${RT}/src/vtts_text_sw.c"
         "${RT}/src/vtts_text_nx.c" "${RT}/src/vtts_text_nx_nl.c" "${RT}/src/vtts_text_nx_sc.c"
         "${RT}/src/vtts_text_da.c" "${RT}/src/vtts_text_lo.c"
         "${RT}/src/vtts_text_nsp.c" "${RT}/src/vtts_text_km.c" "${RT}/src/vtts_text_my.c"
         "${RT}/src/vtts_lex.c"
    INCLUDE_DIRS "." "${RT}/include" "${RT}/src"
    PRIV_REQUIRES ${REQS}
    EMBED_FILES ${EMBED})
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-math-errno -Wno-unused-function -DVTTS_PROFILE
                       ${LANG_DEFS} ${EMBED_DEFS} -DVTTS_BLOCK=64 -DVTTS_HEAD_BLOCK=16 -DVTTS_STREAM_STEP=64)
