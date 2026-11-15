import pytest

from vtts.frontend.numbers import read_int, read_number_token

CASES = [(0, "không"), (10, "mười"), (15, "mười lăm"), (21, "hai mươi mốt"),
         (24, "hai mươi tư"), (25, "hai mươi lăm"), (105, "một trăm linh năm"),
         (1005, "một nghìn không trăm linh năm"), (1050, "một nghìn không trăm năm mươi"),
         (1500, "một nghìn năm trăm"), (1000500, "một triệu năm trăm"),
         (2026, "hai nghìn không trăm hai mươi sáu"), (1000000000, "một tỷ"),
         (11, "mười một"), (14, "mười bốn"), (101, "một trăm linh một"),
         (111, "một trăm mười một"), (2000000000000, "hai nghìn tỷ")]
TOKENS = [("1.000.000", "một triệu"), ("3,5", "ba phẩy năm"), ("-5", "âm năm"),
          ("1.5", "một chấm năm"), ("007", "không không bảy")]


@pytest.mark.parametrize("n,expected", CASES)
def test_read_int(n, expected):
    assert read_int(n) == expected


@pytest.mark.parametrize("tok,expected", TOKENS)
def test_read_number_token(tok, expected):
    assert read_number_token(tok) == expected


def test_huge_numbers_digit_by_digit():
    words = read_int(10**15).split()
    assert words == ["một"] + ["không"] * 15
