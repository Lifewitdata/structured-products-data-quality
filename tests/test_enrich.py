import pytest

from srp_dq.enrich import parse_issuer_code


@pytest.mark.parametrize("short_name, symbol, expected", [
    ("SPWIN UBS C", "SPWIN", "UBS"),
    ("DISPVZ ZKB P 01/27", "DISPVZ", "ZKB"),
    ("7.85 ZKB/Z0CDLZ 27", "Z0CDLZ", "ZKB"),
    ("1.25 VON/ 27", "YCORCV", "VON"),
    ("2.39 YCHACV VON 27", "YCHACV", "VON"),
    ("7.70 RAIFFNL/SYORCH 28 /Z", "SYORCH", "RAIFFNL"),
    ("AA3VSP RBC C 09/31 /Z", "AA3VSP", "RBC"),
    ("MLOA4V VON P01", "MLOA4V", "VON"),
])
def test_issuer_code_from_all_short_name_layouts(short_name, symbol, expected):
    assert parse_issuer_code(short_name, symbol) == expected


def test_missing_short_name():
    assert parse_issuer_code(None, "X") is None
