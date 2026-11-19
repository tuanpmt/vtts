"""Khmer normalization (km/normalize_km.py on frontend/nospace_norm.py)."""

import pytest

from vtts.frontend.km.normalize_km import cardinal, is_khmer_word, normalize_km


@pytest.mark.parametrize("n, words", [
    (0, "សូន្យ"), (1, "មួយ"), (5, "ប្រាំ"), (6, "ប្រាំមួយ"), (9, "ប្រាំបួន"), (10, "ដប់"),
    (11, "ដប់មួយ"), (20, "ម្ភៃ"), (21, "ម្ភៃមួយ"), (35, "សាមសិបប្រាំ"), (99, "កៅសិបប្រាំបួន"),
    (100, "មួយរយ"), (101, "មួយរយមួយ"), (1000, "មួយពាន់"), (2026, "ពីរពាន់ម្ភៃប្រាំមួយ"),
    (15000, "មួយម៉ឺនប្រាំពាន់"), (250000, "ពីរសែនប្រាំម៉ឺន"), (1_000_000, "មួយលាន"),
    (3_500_000, "បីលានប្រាំសែន"), (1_000_000_000, "មួយពាន់លាន"), (-7, "ដកប្រាំពីរ"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("text, out", [
    ("ខ្ញុំមាន ២១ ឆ្នាំ។", "ខ្ញុំមានម្ភៃមួយឆ្នាំ ."),                         # Khmer digits, ។ is "."
    ("តម្លៃ 5000៛", "តម្លៃប្រាំពាន់រៀល"),                                      # riel after the number
    ("តម្លៃ $2.50", "តម្លៃពីរចុចប្រាំសូន្យដុល្លារ"),                            # decimals digit by digit
    ("កើនឡើង 50%", "កើនឡើងហាសិបភាគរយ"),
    ("ថ្ងៃទី 19/11/2026", "ថ្ងៃទីដប់ប្រាំបួនខែវិច្ឆិកាឆ្នាំពីរពាន់ម្ភៃប្រាំមួយ"),  # ថ្ងៃទី once
    ("2026-11-19", "ថ្ងៃទីដប់ប្រាំបួនខែវិច្ឆិកាឆ្នាំពីរពាន់ម្ភៃប្រាំមួយ"),
    ("ម៉ោង 14:30", "ម៉ោងដប់បួនសាមសិបនាទី"),
    ("ម៉ោង ១៤:០៥:០៩", "ម៉ោងដប់បួនប្រាំនាទីប្រាំបួនវិនាទី"),
    ("ទូរស័ព្ទ 012-345-678", "ទូរស័ព្ទសូន្យមួយពីរបីបួនប្រាំប្រាំមួយប្រាំពីរប្រាំបី"),
    ("ពី 10-20 នាក់", "ពីដប់ដល់ម្ភៃនាក់"),
    ("សីតុណ្ហភាព -3°C", "សីតុណ្ហភាពដកបីអង្សាសេ"),
    ("ចម្ងាយ 5 km", "ចម្ងាយប្រាំគីឡូម៉ែត្រ"),
    ("ព.ស. ២៥៦៩", "ពុទ្ធសករាជពីរពាន់ប្រាំរយហុកសិបប្រាំបួន"),
    ("ប្រជាជន 17,000,000 នាក់", "ប្រជាជនដប់ប្រាំពីរលាននាក់"),
    ("ផ្ទះ ៗ", "ផ្ទះៗ"),                                                        # ៗ joins the word
    ("ប្រទេស\u200bកម្ពុជា", "ប្រទេសកម្ពុជា"),                                    # zero-width space
    ("ដូច្នេះ៖ មួយ", "ដូច្នេះ : មួយ"),
])
def test_normalize(text, out):
    assert normalize_km(text) == out


def test_space_between_khmer_runs_is_a_pause():
    assert normalize_km("សួស្តី អ្នកសុខសប្បាយទេ") == "សួស្តី , អ្នកសុខសប្បាយទេ"
    assert normalize_km("តម្លៃ 100 រៀល") == "តម្លៃមួយរយរៀល"  # spaces around numbers are not pauses


def test_latin_goes_to_english_and_codes_are_spelled():
    assert normalize_km("បើក ESP32") == "បើក e s p បីពីរ"
    assert normalize_km("បើក Wi-Fi") == "បើក wi fi"


def test_khmer_word():
    assert is_khmer_word("ផ្ទះៗ") and not is_khmer_word("wifi") and not is_khmer_word("១២")
