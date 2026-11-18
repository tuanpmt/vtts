from vtts.data.zh_corpus import accept_zh, han_count, split_zh, zh_seconds


def test_split_keeps_end_punctuation():
    assert split_zh("今天天气很好。我们去公园吧！你去吗？") == ["今天天气很好。", "我们去公园吧！", "你去吗？"]


def test_split_ignores_blank():
    assert split_zh("  ") == []


def test_accept_plain_sentence():
    assert accept_zh("北京是中华人民共和国的首都，也是全国的政治中心。")


def test_reject_digits_latin_and_brackets():
    assert not accept_zh("该公司成立于2001年，总部位于上海。")
    assert not accept_zh("他在NASA工作了很多年，后来回到了中国。")
    assert not accept_zh("长江（英语：Yangtze）是亚洲最长的河流之一。")


def test_reject_traditional_characters():
    assert not accept_zh("這個城市的歷史非常悠久，吸引了很多遊客。")


def test_reject_length_and_ending():
    assert not accept_zh("你好。")
    assert not accept_zh("北京是中华人民共和国的首都，也是全国的政治中心")


def test_count_and_duration():
    assert han_count("你好，世界。") == 4
    assert zh_seconds("你好，世界。") == 4 / 4.5
