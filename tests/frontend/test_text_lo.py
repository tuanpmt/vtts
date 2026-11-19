"""text_to_ids(text, "lo"): Lao + English, token set lo-en."""

from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_LOEN, VOCAB_SIZE_LOEN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="lo"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def test_token_set_size():
    assert VOCAB_SIZE_LOEN == len(TOKENS_LOEN) == 163
    assert TOKENS_LOEN[:VOCAB_SIZE_V2] == tuple(token_index("vi-en"))


def test_tagging_lao_and_english():
    assert tag_words("ເປີດWi-Fiໃຫ້ແດ່", "lo") == [("ເປີດ", "lo"), ("Wi-Fi", "en"), ("ໃຫ້ແດ່", "lo")]
    assert word_lang("ສະບາຍດີ", "lo") == "lo" and word_lang("YouTube", "lo") == "en"
    assert word_lang("ສະບາຍດີ", "th") == "neutral" and word_lang("ສະບາຍດີ", "vi") == "vi"


def test_syllables_join_without_space_and_spaces_are_pauses():
    toks = flat("ສະບາຍດີ ຂ້ອຍຊື່ແກ້ວ")
    assert " " not in toks and "," in toks
    assert toks.count("LO:T1") >= 2


def test_dot_after_lao_letter_does_not_end_a_sentence():
    assert split_sentences_raw("ປີ ຄ.ສ. 2024 ດີ! Hello.", "lo") == ["ປີ ຄ.ສ. 2024 ດີ!", "Hello."]
    assert split_sentences_raw("ປີ ຄ.ສ. 2024", "th") == ["ປີ ຄ.ສ.", "2024"]  # other modes unchanged
    assert flat("ປີ ຄ.ສ. 2024") == flat("ປີຄິດສະຕະສັກກະລາດສອງພັນຊາວສີ່")


def test_numbers_in_lao():
    assert flat("ມີ 21 ຄົນ") == flat("ມີຊາວເອັດຄົນ")


def test_ids_use_loen_set_and_english_ids_match_v2():
    ids = text_to_ids("ເປີດ YouTube ໃຫ້ແດ່", "lo")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("lo-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_LOEN)
    assert text_to_ids("Turn on the Wi-Fi.", "en") == text_to_ids("Turn on the Wi-Fi.", "lo")


def test_other_modes_unchanged_by_lao():
    for mode in ("vi", "en", "auto"):
        ids = [i for ch in text_to_ids("Xin chào, hello", mode) for i in ch]
        assert max(ids) < VOCAB_SIZE_V2


def test_long_lao_text_is_chunked():
    one = "ເດັກນ້ອຍໃນໂຮງຮຽນຊ່ວຍກັນປູກຕົ້ນໄມ້ອ້ອມເດີ່ນບານ"
    chunks = text_to_tokens(" ".join([one] * 12), "lo")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
