"""text_to_ids(text, "fi"): Finnish + English, token set fi-en."""

from pathlib import Path

import pytest

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.latin import latin_word_lang
from vtts.frontend.phoneme_set import TOKENS_FIEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens

TEMPLATES = Path(__file__).resolve().parents[2] / "scripts" / "data" / "bilingual" / "templates_fi.txt"


def flat(text, lang="fi"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("FI:") for t in flat(text))


def test_tagging_finnish_and_english_words():
    assert tag_words("Avaa Spotify ja soita playlist, kiitos.", "fi") == [
        ("Avaa", "fi"), ("Spotify", "en"), ("ja", "fi"), ("soita", "fi"), ("playlist,", "en"),
        ("kiitos.", "fi")]
    assert tag_words("ESP32-P4 ja USB", "fi") == [("ESP32-P4", "neutral"), ("ja", "fi"), ("USB", "fi")]


def test_words_of_both_lists_follow_their_neighbours():
    assert [t for _, t in tag_words("Turn on the light.", "fi")] == ["en"] * 4
    assert [t for _, t in tag_words("Spotify on hyvä.", "fi")] == ["en", "fi", "fi"]
    assert [t for _, t in tag_words("Helsinki on kaunis.", "fi")] == ["fi"] * 3


@pytest.mark.parametrize("word, lang", [
    ("pääkaupunki", "fi"), ("Åbo", "fi"), ("on", "fi"), ("he", "fi"), ("home", "fi"),
    ("update", "en"), ("router", "en"), ("the", "en"), ("YouTube", "en"), ("iPhone", "en"),
    ("USB", "fi"), ("km", "fi"), ("klo", "fi"), ("talo", "fi"), ("Yhdysvaltain", "fi"),
    ("weekend", "en"), ("Bluetooth", "en"), ("Wi-Fi", "en"), ("Facebook", "en"),
])
def test_latin_word_lang(word, lang):
    assert latin_word_lang(word, "fi") == lang
    assert word_lang(word, "fi") == lang


def test_finnish_sentence():
    assert ph("Hei, mitä kuuluu?") == "h e1 i , m i1 t ae _ k u1 : l u : ?"
    assert "EN:" not in " ".join(flat("Kissa istuu ikkunalla ja katsoo lintuja."))


def test_dot_before_lower_case_word_is_not_a_sentence_end():
    assert split_sentences_raw("Hän syntyi 3. toukokuuta. Sitten hän muutti.", "fi") == [
        "Hän syntyi 3. toukokuuta.", "Sitten hän muutti."]
    assert split_sentences_raw("Paikalla oli n. 50 henkeä.", "fi") == ["Paikalla oli n. 50 henkeä."]
    assert len(split_sentences_raw("Paikalla oli n. 50 henkeä.")) == 2  # other modes unchanged
    assert len(text_to_tokens("Hän syntyi 3. toukokuuta 1950.", "fi")) == 1


def test_mixed_fi_en():
    toks = flat("Avaa GitHub ja etsi projekti.")
    assert "EN:G" in toks and "FI:k" in toks and toks[-1] == "."
    assert toks[toks.index("EN:G") - 1] == " "


def test_numbers_in_finnish():
    assert flat("Olen 21 vuotta.") == flat("Olen kaksikymmentäyksi vuotta.")
    assert flat("klo 7.30") == flat("kello seitsemän kolmekymmentä")


def test_ids_use_fien_set_and_english_ids_match_v2():
    ids = text_to_ids("Avaa GitHub, kiitos.", "fi")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("fi-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_FIEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "fi")


def test_other_modes_unchanged_by_finnish():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, pääkaupunki hello", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    assert word_lang("pääkaupunki", "es") != "fi"


def test_templates_are_readable():
    from vtts.data.train_list import unreadable

    for line in TEMPLATES.read_text(encoding="utf-8").splitlines():
        text = line.replace("{T}", "Bluetooth")
        assert not unreadable(text, "fi"), text
        toks = flat(text)
        assert any(t.startswith("FI:") for t in toks) and "EN:UW" in toks, text


def test_long_finnish_text_is_chunked():
    one = "naapurin koira haukkuu joka aamu kun postinkantaja tuo lehden ovelle"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "fi")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    assert all(sum(1 for t in c if t == " ") + 1 <= 40 for c in chunks)
