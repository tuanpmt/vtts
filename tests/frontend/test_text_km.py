"""text_to_ids(text, "km"): Khmer + English, token set km-en."""

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_KMEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="km"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def test_tagging_khmer_and_english():
    assert tag_words("សូមបើកWi-Fiឱ្យខ្ញុំ", "km") == [
        ("សូមបើក", "km"), ("Wi-Fi", "en"), ("ឱ្យខ្ញុំ", "km")]
    assert tag_words("បើក Netflix ២ ម៉ោង", "km") == [
        ("បើក", "km"), ("Netflix", "en"), ("២", "neutral"), ("ម៉ោង", "km")]
    assert word_lang("សួស្តី", "km") == "km" and word_lang("hello", "km") == "en"


def test_other_modes_unchanged_by_khmer():
    assert word_lang("សួស្តី", "vi") == "vi"  # as before: any non-ASCII letter
    assert word_lang("សួស្តី", "th") == "neutral"
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, សួស្តី", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2


def test_khmer_full_stop_ends_a_sentence():
    assert split_sentences_raw("ខ្ញុំទៅផ្សារ។ គាត់នៅផ្ទះ។") == ["ខ្ញុំទៅផ្សារ។", "គាត់នៅផ្ទះ។"]
    assert split_sentences_raw("ខ្ញុំទៅផ្សារ។គាត់នៅផ្ទះ៕") == ["ខ្ញុំទៅផ្សារ។", "គាត់នៅផ្ទះ៕"]
    assert split_sentences_raw("ព.ស. ២៥៦៩ ជាឆ្នាំថ្មី។") == ["ព.ស. ២៥៦៩ ជាឆ្នាំថ្មី។"]
    assert flat("ខ្ញុំទៅផ្សារ។")[-1] == "."


def test_khmer_run_has_no_space_between_syllables_and_spaces_are_pauses():
    toks = flat("ខ្ញុំស្រលាញ់ប្រទេសកម្ពុជា")
    assert " " not in toks and toks[:4] == ["KM:k", "KM:ny", "KM:o", "KM:F:m"]
    toks = flat("សួស្តី អ្នកសុខសប្បាយទេ")
    assert toks.count(",") == 1 and " " not in toks


def test_mixed_km_en():
    toks = flat("សូមបើក Wi-Fi ឱ្យខ្ញុំ")
    assert "EN:W" in toks and toks.count(" ") == 3  # km | wi | fi | km
    assert flat("សូមបើកWi-Fiឱ្យខ្ញុំ") == toks


def test_numbers_in_khmer():
    assert flat("មាន 21 នាក់") == flat("មានម្ភៃមួយនាក់")
    assert flat("១០១") == flat("មួយរយមួយ")


def test_ids_use_kmen_set_and_english_ids_match_v2():
    ids = text_to_ids("បើក YouTube ឱ្យខ្ញុំ", "km")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("km-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_KMEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "km")


def test_long_khmer_text_is_chunked():
    one = "កាលពីម្សិលមិញខ្ញុំបានទៅដើរលេងនៅមាត់សមុទ្រជាមួយក្រុមគ្រួសារនិងមិត្តភក្តិជាច្រើននាក់"
    chunks = text_to_tokens(" ".join([one] * 6), "km")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
    chunks = text_to_tokens(one * 6, "km")  # no space at all: cut by the syllable limit
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
