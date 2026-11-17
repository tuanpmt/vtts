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

TEXT_SRC = src/vtts_text.c
build/text_test: $(TEXT_SRC) test/text_test.c include/vtts_text.h src/vtts_text_tables.h
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) -Isrc $(TEXT_SRC) test/text_test.c -o $@

build/lex_test: src/vtts_lex.c src/vtts_text_en.c src/vtts_text.c src/vtts_text_en.h test/lex_test.c include/vtts_lex.h src/vtts_text_tables.h
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) -Isrc src/vtts_lex.c src/vtts_text_en.c src/vtts_text.c test/lex_test.c -o $@

build/en_norm_test: src/vtts_text_en.c src/vtts_text.c src/vtts_lex.c test/en_norm_test.c src/vtts_text_en.h src/vtts_text_tables.h
	mkdir -p build
	$(CC) $(CFLAGS) $(SAN) -Isrc src/vtts_text_en.c src/vtts_text.c src/vtts_lex.c test/en_norm_test.c -o $@
