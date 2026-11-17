# Contributing to vtts

Thanks for your interest. Bug reports, measurements on other boards, new language front-ends and runtime speedups are all welcome. For larger changes, please open an issue first so we can agree on the approach.

## Setup and tests

```bash
uv sync                      # Python 3.11; add --extra gpu for training and evaluation
uv run pytest -q             # fast tests: front-ends, data, export, C runtime under ASan/UBSan
uv run pytest -q tests/frontend
uv run pytest -q -m slow     # needs the gpu extra and downloads ASR/MOS models
uv run ruff check .
```

The Python tests also build and run the C tests in `runtime/` (golden, streaming and text parity), so a C compiler and `make` are required. Firmware changes should be built for every board (`BOARD=panel`, `nano`, `s3`) and checked on hardware with `selftest` and `bench`; please include the `bench` output in the pull request.

## Adding a language

The front-end layout, rule precedence and the steps for changing a reading are in [docs/frontend/pronunciation-rules.md](docs/frontend/pronunciation-rules.md).

1. **Token set.** Add the new tokens as a new token set version in `src/vtts/frontend/phoneme_set.py`. Never reorder or remove existing tokens: models store ids, and the model file header records the vocabulary size.
2. **Front-end (Python).** Data tables in `src/vtts/frontend/lexicons/<lang>/*.tsv`, a normalizer (numbers, dates, currency, units, product codes) and a G2P under `src/vtts/frontend/<lang>/`, wired into the language tagger (`lang.py`) and `text.py`. Add tests under `tests/frontend/`.
3. **Front-end (C).** Port the subset devices need to `runtime/src/vtts_text.c`; generate tables from Python (`runtime/tools/gen_text_tables.py`) rather than copying them by hand, and extend the parity fixture (`scripts/frontend/export_text_parity.py`) so Python and C must produce identical ids.
4. **Data and training.** Any recorded or synthesized speech with transcripts works; see "Training a voice" in the README. Document data sources and their licenses in `NOTICE` and in the model card. Use only data whose terms allow training, and only voices that are designed or whose speakers consented.
5. **Evaluation.** Add an out-of-domain sentence set under `eval/sets/` and report CER, UTMOS and on-chip RTF for both model tiers.

## Adding a board

1. Add a folder `firmware/esp32/boards/<id>/` with `board.h` (name, pins, default volume and gain), `board.cmake` (chip and speaker driver) and `sdkconfig.defaults`; `BOARD=<id>` then works with `build.sh`. See [firmware/esp32/boards/README.md](firmware/esp32/boards/README.md).
2. A speaker chip without a driver needs `firmware/esp32/main/bsp/speaker_<driver>.c` implementing the `bsp_speaker_*` functions of `bsp.h`.
3. Run `selftest`, `bench` and a long paragraph with playback (check for zero underruns), and add the numbers to [docs/reports/performance.md](docs/reports/performance.md) and the board to `boards` in `docs/site.json`.

A new chip family also needs SIMD kernels in `runtime/ports/` that pass `selftest` against the reference C kernels; see [runtime/README.md](runtime/README.md#porting).

## Code style

- **Python:** 3.11, formatted and linted with `ruff` (line length 100), type hints on public functions. Each script starts with a docstring that says what it does and shows its usage.
- **C:** C99, `-Wall -Wextra -Werror` clean, no `malloc` in the runtime (all memory comes from the caller's arena), no hard-coded model shapes. New kernels need a reference C version and a bit-exact or tolerance test.
- **Language:** code, comments, file names, commit messages and documentation in English. `README.vi.md` is a maintained Vietnamese translation of `README.md`; update both when you change the README. Vietnamese text that is data (test sentences, templates, lexicons) stays Vietnamese.
- **Commits:** small and focused, with a short imperative subject (`frontend: ...`, `runtime: ...`, `docs: ...`).

## Privacy and secrets

This is a public repository. Before you push, make sure nothing private is committed:

- no API keys, tokens or service URLs (keep them in a local env file outside the repository; the VoxCPM2 client reads `~/.config/vtts/voxcpm.env`);
- no internal hostnames, IP addresses, user names or absolute local paths (home or root directories on your machine or a server); write paths relative to the repository;
- no personal e-mail addresses or names of private organizations.

A quick check before pushing (the bracketed characters keep this line from matching itself):

```bash
git grep -nE "[1]92\.168\.|[r]oot@|[/]Users[/]|[/]home[/]|[/]root[/]|[h]f_[A-Za-z0-9]{10}|[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+"
```

## License

By contributing you agree that your contributions are licensed under the Apache License 2.0 (see [LICENSE](LICENSE)). Model files are licensed separately; see the README.

## README and website

The voice catalog, hardware table, board list and technology summary are shared by `README.md`, `README.vi.md` and the website (`docs/index.html`). Edit them in `docs/site.json` (the `listen` key holds the website's languages, models with their size and RTF, and audio samples), then run:

```bash
uv run python scripts/docs/sync_docs.py
```

The script rewrites only the blocks between `<!-- BEGIN:name -->` and `<!-- END:name -->`; everything else stays hand-written. `tests/docs/test_docs_sync.py` fails when a generated block is out of date. The website loads no third-party resources (fonts are self-hosted in `docs/fonts/`), so it also works where Google services are blocked.
