from datetime import date, datetime

import pandas as pd

from helpers import HEADER, make_isin, row, six_file
from srp_dq.load import parse_text


def test_parses_types_headers_and_footer():
    text = six_file([
        row(ISIN=make_isin("CH000000001")),
        HEADER.rsplit(";", 1)[0] + ";",  # second block header, missing last column name
        row(ISIN=make_isin("CH000000002"), ClosingPrice="", LastTradingDate=""),
    ])
    res = parse_text(text, "derivatives_2026-11-10.csv")

    assert res.snapshot_date == date(2026, 11, 10)
    assert res.produced_at == datetime(2026, 11, 10, 23, 45, 5)
    assert res.header_lines == 2
    assert res.bad_lines == []
    assert len(res.data) == 2

    first = res.data.iloc[0]
    assert first["closing_price"] == 1.5
    assert first["first_trading_date"] == date(2026, 1, 1)
    assert first["product_type"] == "Warrant"
    second = res.data.iloc[1]
    assert pd.isna(second["closing_price"])
    assert pd.isna(second["last_trading_date"])


def test_wrong_field_count_is_reported_not_loaded():
    text = six_file([row(ISIN=make_isin("CH000000001")), "BROKEN; ROW; ONLY"])
    res = parse_text(text, "derivatives_2026-11-10.csv")
    assert len(res.data) == 1
    assert res.bad_lines == ["BROKEN; ROW; ONLY"]


def test_unparseable_values_are_counted():
    text = six_file([row(ISIN=make_isin("CH000000001"), ClosingPrice="n/a", FirstTradingDate="2026-01-01")])
    res = parse_text(text, "derivatives_2026-11-10.csv")
    assert res.unparseable_values == 2
