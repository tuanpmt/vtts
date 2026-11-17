# ESP32-P4 and ESP32-S3 firmware

Runs the whole chain on the chip: text → token ids (C front-end) → streaming synthesis (C int8 runtime) → speaker. Type a sentence on the serial console and the board speaks it; `bench` prints RTF, RMS and memory use.

Supported boards:

| Board | Chip | Flash / PSRAM | Speaker path | `BOARD=` |
|---|---|---|---|---|
| Waveshare ESP32-P4-86-Panel | ESP32-P4 | 32 MB / 32 MB | ES8311 | `panel` (default) |
| Waveshare ESP32-P4-NANO | ESP32-P4 | 16 MB / 32 MB | ES8311 | `nano` |
| Waveshare ESP32-S3-Touch-LCD-2.8 | ESP32-S3R8 | 16 MB / 8 MB (octal) | PCM5101 | `s3` |

## Source layout

| Path | Contents |
|---|---|
| `main/main.c` | Start-up: models, memory (PSRAM first, internal RAM left for DMA), tasks |
| `main/synth.c` | Text or token ids to PCM, `SAID` / `DUMPED` / `REPORT` lines |
| `main/speaker.c` | Playback: soft limiter, stream buffer, prebuffer and chunk size from the measured RTF |
| `main/console.c` | Serial input and commands (`esp_console`; `help` lists them) |
| `main/selftest.c` | SIMD kernel checks (`selftest`, `fusetest`) |
| `components/bsp/` | Board support: speaker drivers and one folder per board ([README](components/bsp/README.md)) |

## Build and flash

```bash
# needs ESP-IDF v6.1; build.sh sources the IDF environment and copies both models into main/
./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor             # 86-Panel
BOARD=nano ./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor  # NANO
BOARD=s3 ./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor    # S3-Touch-LCD-2.8
```

The model files come from the [GitHub releases](https://github.com/tuanpmt/vtts/releases) or [Hugging Face](https://huggingface.co/tuanpm/vtts) (folder `vi/`). The serial console commands are listed in the [main README](../../README.md#serial-console).

Each board has its own build directory and `sdkconfig`. Shared configuration lives in `sdkconfig.defaults`; chip-specific settings live in `sdkconfig.defaults.esp32p4` and `sdkconfig.defaults.esp32s3`.

## Output

Each sentence prints a `REPORT` line: audio duration, synthesis time and RTF (below 1.0 is faster than real time).

## Self-test

`selftest` checks the SIMD kernels against results computed in plain C: one row, many rows, weights read from the model, and both cores running the kernel at the same time. On the S3 the kernel does not use the fused multiply-accumulate-and-load instruction (`ee.vmulas.s8.accx.ld.ip`). An earlier kernel with that instruction gave wrong sums on two cores; a rewritten one is correct (`fusetest` checks it) but barely faster, so the default kernel loads first and then multiply-accumulates.

## Adding a board

Board support is the ESP-IDF component [`components/bsp/`](components/bsp/README.md): one folder per board in `boards/<id>/` (`board.h` with pins and defaults, `board.cmake` with the chip and speaker driver, `sdkconfig.defaults`) and shared speaker drivers in `drivers/`. A new board is a new folder; see [components/bsp/README.md](components/bsp/README.md).
