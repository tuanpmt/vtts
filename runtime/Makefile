CC ?= cc
CFLAGS ?= -std=c99 -O2 -Wall -Wextra -Werror -Iinclude
SAN = -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -g
SRC = src/vtts_model.c src/vtts_synth.c src/vtts_kernels_ref.c

build/golden_test: $(SRC) test/golden_test.c include/vtts.h include/vtts_port.h
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) $(SRC) test/golden_test.c -lm -o $@

build/libvtts.a: $(SRC) include/vtts.h
	mkdir -p build
	$(CC) $(CFLAGS) -c src/vtts_model.c -o build/vtts_model.o
	$(CC) $(CFLAGS) -c src/vtts_synth.c -o build/vtts_synth.o
	ar rcs $@ build/vtts_model.o build/vtts_synth.o

clean:
	rm -rf build
.PHONY: clean

build/vtts_cli: $(SRC) tools/vtts_cli.c include/vtts.h
	mkdir -p build
	$(CC) $(CFLAGS) -O3 $(SRC) tools/vtts_cli.c -lm -o $@

build/stream_test: $(SRC) test/stream_test.c include/vtts.h
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) $(SRC) test/stream_test.c -lm -o $@

TEXT_SRC = src/vtts_text.c src/vtts_text_en.c src/vtts_text_zh.c src/vtts_text_ko.c src/vtts_text_hi.c src/vtts_lex.c
TEXT_HDR = include/vtts_text.h include/vtts_lex.h include/vtts_zlex.h src/vtts_text_en.h src/vtts_text_zh.h src/vtts_text_ko.h src/vtts_text_hi.h src/vtts_text_tables.h
build/text_test: $(TEXT_SRC) test/text_test.c $(TEXT_HDR)
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) -Isrc $(TEXT_SRC) test/text_test.c -o $@

build/lex_test: $(TEXT_SRC) test/lex_test.c $(TEXT_HDR)
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) -Isrc $(TEXT_SRC) test/lex_test.c -o $@

build/en_norm_test: $(TEXT_SRC) test/en_norm_test.c $(TEXT_HDR)
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) -Isrc $(TEXT_SRC) test/en_norm_test.c -o $@

build/token_set_test: $(SRC) $(TEXT_SRC) test/token_set_test.c include/vtts.h $(TEXT_HDR)
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) -Isrc $(SRC) $(TEXT_SRC) test/token_set_test.c -lm -o $@

# Host synthesizer from text: front-end chosen by the model's token set (like the firmware)
build/vtts_say: $(SRC) $(TEXT_SRC) tools/vtts_say.c include/vtts.h $(TEXT_HDR)
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) -Isrc $(SRC) $(TEXT_SRC) tools/vtts_say.c -lm -o $@

# Blobs of the device front-end, built from the Python tables (needs uv at the repository root).
build/lex_en.bin: ../src/vtts/frontend/en/vlex.py ../scripts/frontend/build_lexicon.py
	mkdir -p build
	cd .. && uv run python scripts/frontend/build_lexicon.py --out runtime/$@

build/zh_lex.bin: ../src/vtts/frontend/lexicons/zh/chars.tsv ../src/vtts/frontend/lexicons/zh/phrases.tsv ../scripts/frontend/build_zh_blob.py
	mkdir -p build
	cd .. && uv run python scripts/frontend/build_zh_blob.py --out runtime/$@

# Mandarin (VTTS_LANG_ZH) parity with text_to_ids(text, "zh") and the fuzz run in every mode.
zh_test: build/text_test build/lex_en.bin build/zh_lex.bin
	./build/text_test --lex build/lex_en.bin --zh build/zh_lex.bin test/text_parity_zh.tsv
	./build/text_test --fuzz --lex build/lex_en.bin --zh build/zh_lex.bin

# Korean (VTTS_LANG_KO) parity with text_to_ids(text, "ko"); tables are compiled in (no blob).
ko_test: build/text_test build/lex_en.bin
	./build/text_test --lex build/lex_en.bin test/text_parity_ko.tsv

# Hindi (VTTS_LANG_HI) parity with text_to_ids(text, "hi") and the fuzz run (hi among the modes);
# tables are compiled in (no blob).
hi_test: build/text_test build/lex_en.bin
	./build/text_test --lex build/lex_en.bin test/text_parity_hi.tsv
	./build/text_test --fuzz --lex build/lex_en.bin

# All text front-end tests (no model needed); the model golden tests run from pytest.
test: build/token_set_test build/text_test build/lex_test build/en_norm_test build/lex_en.bin build/zh_lex.bin
	./build/token_set_test
	./build/text_test test/text_parity.tsv
	./build/text_test --lex build/lex_en.bin test/text_parity_v2.tsv
	./build/lex_test build/lex_en.bin test/lex_expect.tsv
	./build/en_norm_test test/en_norm.tsv
	$(MAKE) zh_test
	$(MAKE) ko_test
	$(MAKE) hi_test
.PHONY: zh_test ko_test hi_test test
