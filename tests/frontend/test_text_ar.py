"""text_to_ids(text, "ar"): Arabic + English, token set ar-en."""

from pathlib import Path

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_AREN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens

TEMPLATES = Path(__file__).resolve().parents[2] / "scripts" / "data" / "bilingual" / "templates_ar.txt"


def flat(text, lang="ar"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("AR:") for t in flat(text))


def test_tagging_arabic_and_latin_words():
    assert tag_words("افتح YouTube على التلفاز، من فضلك.", "ar") == [
        ("افتح", "ar"), ("YouTube", "en"), ("على", "ar"), ("التلفاز،", "ar"), ("من", "ar"),
        ("فضلك.", "ar")]
    assert tag_words("Wi-Fi، نعم", "ar")[0] == ("Wi-Fi،", "en")
    assert word_lang("ESP32", "ar") == "neutral"
    assert word_lang("km", "ar") == "ar" and word_lang("USD", "ar") == "ar"
    assert word_lang("٢٠٢٤", "ar") == "neutral"


def test_arabic_sentence():
    assert ph("ذهب الولد إلى المدرسة.") == (
        "dh a1 h a b _ a l w a1 l a d _ ? i1 l aa _ a l m a1 d r a s a .")
    assert "EN:" not in " ".join(flat("السلام عليكم، كيف حالك اليوم؟"))


def test_arabic_marks_end_sentences():
    assert split_sentences_raw("كيف حالك؟ أنا بخير؛ شكرا. مع السلامة") == [
        "كيف حالك؟", "أنا بخير؛", "شكرا.", "مع السلامة"]
    chunks = text_to_tokens("كيف حالك؟ أنا بخير.", "ar")
    assert len(chunks) == 2 and chunks[0][-1] == "?" and chunks[1][-1] == "."
    assert "," in flat("نعم، شكرا")


def test_mixed_ar_en():
    toks = flat("قمت بتحديث software على laptop أمس.")
    assert "EN:AE" in toks and "AR:3" not in toks[:0] and toks[-1] == "."
    assert flat("Wi-Fi لا يعمل")[:len(flat("Wi-Fi", "en"))] == flat("Wi-Fi", "en")
    assert flat("هاتفي يدعم 5G") == flat("هاتفي يدعم خَمْسَة جِي")


def test_numbers_in_arabic():
    assert flat("عمري 21 سنة.") == flat("عمري وَاحِد وَعِشْرُون سنة.")
    assert flat("عمري ٢١ سنة.") == flat("عمري 21 سنة.")
    assert flat("عمري ۲۱ سنة.") == flat("عمري 21 سنة.")


def test_vowel_marks_in_the_text_are_used():
    assert ph("عِلْم") == "3 i l m" and ph("عَلَم") == "3 a1 l a m"


def test_ids_use_aren_set_and_english_ids_match_v2():
    ids = text_to_ids("افتح YouTube من فضلك.", "ar")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("ar-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_AREN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "ar")


def test_other_modes_unchanged_by_arabic():
    for mode in ("vi", "en", "auto", "es", "hi", "th"):
        assert word_lang("مرحبا", mode) != "ar"
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, مرحبا", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2


def test_templates_are_readable():
    from vtts.data.train_list import unreadable

    for line in TEMPLATES.read_text(encoding="utf-8").splitlines():
        text = line.replace("{T}", "Bluetooth")
        assert not unreadable(text, "ar"), text
        toks = flat(text)
        assert any(t.startswith("AR:") for t in toks) and "EN:UW" in toks, text


def test_long_arabic_text_is_chunked():
    one = "نذهب كل يوم جمعة إلى الحديقة الكبيرة ونلعب مع الأطفال حتى المساء"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "ar")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    words = [sum(1 for t in c if t == " ") + 1 for c in chunks]
    assert all(w <= 40 for w in words)
