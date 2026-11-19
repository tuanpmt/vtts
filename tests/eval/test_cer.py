import pytest

from vtts.eval.cer import cer, corpus_cer, prep_for_cer, wer


def test_cer_tone_sensitive():
    assert cer("ma", "mà") == 0.5


def test_cer_ignores_case_punct_and_digits():
    assert cer("Hai mươi mốt.", "hai mươi mốt") == 0.0
    assert cer("21", "hai mươi mốt") == 0.0


def test_corpus_cer():
    # 0 errors in "ba" (2 chars) + 1 error in "cơm" (3 chars) -> 1/5, not the mean of clip CERs
    assert corpus_cer([("ba", "ba"), ("cơm", "cờm")]) == pytest.approx(1 / 5)


def test_wer_counts_words():
    assert wer("xin chào bạn", "xin chao bạn") == pytest.approx(1 / 3)


def test_prep_keeps_tones():
    assert prep_for_cer("Việt Nam!") == "việt nam"


def test_cer_ignores_tone_placement_style():
    assert cer("hoà bình", "hòa bình") == 0.0
    assert cer("thuỷ", "thủy") == 0.0


def test_english_normalization_matches_spoken_forms():
    from vtts.eval.cer import cer, prep_for_cer
    assert prep_for_cer("Battery level is at 15 percent.", "en") == "battery level is at fifteen percent"
    assert cer("The meeting starts at 9:30.", "the meeting starts at nine thirty", "en") == 0.0


def test_mixed_keeps_english_words_and_reads_numbers():
    from vtts.eval.cer import prep_for_cer, wer
    assert prep_for_cer("Pin AirPods còn 20%, nhớ sạc nhé.", "mixed") == "pin airpods còn hai mươi phần trăm nhớ sạc nhé"
    assert wer("Mở Spotify và play playlist.", "mở spotify và play playlist", "mixed") == 0.0


def test_vietnamese_default_unchanged():
    from vtts.eval.cer import prep_for_cer
    assert prep_for_cer("Pin còn 15%.") == prep_for_cer("Pin còn 15%.", "vi") == "pin còn mười lăm phần trăm"


def test_zh_character_units_simplified_and_numbers_read():
    from vtts.eval.cer import cer, prep_for_cer
    assert prep_for_cer("打开Wi-Fi，电量20%。", "zh") == "打 开 wi fi 电 量 百 分 之 二 十"
    assert cer("今天天气很好。", "今天天氣很好", "zh") == 0.0
    assert cer("福建福清人", "福建福情人", "zh") == pytest.approx(1 / 5)
    assert cer("电量20%。", "电量百分之二十", "zh") == 0.0


def test_cjk_cer_ignores_spacing_of_latin_terms():
    from vtts.eval.cer import cer, wer
    assert cer("打开Wi-Fi。", "打开 WiFi", "zh") == 0.0
    assert cer("打开Spotify。", "打开 Spot ify", "zh") == 0.0
    # WER counts a Han character or a Latin word as one unit: spotify vs spot ify differ
    assert wer("打开Spotify。", "打开Spot ify", "zh") == pytest.approx(2 / 3)


def test_ko_syllable_cer_and_word_wer():
    from vtts.eval.cer import cer, prep_for_cer, wer
    assert prep_for_cer("Wi-Fi를 켜 주세요. 3시 30분!", "ko") == "wi fi 를 켜 주세요 세 시 삼십 분"
    assert cer("불을 켜 주세요.", "불을 켜주세요", "ko") == 0.0  # spacing is not a character
    assert cer("불을 켜 주세요.", "불을 꺼 주세요", "ko") == pytest.approx(1 / 6)
    assert wer("불을 켜 주세요.", "불을 꺼 주세요", "ko") == pytest.approx(1 / 3)


def test_ja_katakana_as_hiragana_and_numbers_read():
    from vtts.eval.cer import cer, prep_for_cer
    assert cer("テレビをつけて。", "てれびをつけて", "ja") == 0.0
    assert cer("3時30分です。", "三時三十分です", "ja") > 0  # kanji vs reading: spelling counts
    assert cer("3時30分です。", "3時30分です", "ja") == 0.0
    assert prep_for_cer("Wi-Fiを設定。", "ja") == "wi fi を 設 定"


