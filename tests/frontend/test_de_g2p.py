"""German G2P (g2p_de): morphs, vowel length, consonant rules, stress, lexicon files."""

import pytest

from vtts.frontend.de.g2p_de import (
    override_table,
    phonemes,
    segment,
    stem_table,
    valid_spelling,
    word_tokens_de,
)
from vtts.frontend.lexicons import load_words
from vtts.frontend.phoneme_set import TOKENS_DEEN


def ph(word):
    return " ".join(phonemes(word))


@pytest.mark.parametrize("word, expected", [
    # vowel length: open syllable, h, doubled vowel, ie, ß; short before clusters and doubles
    ("tage", "t a:1 g @"), ("bahn", "b a:1 n"), ("see", "z e:1"), ("spiel", "S p i:1 l"),
    ("fuß", "f u:1 s"), ("wasser", "v a1 s 6"), ("kunst", "k U1 n s t"),
    # final devoicing, also before an ending after a known stem (sag+t)
    ("tag", "t a:1 k"), ("tags", "t a:1 k s"), ("sagt", "z a:1 k t"), ("gibt", "g i:1 p t"),
    # ich-Laut / ach-Laut, initial ch, chs
    ("ich", "? I C"), ("ach", "? a1 x"), ("buch", "b u:1 x"), ("bücher", "b y:1 C 6"),
    ("chor", "k o:1 6"), ("chef", "S E1 f"), ("chemie", "C e: m i:1"), ("sechs", "z E1 k s"),
    # -ig, -ig + -lich, -ig + -keit
    ("könig", "k 2:1 n I C"), ("königlich", "k 2:1 n I k l I C"), ("ewigkeit", "? e:1 v I C k aI t"),
    # sp/st at the start of a stem, also after a prefix; s before a vowel
    ("stein", "S t aI1 n"), ("verstehen", "f E 6 S t e:1 @ n"), ("haus", "h aU1 s"),
    ("häuser", "h OY1 z 6"),
    # -er vocalization, schwa
    ("lehrer", "l e:1 R 6"), ("lehrerin", "l e:1 R @ R I n"), ("vater", "f a:1 t 6"),
    # glottal stop after a prefix, unstressed prefixes
    ("beachten", "b @ ? a1 x t @ n"),
    # foreign stress
    ("universität", "? u: n i: v E 6 z i: t E:1 t"), ("studieren", "S t u: d i:1 R @ n"),
    ("nation", "n a t s j o:1 n"), ("energie", "? e: n E 6 g i:1"), ("familie", "f a m i:1 l j @"),
    ("musik", "m u: z i:1 k"), ("technik", "t E1 C n I k"), ("politisch", "p o: l i:1 t I S"),
    ("gymnasium", "g Y m n a:1 z j U m"),
    # compounds: stress on the first part, sch / s+ch at the boundary
    ("bahnhofstraße", "b a:1 n h o: f S t R a: s @"), ("häuschen", "h OY1 s C @ n"),
    ("einundzwanzig", "? aI1 n ? U n t t s v a n t s I C"),
    # overrides
    ("vielleicht", "f i: l aI1 C t"), ("zurück", "t s u: R Y1 k"), ("der", "d E 6"),
])
def test_phonemes(word, expected):
    assert ph(word) == expected


def test_segment_compounds_and_prefixes():
    assert next(p.text for p in segment("bundesregierung")) == "bundes"
    assert [(p.kind, p.text) for p in segment("verstehen")] == [("up", "ver"), ("stem", "steh"), ("suf", "en")]
    assert next(p.text for p in segment("ausstellung")) == "aus"


def test_stress_marks_one_vowel_per_content_word():
    for w in ("arbeit", "regierung", "kindergarten", "aufgabe", "übersetzung", "unterricht"):
        assert sum(p.endswith("1") for p in phonemes(w)) == 1, w
    assert ph("übersetzung").index("1") > ph("übersetzung").index("z")  # über- unstressed before -ung
    assert ph("unterricht").startswith("? U1")


def test_tokens_in_token_set_and_spelled_letters():
    words = list(override_table()) + list(stem_table())[:400] + ["xylophon", "quatsch", "ypsilon"]
    for w in words:
        for t in word_tokens_de(w):
            assert t in TOKENS_DEEN, (w, t)
    assert word_tokens_de("km") == word_tokens_de("ka") + word_tokens_de("emm")
    assert word_tokens_de("café") == ["DE:k", "DE:a", "DE:f", "DE:e:1"]


def test_overrides_use_tokens_of_the_set():
    for w, reading in override_table().items():
        assert all(f"DE:{t}" in TOKENS_DEEN for t in reading.split()), w


@pytest.mark.parametrize("word, ok", [
    ("haus", True), ("schmetterling", True), ("bewegen", True), ("videoanruf", True), ("koalition", True),
    ("bluetooth", False), ("smartphone", False), ("weekend", False), ("show", False), ("party", False),
    ("update", False), ("meeting", False), ("coach", False), ("night", False),
])
def test_valid_spelling(word, ok):
    assert valid_spelling(word) is ok


def test_word_lists_are_lower_case():
    assert "in" in load_words("de", "native") and "update" in load_words("de", "english")


def test_prefix_tables_use_tokens_of_the_set():
    from vtts.frontend.de.g2p_de import PREFIXES

    for prefix, (_, reading) in PREFIXES.items():
        assert all(f"DE:{t}" in TOKENS_DEEN for t in reading.split()), prefix


def test_random_letter_strings_give_tokens_of_the_set():
    import random

    rnd = random.Random(3)
    letters = list("abcdefghijklmnopqrstuvwxyzäöüßé") + ["sch", "ch", "ie", "ck", "qu", "cc", "ww", "ßß"]
    for _ in range(3000):
        w = "".join(rnd.choice(letters) for _ in range(rnd.randint(1, 12)))
        assert all(t in TOKENS_DEEN for t in word_tokens_de(w)), w
