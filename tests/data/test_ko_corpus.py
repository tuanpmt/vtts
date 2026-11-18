from vtts.data.ko_corpus import accept_ko, ko_seconds, split_ko, syllable_count


def test_split_keeps_end_punctuation():
    assert split_ko("오늘은 날씨가 좋다. 공원에 갈까? 가자!") == ["오늘은 날씨가 좋다.", "공원에 갈까?", "가자!"]


def test_split_ignores_blank():
    assert split_ko("  ") == []


def test_accept_plain_sentence():
    assert accept_ko("서울은 대한민국의 수도이며, 가장 큰 도시이다.")
    assert accept_ko("그는 “좋은 아침입니다”라고 말하며 사람들에게 인사를 건넸다.")
    assert accept_ko("너는 오늘 저녁에 무엇을 먹고 싶니?")


def test_reject_digits_latin_brackets_hanja_jamo():
    assert not accept_ko("이 회사는 2001년에 설립되었으며 본사는 서울에 있다.")
    assert not accept_ko("그는 NASA에서 오랫동안 일한 뒤 한국으로 돌아왔다.")
    assert not accept_ko("한강(漢江)은 한반도 중부를 흐르는 큰 강이다.")
    assert not accept_ko("한강은 漢江이라고도 쓰며 한반도 중부를 흐른다.")
    assert not accept_ko("그 영상에는 ㅋㅋ 같은 댓글이 아주 많이 달려 있었다.")
    assert not accept_ko("즉, 는 스칼라장 의 기울기 벡터장이다.")    # formula removed by the dump
    assert not accept_ko("그는 서울, 부산; 대구를 차례로 방문하고 돌아왔다.")


def test_reject_length_and_ending():
    assert not accept_ko("안녕하세요.")
    assert not accept_ko("서울은 대한민국의 수도이며 가장 큰 도시이다")
    assert not accept_ko(" ".join(["아주"] * 31) + ".")
    assert not accept_ko("서울은 대한민국의 수도이며 가장 큰 도시이다...")
    assert not accept_ko("서울은 대한민국의 수도이며 가장 큰 도시이다 .")


def test_count_and_duration():
    assert syllable_count("안녕, 세상.") == 4
    assert ko_seconds("안녕, 세상.") == 4 / 5.5
