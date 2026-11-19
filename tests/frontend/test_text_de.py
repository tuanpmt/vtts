"""text_to_ids(text, "de"): German + English, token set de-en."""

import pytest

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_DEEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="de"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("DE:") for t in flat(text))


def test_tagging_german_and_english_words():
    assert tag_words("Öffne das Update von GitHub.", "de") == [
        ("Öffne", "de"), ("das", "de"), ("Update", "en"), ("von", "de"), ("GitHub.", "en")]
    assert tag_words("ESP32-P4 mit USB", "de") == [("ESP32-P4", "neutral"), ("mit", "de"), ("USB", "de")]


@pytest.mark.parametrize("word, lang", [
    ("Straße", "de"), ("Größe", "de"), ("in", "de"), ("was", "de"), ("Name", "de"), ("Hand", "de"),
    ("Haus", "de"), ("bewegen", "de"), ("Schmetterling", "de"), ("Bahnhof", "de"), ("Theater", "de"),
    ("update", "en"), ("online", "en"), ("Laptop", "en"), ("the", "en"), ("YouTube", "en"),
    ("Bluetooth", "en"), ("Smartphone", "en"), ("Meeting", "en"), ("Wi-Fi", "en"), ("Party", "en"),
])
def test_word_lang(word, lang):
    assert word_lang(word, "de") == lang


def test_german_sentence():
    assert ph("Guten Tag!") == "g u:1 t @ n _ t a:1 k !"
    assert "EN:" not in " ".join(flat("Der Hund läuft jeden Morgen durch den großen Park."))


def test_mixed_de_en():
    toks = flat("Ich lade das Update für die Software herunter.")
    assert "EN:AH" in toks and "DE:C" in toks and toks[-1] == "."
    assert flat("Der Laptop ist langsam.").count(" ") == 3


def test_numbers_dates_and_codes_in_german():
    assert flat("Ich habe 21 Äpfel.") == flat("Ich habe einundzwanzig Äpfel.")
    assert flat("um 14:30 Uhr") == flat("um vierzehn Uhr dreißig")
    assert flat("ESP32") == flat("e ess pe drei zwei")
    assert flat("Am 3. Mai kommt er.") == flat("Am dritten Mai kommt er.")
    assert len(text_to_tokens("Das sind z. B. Äpfel. Gut.", "de")) == 2


def test_ids_use_deen_set_and_english_ids_match_v2():
    ids = text_to_ids("Öffne bitte YouTube.", "de")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("de-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_DEEN)
    assert text_to_ids("Please open the app.", "en") == text_to_ids("Please open the app.", "de")


def test_other_modes_unchanged_by_german():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Größe, Straße und Bär", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2
    assert split_sentences_raw("Am 3. Mai. Gut.") == ["Am 3.", "Mai.", "Gut."]  # other modes split as before
    assert split_sentences_raw("Am 3. Mai. Gut.", "de") == ["Am 3. Mai.", "Gut."]


def test_long_german_text_is_chunked():
    one = "der kleine hund des nachbarn läuft jeden morgen durch den großen park am fluss"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "de")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
