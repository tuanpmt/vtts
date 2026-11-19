/* SPDX-License-Identifier: Apache-2.0 */
/* console.c -- serial console: one command or sentence per line, answered by "DONE".
 *
 * Commands are registered with esp_console (`help` lists them). A line whose first word is not a
 * command is spoken; `dump <text>` and `ids <...>` also take the rest of the line verbatim, so
 * text never goes through the argument parser (which would strip quotes). */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app.h"
#include "bsp.h"
#include "driver/uart.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_console.h"
#include "freertos/task.h"
#include "vtts_port.h"

extern int64_t vtts_prof_us[];
extern const int vtts_prof_n;
extern const char *const vtts_prof_names[];
void vtts_par_enable(int on);

static float arg_f(int argc, char **argv, float dflt) { return argc > 1 ? (float)atof(argv[1]) : dflt; }

static int cmd_bench(int argc, char **argv) { (void)argc; (void)argv; synth_bench(); return 0; }
static int cmd_selftest(int argc, char **argv) { (void)argc; (void)argv; return selftest_run() ? 1 : 0; }
static int cmd_fusetest(int argc, char **argv) { (void)argc; (void)argv; return fusetest_run(); }

static int cmd_model(int argc, char **argv) {
    if (argc > 1) g.cur = (argv[1][0] == 'm' || argv[1][0] == 'M') ? 1 : 0;
    printf("model %c (token set %s, lang %s)\n", g.cur ? 'M' : 'S', vtts_token_set_name(vtts_token_set(&g.models[g.cur])),
           synth_lang_name(g.cur));
    return 0;
}

static int cmd_vol(int argc, char **argv) {
    if (argc > 1) g.vol = atoi(argv[1]);
    if (g.spk) bsp_speaker_set_vol(g.vol);
    printf("vol %d\n", g.vol);
    return 0;
}

static int cmd_gain(int argc, char **argv) { /* digital gain in dB, 0..24, before the soft limiter */
    float db = arg_f(argc, argv, 0.0f);
    db = db < 0 ? 0 : db > 24 ? 24 : db;
    g.gain = powf(10.0f, db / 20.0f);
    printf("gain %.1f dB\n", db);
    return 0;
}

static int cmd_speed(int argc, char **argv) { /* length scale 0.7..1.6, higher is slower */
    float v = arg_f(argc, argv, 1.0f);
    g.speed = v < 0.7f ? 0.7f : v > 1.6f ? 1.6f : v;
    printf("speed %.2f\n", g.speed);
    return 0;
}

static int cmd_expr(int argc, char **argv) { /* intonation range of prosody models, 0.5..2.5 */
    float e = arg_f(argc, argv, 1.0f);
    e = e < 0.5f ? 0.5f : e > 2.5f ? 2.5f : e;
    for (int k = 0; k < 2; k++) vtts_set_expressiveness(&g.models[k], e);
    printf("expr %.2f (prosody model: %d)\n", e, g.models[g.cur].prosody);
    return 0;
}

static int cmd_chunk(int argc, char **argv) {
    int c = argc > 1 ? atoi(argv[1]) : g.chunk;
    g.chunk = c < 1 ? 1 : c > MAX_CHUNK ? MAX_CHUNK : c;
    printf("chunk %d\n", g.chunk);
    return 0;
}

static int cmd_first(int argc, char **argv) {
    int f = argc > 1 ? atoi(argv[1]) : g.first;
    g.first = f < 1 ? 1 : f;
    printf("first %d\n", g.first);
    return 0;
}

static int cmd_cores(int argc, char **argv) {
    int two = argc > 1 && atoi(argv[1]) >= 2;
    vtts_par_enable(two);
    printf("cores %d\n", two ? 2 : 1);
    return 0;
}

/* text mode of the current model; the valid modes depend on its token set (vtts_text_modes) */
static int cmd_lang(int argc, char **argv) {
    int ts = vtts_token_set(&g.models[g.cur]), rc = 0;
    if (argc > 1) {
        vtts_lang l;
        if (vtts_text_lang_for(ts, argv[1], &l) == 0) g.lang[g.cur] = (int)l;
        else {
            printf("ERROR lang %s is not a mode of token set %s (modes: %s)\n", argv[1], vtts_token_set_name(ts),
                   *vtts_text_modes(ts) ? vtts_text_modes(ts) : "none, send ids");
            rc = 1;
        }
    }
    printf("lang %s (model %c: token set %s, modes %s)\n", synth_lang_name(g.cur), g.cur ? 'M' : 'S',
           vtts_token_set_name(ts), *vtts_text_modes(ts) ? vtts_text_modes(ts) : "none");
    return rc;
}

static int cmd_prof(int argc, char **argv) {
    (void)argc; (void)argv;
    int64_t tot = 0;
    for (int i = 0; i < vtts_prof_n; i++) tot += vtts_prof_us[i];
    for (int i = 0; i < vtts_prof_n; i++)
        printf("PROF %-14s %8.3fs %5.1f%%\n", vtts_prof_names[i], vtts_prof_us[i] / 1e6, tot ? 100.0 * vtts_prof_us[i] / tot : 0.0);
    memset(vtts_prof_us, 0, sizeof(int64_t) * (size_t)vtts_prof_n);
    return 0;
}

