"""text_to_ids(text, "pl"): Polish + English, token set pl-en."""

from pathlib import Path

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.latin import latin_word_lang
from vtts.frontend.phoneme_set import TOKENS_PLEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens

TEMPLATES = Path(__file__).resolve().parents[2] / "scripts" / "data" / "bilingual" / "templates_pl.txt"


def flat(text, lang="pl"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("PL:") for t in flat(text))


def test_tagging_polish_and_english_words():
    assert tag_words("Otwórz YouTube na iPhone, proszę.", "pl") == [
        ("Otwórz", "pl"), ("YouTube", "en"), ("na", "pl"), ("iPhone,", "en"), ("proszę.", "pl")]
    assert word_lang("Wi-Fi", "pl") == "en" and word_lang("ESP32", "pl") == "neutral"


@pytest.mark.parametrize("word, lang", [
    ("Kraków", "pl"), ("dom", "pl"), ("warszawa", "pl"), ("niemiecki", "pl"),
    ("do", "pl"), ("to", "pl"), ("ten", "pl"), ("my", "pl"), ("mln", "pl"), ("km", "pl"),
    ("update", "en"), ("online", "en"), ("router", "en"), ("the", "en"), ("YouTube", "en"),
    ("smartphone", "en"), ("streaming", "en"), ("USB", "pl"),
])
def test_latin_word_lang(word, lang):
    assert latin_word_lang(word, "pl") == lang


def test_polish_sentence():
    assert ph("Cześć, jak się masz?") == "ch e1 s' c' , j a1 k _ s' e _ m a1 sh ?"
    assert "EN:" not in " ".join(flat("Jutro rano pojedziemy na działkę i zbierzemy jabłka."))


def test_mixed_pl_en():
    toks = flat("Zaktualizowałem system na laptop.")
    assert "EN:AE" in toks and "PL:z" in toks and toks[-1] == "."
    assert flat("Wi-Fi nie działa.")[:len(flat("Wi-Fi", "en"))] == flat("Wi-Fi", "en")


def test_numbers_in_polish():
    assert flat("Mam 21 lat.") == flat("Mam dwadzieścia jeden lat.")
    assert flat("Spotkanie o 7:30.") == flat("Spotkanie o siódmej trzydzieści.")


def test_prepositions_join_the_next_word():
    assert ph("w domu") == "v d o1 m u"
    assert ph("w Polsce") == "f p o1 l s ts e"


def test_ids_use_plen_set_and_english_ids_match_v2():
    ids = text_to_ids("Otwórz YouTube, please.", "pl")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("pl-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_PLEN)
    assert text_to_ids("Thank you, see you soon.", "en") == text_to_ids("Thank you, see you soon.", "pl")


def test_other_modes_unchanged_by_polish():
    for mode in ("vi", "en", "auto", "es", "pt", "ru"):
        assert word_lang("Kraków", mode) != "pl"
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, Cześć", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2


def test_templates_are_readable():
    from vtts.data.train_list import unreadable

    for line in TEMPLATES.read_text(encoding="utf-8").splitlines():
        text = line.replace("{T}", "Bluetooth")
        assert not unreadable(text, "pl"), text
        toks = flat(text)
        assert any(t.startswith("PL:") for t in toks) and "EN:UW" in toks, text


def test_long_polish_text_is_chunked():
    one = "w każdą niedzielę chodzimy do parku i spacerujemy tam razem z dziećmi i psem"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "pl")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    words = [sum(1 for t in c if t == " ") + 1 for c in chunks]
    assert all(w <= 40 for w in words)
