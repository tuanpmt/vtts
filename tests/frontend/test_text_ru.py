"""text_to_ids(text, "ru"): Russian + English, token set ru-en."""

from pathlib import Path

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_RUEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens

TEMPLATES = Path(__file__).resolve().parents[2] / "scripts" / "data" / "bilingual" / "templates_ru.txt"


def flat(text, lang="ru"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("RU:") for t in flat(text))


def test_tagging_cyrillic_and_latin_words():
    assert tag_words("Открой YouTube на iPhone.", "ru") == [
        ("Открой", "ru"), ("YouTube", "en"), ("на", "ru"), ("iPhone.", "en")]
    assert word_lang("Wi-Fi", "ru") == "en" and word_lang("ESP32", "ru") == "neutral"
    assert word_lang("km", "ru") == "ru" and word_lang("GB", "ru") == "ru"  # units of the normalizer
    assert word_lang("Київ", "ru") == "ru"


def test_russian_sentence():
    assert ph("Привет, как дела?") == "p r' i v' e1 t , k a1 k _ d' i l a1 ?"
    assert "EN:" not in " ".join(flat("Мы завтра утром поедем на дачу и соберём яблоки."))


def test_abbreviations_do_not_end_a_sentence():
    assert split_sentences_raw("Это т. е. пример. Новое предложение! Да.") == [
        "Это т. е. пример.", "Новое предложение!", "Да."]
    assert split_sentences_raw("Улицы, дома и т. п. остались. Всё.") == [
        "Улицы, дома и т. п. остались.", "Всё."]


def test_mixed_ru_en():
    toks = flat("Я обновил software на laptop.")
    assert "EN:AE" in toks and "RU:j" in toks and toks[-1] == "."
    assert flat("Wi-Fi не работает.")[:len(flat("Wi-Fi", "en"))] == flat("Wi-Fi", "en")
    assert flat("У меня 5G") == flat("У меня пять джи")


def test_numbers_in_russian():
    assert flat("Мне 21 год.") == flat("Мне двадцать один год.")
    assert flat("Встреча в 7:30.") == flat("Встреча в семь тридцать.")


def test_clitic_prepositions_join_the_next_word():
    assert ph("в доме") == "v d o1 m' i"  # one word: no pause token, voicing across
    assert ph("к дому") == "g d o1 m u"


def test_ids_use_ruen_set_and_english_ids_match_v2():
    ids = text_to_ids("Открой YouTube, please.", "ru")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("ru-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_RUEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "ru")


def test_other_modes_unchanged_by_russian():
    for mode in ("vi", "en", "auto", "es", "pt", "hi"):
        assert word_lang("Привет", mode) != "ru"
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, Привет", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2


def test_templates_are_readable():
    from vtts.data.train_list import unreadable

    for line in TEMPLATES.read_text(encoding="utf-8").splitlines():
        text = line.replace("{T}", "Bluetooth")
        assert not unreadable(text, "ru"), text
        toks = flat(text)
        assert any(t.startswith("RU:") for t in toks) and "EN:UW" in toks, text


def test_long_russian_text_is_chunked():
    one = "мы каждое воскресенье ходим в парк и гуляем там вместе с детьми и собакой"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "ru")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    words = [sum(1 for t in c if t == " ") + 1 for c in chunks]
    assert all(w <= 40 for w in words)
