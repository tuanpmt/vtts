from vtts.data.filter import Row, apply_filters


def test_filters_each_reason():
    rows = [
        Row("ok", "xin chào bạn", 3.0, asr="xin chào bạn", dnsmos_ovrl=3.5),
        Row("cer", "xin chào bạn", 3.0, asr="tạm biệt nhé", dnsmos_ovrl=3.5),
        Row("dns", "xin chào bạn", 3.0, asr="xin chào bạn", dnsmos_ovrl=2.0),
        Row("short", "xin chào bạn", 0.5, asr="xin chào bạn", dnsmos_ovrl=3.5),
        Row("long", "xin chào bạn", 20.0, asr="xin chào bạn", dnsmos_ovrl=3.5),
        Row("bad", "", 3.0, asr="", dnsmos_ovrl=3.5),
        Row("noscore", "xin chào bạn", 3.0, asr=None, dnsmos_ovrl=None),
    ]
    kept, reasons = apply_filters(rows)
    assert [r.id for r in kept] == ["ok"]
    assert reasons == {"cer": 1, "dnsmos": 1, "too_short": 1, "too_long": 1,
                       "invalid_text": 1, "unscored": 1}


def test_rows_with_spelled_out_words_are_rejected():
    rows = [Row("qwz", "chung cư qwz", 3.0, asr="chung cư qwz", dnsmos_ovrl=3.5),
            Row("hlv", "hlv đội tuyển", 3.0, asr="huấn luyện viên đội tuyển", dnsmos_ovrl=3.5)]
    kept, reasons = apply_filters(rows)
    assert kept == [] and reasons == {"spelled_word": 2}
