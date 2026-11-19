"""Token set ms-en and Malay spelling-to-phoneme rules (ms/g2p_ms.py, shared with id/g2p_id.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.id.g2p_id import phonemes as id_phonemes
from vtts.frontend.lexicons import load_table
from vtts.frontend.ms.g2p_ms import (
    override_table,
    phonemes,
    unreadable_ms,
    valid_spelling,
    word_tokens_ms,
)


def test_token_set_msen_extends_v2():
    assert ps.TOKENS_MSEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_MSEN[107:]
    assert all(t.startswith("MS:") for t in block)
    assert len(block) == len(set(block)) == 38 and ps.VOCAB_SIZE_MSEN == 145
    assert ps.TOKEN_SETS[ps.TOKEN_SET_MSEN] is ps.TOKENS_MSEN and ps.TOKEN_SET_MSEN == "ms-en"
    assert ps.PAIR_MODES["ms"] == "ms-en"
    idx = ps.token_index("ms-en")
    assert idx["MS:a"] == 107 and idx["MS:@"] == 111 and idx["MS:a1"] == 113 and idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_MSEN[107:]}
    text = ("besar elok anak ma'af pantai pulau bunga nyanyi syarikat khabar ghaib ramadhan cara "
            "jalan zaman fakta universiti xenon quran wajib yakin kerja")
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w


@pytest.mark.parametrize("word, ph", [
    # shared Indonesian rules
    ("bunga", "b u1 ng a"), ("syarikat", "sy a r i1 k a t"), ("khabar", "kh a1 b a r"),
    ("anak", "a1 n a ?"), ("pantai", "p a1 n t a y"), ("pulau", "p u1 l a w"), ("baik", "b a1 i ?"),
    ("besar", "b @ s a1 r"), ("sekolah", "s @ k o1 l a h"), ("boleh", "b o1 l e h"),
    ("meja", "m e1 j a"), ("kereta", "k @ r e1 t a"), ("mejanya", "m e j a1 ny a"),
    # Malay letters: v stays v, gh and dh are one sound
    ("universiti", "u n i v @ r s i1 t i"), ("ghaib", "gh a1 i b"), ("loghat", "l o1 gh a t"),
    ("ramadhan", "r a m a1 dh a n"), ("mahathir", "m a h a1 th i r"),
    # Malay e table (over the Indonesian one), also with affixes
    ("nenek", "n e1 n e ?"), ("esok", "e1 s o ?"), ("teksi", "t e1 k s i"),
    ("berbeza", "b @ r b e1 z a"), ("televisyen", "t e l e v i1 sy e n"),
    # final a is a; Malay function words
    ("lapan", "l a1 p a n"), ("kerana", "k @ r a1 n a"), ("kepada", "k @ p a d a"),
    ("daripada", "d a r i p a d a"),
])
def test_phonemes(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_indonesian_unchanged_by_the_shared_code():
    assert " ".join(id_phonemes("video")) == "f i d e1 o"
    assert " ".join(id_phonemes("besar")) == "b @ s a1 r"
    assert " ".join(phonemes("video")) == "v i d e1 o"


def test_overrides():
    ms = load_table("ms", "overrides")
    for key, reading in ms.items():
        assert key == reading.replace("é", "e") and phonemes(key), key
    assert override_table()["meja"] == "méja" and override_table()["teksi"] == "téksi"


def test_word_without_vowel_is_spelled():
    assert word_tokens_ms("km") == word_tokens_ms("ké") + word_tokens_ms("ém")


@pytest.mark.parametrize("word", ["rumah", "makan", "sekolah", "struktur", "program", "stesen",
                                  "teksi", "ekspres", "teknologi", "loghat", "ghaib", "ramadhan",
                                  "maaf", "syarikat", "nyanyi", "khabar", "kampung"])
def test_valid_malay_spelling(word):
    assert valid_spelling(word)


@pytest.mark.parametrize("word", ["smart", "weekend", "facebook", "bluetooth", "spotify", "check",
                                  "playlist", "download", "shopping", "party", "happy", "router"])
def test_english_looking_spelling(word):
    assert not valid_spelling(word)


def test_unreadable():
    assert unreadable_ms("Apa khabar? Kafé, ma'af 123") == []
    assert unreadable_ms("Kuala Lumpur 東京") == list("東京")