def test_corpus_cer_cjk_counts_characters():
    from vtts.eval.cer import corpus_cer, corpus_wer
    assert corpus_cer([("你好", "你好"), ("打开灯", "打开等")], "zh") == pytest.approx(1 / 5)
    assert corpus_wer([("你好", "你好"), ("打开灯", "打开等")], "zh") == pytest.approx(1 / 5)


def test_latin_pair_cer_reads_numbers_and_keeps_spaces():
    from vtts.eval.cer import WHISPER_LANGUAGE, cer, prep_for_cer, wer
    assert prep_for_cer("Abre GitHub a las 7:30.", "es") == "abre git hub a las siete y treinta"
    assert cer("Tengo 21 años.", "tengo veintiún años", "es") == 0.0
    assert cer("La casa.", "la cosa", "es") == pytest.approx(1 / 7)  # "la casa": 7 characters
    assert wer("La casa es grande.", "la cosa es grande", "es") == pytest.approx(1 / 4)
    assert WHISPER_LANGUAGE["es"] == "es"
    assert cer("Tenho 21 anos.", "tenho vinte e um anos", "pt") == 0.0
    assert WHISPER_LANGUAGE["pt"] == "pt"
    assert cer("มี 21 คน", "มียี่สิบเอ็ดคน", "th") == 0.0  # Thai: spaces and numbers do not count
    assert WHISPER_LANGUAGE["th"] == "th"
    assert cer("Ada 21 orang.", "ada dua puluh satu orang", "id") == 0.0
    assert WHISPER_LANGUAGE["id"] == "id"
    assert cer("J'ai 21 ans.", "j'ai vingt et un ans", "fr") == 0.0  # liaison on both sides
    assert WHISPER_LANGUAGE["fr"] == "fr"
    assert cer("Ich habe 21 Äpfel.", "ich habe einundzwanzig äpfel", "de") == 0.0
    assert prep_for_cer("Am 3. Mai um 14:30 Uhr.", "de") == "am dritten mai um vierzehn uhr dreißig"
    assert WHISPER_LANGUAGE["de"] == "de"
    assert cer("Ho 21 anni.", "ho ventun anni", "it") == 0.0
    assert prep_for_cer("Apri l’app alle 7:30.", "it") == "apri l\u02bc app alle sette e trenta"
    assert WHISPER_LANGUAGE["it"] == "it"
    assert cer("21 yaşındayım.", "yirmi bir yaşındayım", "tr") == 0.0
    assert prep_for_cer("İstanbul’da 5. sınıf.", "tr") == "istanbul'da beşinci sınıf"
    assert WHISPER_LANGUAGE["tr"] == "tr"


def test_hindi_cer_reads_numbers_and_keeps_spaces():
    from vtts.eval.cer import WHISPER_LANGUAGE, cer, prep_for_cer
    assert prep_for_cer("मेरी उम्र 21 साल है।", "hi") == "मेरी उम्र इक्कीस साल है"
    assert cer("मेरी उम्र २१ साल है।", "मेरी उम्र इक्कीस साल है", "hi") == 0.0
    assert prep_for_cer("YouTube खोलो।", "hi") == "you tube खोलो"
    assert WHISPER_LANGUAGE["hi"] == "hi"


def test_dutch_cer_reads_numbers_and_keeps_spaces():
    from vtts.eval.cer import WHISPER_LANGUAGE, cer, prep_for_cer
    assert prep_for_cer("Ik ben 21 jaar.", "nl") == "ik ben eenentwintig jaar"
    assert cer("Het kost € 5,50.", "het kost vijf euro en vijftig cent", "nl") == 0.0
    assert WHISPER_LANGUAGE["nl"] == "nl"
    assert cer("Olen 21 vuotta.", "olen kaksikymmentäyksi vuotta", "fi") == 0.0
    assert cer("Kokous 3. toukokuuta.", "kokous kolmas toukokuuta", "fi") == 0.0
    assert WHISPER_LANGUAGE["fi"] == "fi"
    assert cer("Είμαι 21 χρονών.", "είμαι είκοσι ένα χρονών", "el") == 0.0
    assert prep_for_cer("Άνοιξες το Netflix;", "el") == "άνοιξες το netflix"
    assert WHISPER_LANGUAGE["el"] == "el"


