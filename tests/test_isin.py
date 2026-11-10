import pytest

from srp_dq.isin import isin_check_digit, is_valid_format, is_valid_isin


@pytest.mark.parametrize("isin", [
    "US0378331005",  # Apple
    "CH0012745979",  # SIX tracker certificate seen in the raw files
    "XS2550931773",
    "FR001401AYS9",
    "DE000BAY0017",  # Bayer
])
def test_real_isins_are_valid(isin):
    assert is_valid_isin(isin)


def test_check_digit_matches_known_value():
    assert isin_check_digit("US037833100") == 5


@pytest.mark.parametrize("isin", ["US0378331004", "CH0012745970"])
def test_wrong_check_digit_rejected(isin):
    assert is_valid_format(isin)
    assert not is_valid_isin(isin)


@pytest.mark.parametrize("isin", [None, "", "ISIN", "US037833100", "1S0378331005", "US037833100X",
                                  "us0378331005"])
def test_bad_format_rejected(isin):
    assert not is_valid_format(isin)
    assert not is_valid_isin(isin)
