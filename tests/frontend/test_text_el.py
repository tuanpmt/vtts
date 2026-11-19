"""text_to_ids(text, "el"): Greek + English, token set el-en."""

from pathlib import Path

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_ELEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens

TEMPLATES = Path(__file__).resolve().parents[2] / "scripts" / "data" / "bilingual" / "templates_el.txt"


def flat(text, lang="el"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("EL:") for t in flat(text))


def test_tagging_greek_and_latin_words():
    assert tag_words("Άνοιξες το Netflix;", "el") == [("Άνοιξες", "el"), ("το", "el"), ("Netflix?", "en")]
    assert word_lang("Wi-Fi", "el") == "en" and word_lang("ESP32", "el") == "neutral"
    assert word_lang("km", "el") == "el" and word_lang("GB", "el") == "el"  # units of the normalizer


def test_greek_question_mark():
    assert split_sentences_raw("Τι κάνεις; Καλά.", "el") == ["Τι κάνεις;", "Καλά."]
    chunks = text_to_tokens("Τι κάνεις; Άνοιξες το Netflix; Καλά.", "el")
    assert [c[-1] for c in chunks] == ["?", "?", "."]


def test_greek_sentence():
    assert ph("Καλημέρα, τι κάνεις;") == "k a l i m e1 r a , t i1 _ k a1 n i s ?"
    assert "EN:" not in " ".join(flat("Τα παιδιά παίζουν στην αυλή του σχολείου."))


def test_dot_before_lower_case_word_is_not_a_sentence_end():
    assert len(split_sentences_raw("Ο κ. Παπαδόπουλος ήρθε. Μετά έφυγε.", "el")) == 3  # κ. + capital
    assert split_sentences_raw("Είναι περ. είκοσι.", "el") == ["Είναι περ. είκοσι."]


def test_mixed_el_en():
    toks = flat("Άνοιξε το GitHub και βρες το project.")
    assert "EN:G" in toks and "EL:k" in toks and toks[-1] == "."
    assert flat("Το κινητό έχει 5G") == flat("Το κινητό έχει πέντε τζι")


def test_numbers_in_greek():
    assert flat("Είμαι 21 χρονών.") == flat("Είμαι είκοσι ένα χρονών.")
    assert flat("στις 7:30") == flat("στις επτά και τριάντα")


def test_ids_use_elen_set_and_english_ids_match_v2():
    ids = text_to_ids("Άνοιξε το GitHub, παρακαλώ.", "el")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("el-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_ELEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "el")


def test_other_modes_unchanged_by_greek():
    for mode in ("vi", "en", "auto", "es", "fi"):
        assert word_lang("Αθήνα", mode) != "el"
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, Αθήνα", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2


def test_templates_are_readable():
    from vtts.data.train_list import unreadable

    for line in TEMPLATES.read_text(encoding="utf-8").splitlines():
        text = line.replace("{T}", "Bluetooth")
        assert not unreadable(text, "el"), text
        toks = flat(text)
        assert any(t.startswith("EL:") for t in toks) and "EN:UW" in toks, text


def test_long_greek_text_is_chunked():
    one = "ο σκύλος του γείτονα γαβγίζει κάθε πρωί όταν ο ταχυδρόμος φέρνει την εφημερίδα"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "el")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    assert all(sum(1 for t in c if t == " ") + 1 <= 40 for c in chunks)
