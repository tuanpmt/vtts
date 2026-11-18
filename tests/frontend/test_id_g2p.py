"""Token set id-en and Indonesian spelling-to-phoneme rules (id/g2p_id.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.id.g2p_id import phonemes, respell, unreadable_id, valid_spelling, word_tokens_id
from vtts.frontend.lexicons import load_table


def test_token_set_iden_extends_v2():
    assert ps.TOKENS_IDEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_IDEN[107:]
    assert all(t.startswith("ID:") for t in block)
    assert len(block) == len(set(block)) == 34 and ps.VOCAB_SIZE_IDEN == 141
    assert ps.TOKEN_SETS[ps.TOKEN_SET_IDEN] is ps.TOKENS_IDEN and ps.TOKEN_SET_IDEN == "id-en"
    assert ps.PAIR_MODES["id"] == "id-en"
    idx = ps.token_index("id-en")
    assert idx["ID:a"] == 107 and idx["ID:@"] == 111 and idx["ID:a1"] == 113 and idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_IDEN[107:]}
    text = ("besar enak anak ma'af pantai pulau bunga nyanyi masyarakat akhir cara jalan zaman "
            "fakta video xenon quran wajib yakin kerja")
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w


@pytest.mark.parametrize("word, ph", [
    # consonants and digraphs
    ("bunga", "b u1 ng a"), ("nyanyi", "ny a1 ny i"), ("masyarakat", "m a sy a r a1 k a t"),
    ("akhir", "a1 kh i r"), ("cara", "c a1 r a"), ("jalan", "j a1 l a n"),
    ("video", "f i d e1 o"), ("quran", "k u1 r a n"), ("xenon", "s @ n o1 n"),
    ("allah", "a1 l a h"),
    # glottal stop: final k and apostrophe; k before a consonant stays
    ("anak", "a1 n a ?"), ("ma'af", "m a1 ? a f"), ("rakyat", "r a1 k y a t"),
    # final diphthongs; vowels elsewhere are nuclei
    ("pantai", "p a1 n t a y"), ("pulau", "p u1 l a w"), ("baik", "b a1 i ?"),
    ("laut", "l a1 u t"),
    # the two e's: defaults
    ("besar", "b @ s a1 r"), ("kecil", "k @ c i1 l"), ("sekolah", "s @ k o1 l a h"),
    ("sore", "s o1 r e"), ("boleh", "b o1 l e h"), ("bebek", "b @ b e1 ?"),
    ("hotel", "h o1 t e l"), ("persen", "p @ r s e1 n"), ("komputer", "k o m p u1 t @ r"),
    ("teori", "t e o1 r i"), ("empat", "@ m p a1 t"), ("ke", "k @"),
    # the two e's: overrides, also with affixes
    ("enak", "e1 n a ?"), ("meja", "m e1 j a"), ("mereka", "m @ r e1 k a"),
    ("mejanya", "m e j a1 ny a"), ("berbeda", "b @ r b e1 d a"),
    ("kedewasaan", "k @ d e w a s a1 a n"), ("ember", "e1 m b @ r"),
    # stress: penultimate, the last syllable when the penultimate has the schwa
    ("pergi", "p @ r g i1"), ("seperti", "s @ p @ r t i1"), ("rumah", "r u1 m a h"),
    # function words
    ("yang", "y a ng"), ("dengan", "d @ ng a n"),
    # é from the normalizer (letter names)
    ("bé", "b e1"),
])
def test_phonemes(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_respell_and_overrides():
    assert respell("mejanya") == ("méjanya", True)
    assert respell("pedesaan") == ("pedésaan", True)
    assert respell("rumah") == ("rumah", False)
    for key, reading in load_table("id", "overrides").items():
        assert key == reading.replace("é", "e") and phonemes(key), key


def test_word_without_vowel_is_spelled():
    assert word_tokens_id("km") == word_tokens_id("ka") + word_tokens_id("ém")


@pytest.mark.parametrize("word", ["rumah", "makan", "sekolah", "struktur", "program", "stasiun",
                                  "swasta", "ekspor", "teknologi", "keenam", "diikuti", "maaf",
                                  "saat", "gojek", "masyarakat", "nyanyi", "akhir", "zaman"])
def test_valid_indonesian_spelling(word):
    assert valid_spelling(word)


@pytest.mark.parametrize("word", ["smart", "weekend", "facebook", "bluetooth", "spotify", "check",
                                  "playlist", "download", "shopping", "party", "happy", "router",
                                  "sport", "google", "access", "jazz"])
def test_english_looking_spelling(word):
    assert not valid_spelling(word)


def test_unreadable():
    assert unreadable_id("Apa kabar? Kafé, ma'af 123") == []
    assert unreadable_id("Jakarta 東京") == list("東京")
