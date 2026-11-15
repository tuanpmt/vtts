set(RT ${CMAKE_CURRENT_LIST_DIR}/../../../runtime)
idf_component_register(
    SRCS "main.c" "${RT}/ports/esp32p4/vtts_port_p4.c"
         "${RT}/src/vtts_model.c" "${RT}/src/vtts_synth.c" "${RT}/src/vtts_kernels_ref.c"
         "${RT}/src/vtts_text.c"
    INCLUDE_DIRS "." "${RT}/include" "${RT}/src"
    PRIV_REQUIRES esp_timer esp_driver_uart
    EMBED_FILES "model_s.vtts" "model_m.vtts")
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -Wno-unused-function -DVTTS_PROFILE -DVTTS_BLOCK=64 -DVTTS_HEAD_BLOCK=16)
