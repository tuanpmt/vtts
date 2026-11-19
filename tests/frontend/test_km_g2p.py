"""Khmer spelling rules (km/g2p_km.py): token set, clusters, syllables, series, tables, words."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.km.g2p_km import (
    VOWEL_PHONES,
    clusters,
    khmer_syllable_tokens,
    onset_table,
    override_table,
    rhyme_table,
    rule_phones,
    run_phones,
    segment,
    spell,
    syllable_tokens,
    syllables,
    unreadable_km,
    word_set,
)


def read(text):
    return " . ".join(" ".join(p) for p in run_phones(text))


def rules(word):
    return " . ".join(" ".join(p) for p in rule_phones(spell(word)))


def test_token_set_kmen():
    assert ps.TOKENS_KMEN[:107] == ps.TOKENS_V2
    assert len(set(ps.TOKENS_KMEN)) == len(ps.TOKENS_KMEN) == ps.VOCAB_SIZE_KMEN == 176
    assert ps.PAIR_MODES["km"] == ps.TOKEN_SET_KMEN == "km-en"
    idx = ps.token_index("km-en")
    assert idx["KM:?"] == 107 and idx["KM:F:s"] == 175
    assert len(ps.KM_CONSONANTS) == 24 and len(ps.KM_VOWELS) == 30 and len(ps.KM_FINALS) == 15


def test_every_table_phoneme_is_in_the_set():
    idx = ps.token_index("km-en")
    readings = [*rhyme_table().values(), *onset_table().values(),
                *(" ".join(" ".join(s) for s in v) for v in override_table().values())]
    for r in readings:
        for syl in r.split(" . "):
            assert all(t in idx for t in syllable_tokens(syl.split())), r


def test_clusters():
    c = clusters(spell("ស្ត្រី"))
    assert len(c) == 1 and c[0].base == "ស" and c[0].subs == "តរ" and c[0].vowel == "ី"
    c = clusters("ប៉ុន្តែ")
    assert [x.base for x in c] == ["ប", "ន"] and c[0].shift == 1 and c[1].subs == "ត"
    assert clusters("ស៊ី")[0].shift == 2
    assert clusters("ស៊ុី")[0].shift == 2 and clusters("ស៊ុី")[0].vowel == "ី"  # ុ under ី shifts


def test_spelling_variants_fold():
    assert spell("ស្រ្តី") == "ស្ត្រី"          # coeng ro last
    assert spell("ក្ដី") == "ក្តី"              # subscript ដ = subscript ត
    assert spell("ឲ្យ") == "ឱ្យ"
    assert spell("ប្រទេស\u200bកម្ពុជា") == "ប្រទេសកម្ពុជា"


@pytest.mark.parametrize("word, reading", [
    ("សង្គម", "s ɑ ŋ . k u m"),          # the pair after the inherent vowel splits
    ("ចិត្ត", "c ə t"),                  # a final subscript is silent
    ("របស់", "r ɔ . ɓ ɑ h"),             # bantoc: ស closes ប, so រ is a syllable
    ("នគរ", "n ɔ . k ɔɔ"),               # final រ is silent
    ("ទីក្រុង", "t ii . k r o ŋ"),        # ក្រ after a written vowel is an initial cluster
    ("ពុទ្ធ", "p u t"),
    ("ផ្ទះ", "p t ea h"),                # o-series from the subscript ទ
    ("ធម៌", "th oa"),                    # robat
    ("ភូមិ", "ph uu m"),                  # final ិ after a written vowel is silent
    ("ទាំង", "t ea ŋ"),                  # ាំង
    ("ស៊ី", "s ii"),                     # triisap: o-series
    ("ប៉ុន្តែ", "p o n . t ae"),          # muusikatoan: ប៉ = p
])
def test_rules(word, reading):
    assert rules(word) == reading


@pytest.mark.parametrize("word, reading", [
    ("ខ្ញុំ", "k ɲ o m"), ("ខ្មែរ", "k m ae"), ("ជា", "c ie"), ("ការ", "k aa"),
    ("កម្ពុជា", "k a m . p u ʔ . c ie"), ("ប្រទេស", "p r ɑ . t e h"), ("នេះ", "n i h"),
    ("អ្នក", "n ea k"),
])
def test_frequent_words(word, reading):
    assert read(word) == reading


def test_segmentation():
    assert segment(spell("ខ្ញុំស្រលាញ់ប្រទេសកម្ពុជា")) == ["ខ្ញុំ", "ស្រលាញ់", "ប្រទេស", "កម្ពុជា"]
    assert "កម្ពុជា" in word_set()


def test_repeat_mark_repeats_the_word():
    assert read("ផ្ទះៗ") == "p t ea h . p t ea h"


def test_syllable_tokens():
    assert syllable_tokens(["k", "ɲ", "o", "m"]) == ["KM:k", "KM:ny", "KM:o", "KM:F:m"]
    assert syllable_tokens(["ʔ", "ɑɑ"]) == ["KM:?", "KM:AA"]
    assert khmer_syllable_tokens("ផ្ទះ") == [["KM:p", "KM:t", "KM:ea", "KM:F:h"]]
    assert all(p in VOWEL_PHONES for p in ("ɨə", "ɛə", "aə"))


def test_last_syllable_flag():
    syls = syllables(spell("កម្ពុជា"))
    assert [s.last for s in syls] == [False, False, True]


def test_unreadable():
    assert unreadable_km("សួស្តី Москва") and not unreadable_km("សួស្តី Café ១០")