def test_polish_cer_reads_numbers():
    from vtts.eval.cer import WHISPER_LANGUAGE, cer, prep_for_cer
    assert prep_for_cer("Mam 21 lat.", "pl") == "mam dwadzieścia jeden lat"
    assert cer("Mam 21 lat.", "mam dwadzieścia jeden lat", "pl") == 0.0
    assert WHISPER_LANGUAGE["pl"] == "pl"


def test_russian_cer_reads_numbers_and_folds_yo():
    from vtts.eval.cer import WHISPER_LANGUAGE, cer, prep_for_cer
    assert prep_for_cer("Мне 21 год.", "ru") == "мне двадцать один год"
    assert cer("Она ещё в доме.", "она еще в доме", "ru") == 0.0
    assert prep_for_cer("Открой YouTube.", "ru") == "открой you tube"
    assert WHISPER_LANGUAGE["ru"] == "ru"


def test_arabic_cer_reads_numbers_and_ignores_vowel_marks():
    from vtts.eval.cer import WHISPER_LANGUAGE, cer, prep_for_cer
    assert prep_for_cer("عمري 21 سنة.", "ar") == "عمري واحد وعشرون سنة"
    assert cer("عمري ٢١ سنة.", "عُمْرِي وَاحِد وَعِشْرُونَ سَنَة", "ar") == 0.0
    assert prep_for_cer("افتح YouTube.", "ar") == "افتح you tube"
    assert WHISPER_LANGUAGE["ar"] == "ar"


def test_malay_cer_reads_numbers():
    from vtts.eval.cer import WHISPER_LANGUAGE, cer, prep_for_cer
    assert cer("Ada 8 orang.", "ada lapan orang", "ms") == 0.0
    assert prep_for_cer("Harga RM12.50.", "ms") == "harga dua belas ringgit lima puluh sen"
    assert WHISPER_LANGUAGE["ms"] == "ms"


def test_tagalog_cer_reads_numbers():
    from vtts.eval.cer import WHISPER_LANGUAGE, cer, prep_for_cer
    assert cer("May 3 aso.", "may tatlong aso", "tl") == 0.0
    assert prep_for_cer("Alas 3:30 na.", "tl") == "alas tres i medya na"
    assert WHISPER_LANGUAGE["tl"] == "tl"


def test_swahili_cer_reads_numbers():
    from vtts.eval.cer import WHISPER_LANGUAGE, cer, prep_for_cer
    assert cer("Watu 3.", "watu tatu", "sw") == 0.0
    assert prep_for_cer("Bei ni TSh 5,000.", "sw") == "bei ni shilingi elfu tano"
    assert WHISPER_LANGUAGE["sw"] == "sw"


def test_main_script_cer_skips_english_words():
    from vtts.eval.cer import main_script_cer
    ref = "사진을 Google Drive에 백업했습니다."
    # Whisper writes the English words in Hangul: plain CER counts them, the Hangul-only CER does not
    assert corpus_cer([(ref, "사진을 구글 드라이브에 백업했습니다.")], "ko") > 0.3
    assert main_script_cer([(ref, "사진을 구글 드라이브에 백업했습니다.")], "ko") == 0.0
    assert main_script_cer([(ref, "사진을 Google Drive에 백업했습니다.")], "ko") == 0.0
    # a wrong Hangul syllable counts: 1 of 10 Hangul characters
    assert main_script_cer([(ref, "사진을 Google Drive에 백업했습니까.")], "ko") == pytest.approx(1 / 10)
    # a dropped Hangul syllable and an insertion inside a Hangul word count
    assert main_script_cer([("거실 불을 켜 드릴까요?", "거실 불 켜 드릴까요")], "ko") == pytest.approx(1 / 9)
    assert main_script_cer([("거실 불을 켜 드릴까요?", "거실 불을을 켜 드릴까요")], "ko") == pytest.approx(1 / 9)
