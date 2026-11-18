from vtts.data.ja_corpus import accept_ja, char_count, ja_morae, ja_seconds, plain_ja, split_ja


def test_split_keeps_end_punctuation_without_spaces():
    assert split_ja("今日は晴れです。明日は雨かな？行こう！") == ["今日は晴れです。", "明日は雨かな？", "行こう！"]
    assert split_ja("  ") == []


def test_accept_plain_sentence():
    assert accept_ja("東京は日本の首都であり、最大の都市である。")
    assert accept_ja("彼は「おはようございます」と言って部屋に入った。")
    assert accept_ja("あなたは明日の会議に出席しますか？")
    assert accept_ja("ジョン・スミスはアメリカの作家である。")


def test_reject_digits_latin_brackets():
    assert not accept_ja("この会社は2001年に設立され、本社は東京にある。")
    assert not accept_ja("この会社は２００１年に設立され、本社は東京にある。")
    assert not accept_ja("彼はNASAで長く働いた後に日本へ戻った。")
    assert not accept_ja("東京（とうきょう）は日本の首都である。")
    assert not accept_ja("東京は日本の首都である（諸説あり）。")


def test_reject_length_ending_and_marks():
    assert not accept_ja("こんにちは。")                         # under 10 characters
    assert not accept_ja("東京は日本の首都であり最大の都市である")      # no end mark
    assert not accept_ja("あ" * 61 + "。")
    assert not accept_ja("東京は日本の首都であり、、最大の都市である。")
    assert not accept_ja("彼は「おはようございますと言って部屋に入った。")  # unbalanced quote


def test_reject_kanji_without_reading():
    s = "この文字は龘という字で画数がとても多い。"                    # 龘: no reading in the tables
    assert plain_ja(s) and not accept_ja(s)


def test_count_and_duration():
    assert char_count("東京、日本。") == 4
    assert ja_morae("がっこう") == 4
    assert ja_seconds("がっこう") == 4 / 7.5