static const esp_console_cmd_t CMDS[] = {
    {.command = "bench", .help = "RTF on four fixed sentences, no audio (REPORT lines)", .func = cmd_bench},
    {.command = "prof", .help = "time per synthesis stage since the last prof", .func = cmd_prof},
    {.command = "model", .help = "lite (s) or quality (m) model", .hint = "s|m", .func = cmd_model},
    {.command = "lang", .help = "text mode of the current model's token set: v1 vi; vi-en vi|en|auto (vi also reads English words); zh-en zh; ko-en ko; hi-en hi; ja-en ja; es-en es; id-en id; pt-en pt; th-en th; fr-en fr; de-en de; it-en it; tr-en tr; ru-en ru; pl-en pl; ar-en ar; fi-en fi; el-en el; ms-en ms; tl-en tl; sw-en sw; nl-en nl; sv-en sv; no-en no (each when built in)", .hint = "vi|en|auto|zh|ko|hi|ja|es|id|pt|th|fr|de|it|tr|ru|pl|ar|fi|el|ms|tl|sw|nl|sv|no", .func = cmd_lang},
    {.command = "vol", .help = "speaker volume", .hint = "0-100", .func = cmd_vol},
    {.command = "gain", .help = "digital gain in dB before a soft limiter", .hint = "0-24", .func = cmd_gain},
    {.command = "speed", .help = "speaking rate (length scale, higher is slower)", .hint = "0.7-1.6", .func = cmd_speed},
    {.command = "expr", .help = "intonation range (models with a pitch predictor)", .hint = "0.5-2.5", .func = cmd_expr},
    {.command = "chunk", .help = "largest streaming chunk in frames (the firmware may pick smaller)", .hint = "1-256", .func = cmd_chunk},
    {.command = "first", .help = "frames in the first chunk", .hint = "N", .func = cmd_first},
    {.command = "cores", .help = "synthesis on one or two cores", .hint = "1|2", .func = cmd_cores},
    {.command = "selftest", .help = "SIMD kernels against plain C, including two cores at once", .func = cmd_selftest},
    {.command = "fusetest", .help = "ESP32-S3: the fused ld.ip kernel over memory x cores x interrupts", .func = cmd_fusetest},
};

static int is_command(const char *line) {
    size_t n = strcspn(line, " ");
    if (n == 4 && strncmp(line, "help", 4) == 0) return 1;
    for (size_t i = 0; i < sizeof CMDS / sizeof *CMDS; i++)
        if (strlen(CMDS[i].command) == n && strncmp(line, CMDS[i].command, n) == 0) return 1;
    return 0;
}

static void handle(char *line) {
    /* skip noise from port open or reset: control bytes and bytes that cannot start UTF-8 */
    for (unsigned char ch; (ch = (unsigned char)*line) && (ch < 0x20 || ch == 0x7f || (ch >= 0x80 && ch < 0xc2) || ch >= 0xf5);)
        line++;
    size_t len = strlen(line);
    while (len && (line[len - 1] == '\r' || line[len - 1] == '\n' || line[len - 1] == ' ')) line[--len] = 0;
    if (!len) return;
    if (strncmp(line, "dump ", 5) == 0) synth_dump(line + 5);
    else if (is_command(line)) {
        int ret;
        esp_err_t e = esp_console_run(line, &ret);
        if (e != ESP_OK) printf("ERROR %s\n", esp_err_to_name(e));
    } else synth_say(line); /* a sentence, or "ids ..." */
    printf("DONE\n");
}

/* console input: UART (P4 boards, USB bridge) or the S3's own USB-Serial-JTAG */
#if CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG
static void input_init(void) {
    usb_serial_jtag_driver_config_t cfg = {.rx_buffer_size = 4096, .tx_buffer_size = 4096};
    usb_serial_jtag_driver_install(&cfg);
    usb_serial_jtag_vfs_use_driver();
}
static int input_read(uint8_t *ch) { return usb_serial_jtag_read_bytes(ch, 1, portMAX_DELAY); }
#else
static void input_init(void) { uart_driver_install(CONFIG_ESP_CONSOLE_UART_NUM, 4096, 0, 0, NULL, 0); }
static int input_read(uint8_t *ch) { return uart_read_bytes(CONFIG_ESP_CONSOLE_UART_NUM, ch, 1, portMAX_DELAY); }
#endif

static void console_task(void *arg) {
    (void)arg;
    input_init();
    esp_console_config_t cfg = ESP_CONSOLE_CONFIG_DEFAULT();
    cfg.max_cmdline_length = 2048;
    esp_console_init(&cfg);
    esp_console_register_help_command();
    for (size_t i = 0; i < sizeof CMDS / sizeof *CMDS; i++) esp_console_cmd_register(&CMDS[i]);
    static char line[2048];
    size_t n = 0;
    printf("board %s\n", bsp_name());
    printf("READY (type a sentence to speak it; `help` lists the commands)\n");
    for (;;) {
        uint8_t ch;
        if (input_read(&ch) != 1) continue;
        if (ch == '\n' || ch == '\r') {
            line[n] = 0;
            if (n) handle(line);
            n = 0;
        } else if (n < sizeof(line) - 1) {
            line[n++] = (char)ch;
        }
    }
}

void console_start(void) { xTaskCreatePinnedToCore(console_task, "console", 16384, NULL, 5, NULL, 0); }
