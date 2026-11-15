import pytest

from vtts.frontend.normalize import normalize

CASES = [
    ("14/11/2026", "ngày mười bốn tháng mười một năm hai nghìn không trăm hai mươi sáu"),
    ("8:30", "tám giờ ba mươi phút"),
    ("8h", "tám giờ"),
    ("50%", "năm mươi phần trăm"),
    ("100.000đ", "một trăm nghìn đồng"),
    ("5 USD", "năm đô la"),
    ("5km", "năm ki lô mét"),
    ("25°C", "hai mươi lăm độ xê"),
    ("TP.HCM", "thành phố hồ chí minh"),
    ("ABC", "a bê xê"),
    ("wifi", "oai phai"),
    ("Xin chào, Việt Nam!", "xin chào , việt nam !"),
    ("ĐƯỜNG", "đường"),
    ("Bật đèn 😀 nhé", "bật đèn nhé"),
    ("Gửi tới a@b.com", "gửi tới a a còng bê chấm com"),
    ("Giá 3,5 triệu", "giá ba phẩy năm triệu"),
    ("Nhiệt độ -5 độ", "nhiệt độ âm năm độ"),
    ("“Xin chào” – bạn…", "xin chào , bạn ."),
    ("Q.1, P.Bến Nghé", "quận một , phường bến nghé"),
    ("Gọi 0912.345.678", "gọi không chín một hai ba bốn năm sáu bảy tám"),
    ("Tôi sinh ngày 2/9.", "tôi sinh ngày hai tháng chín ."),
    ("Điện thoại 0987 654 321.", "điện thoại không chín tám bảy sáu năm bốn ba hai một ."),
    ("2024-11-14", "ngày mười bốn tháng mười một năm hai nghìn không trăm hai mươi tư"),
]


@pytest.mark.parametrize("text,expected", CASES, ids=[c[0] for c in CASES])
def test_normalize(text, expected):
    assert normalize(text) == expected


def test_idempotent():
    once = normalize("Hôm nay, 14/11/2026, trời 25°C; bạn có khoẻ không?")
    assert normalize(once) == once


@pytest.mark.parametrize("text", ["10²", "2³ là tám", "x ² y", "①"])
def test_superscript_and_circled_digits_do_not_crash(text):
    out = normalize(text)
    assert "²" not in out and "①" not in out


def test_ngay_ngay_in_prose_is_kept():
    assert normalize("ngày ngày người thợ già") == "ngày ngày người thợ già"


def test_tone_placement_is_canonical():
    assert normalize("hoà bình") == normalize("hòa bình")
    assert normalize("thuỷ") == normalize("thủy")
    assert normalize("khoẻ") == normalize("khỏe")
