from datetime import date

import pandas as pd

from srp_dq.audit import TRACKED_FIELDS, ProductHistory, diff_snapshots

D1, D2, D3 = date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)


def snap(records: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for isin, overrides in records.items():
        base = {f: None for f in TRACKED_FIELDS}
        base.update({"short_name": f"{isin} VON C", "currency": "CHF", "issuer_code": "VON"})
        base.update(overrides)
        rows.append({"isin": isin, **base})
    return pd.DataFrame(rows, columns=["isin", *TRACKED_FIELDS])


def test_initial_load_creates_one_event_per_product():
    ev = diff_snapshots(None, snap({"A": {}, "B": {}}), D1, set())
    assert list(ev["change_type"]) == ["INITIAL_LOAD", "INITIAL_LOAD"]


def test_detects_new_removed_and_field_changes():
    prev = snap({"A": {}, "B": {}, "C": {"last_trading_date": None}})
    curr = snap({"A": {"currency": "EUR"}, "C": {"last_trading_date": date(2026, 11, 4)}, "D": {}})
    ev = diff_snapshots(prev, curr, D2, {"A", "B", "C"})

    kinds = {(r.isin, r.change_type, r.field) for r in ev.itertuples()}
    assert ("D", "NEW_LISTING", None) in {(i, c, f if pd.notna(f) else None) for i, c, f in kinds}
    assert ("B", "REMOVED") in {(i, c) for i, c, _ in kinds}
    a = ev[(ev["isin"] == "A")].iloc[0]
    assert (a["field"], a["old_value"], a["new_value"]) == ("currency", "CHF", "EUR")
    c = ev[(ev["isin"] == "C")].iloc[0]
    assert pd.isna(c["old_value"]) and c["new_value"] == "2026-11-04"


def test_unchanged_nulls_are_not_changes():
    prev = snap({"A": {"product_type": None}})
    ev = diff_snapshots(prev, snap({"A": {"product_type": None}}), D2, {"A"})
    assert ev.empty


def test_relisting_is_distinguished_from_new_listing():
    ev = diff_snapshots(snap({}), snap({"A": {}}), D3, ever_seen={"A"})
    assert list(ev["change_type"]) == ["RELISTED"]


def test_scd2_versions_and_validity_windows():
    hist = ProductHistory()
    s1 = snap({"A": {}, "B": {}})
    hist.apply(s1, diff_snapshots(None, s1, D1, set()), D1)
    s2 = snap({"A": {"currency": "EUR"}})
    hist.apply(s2, diff_snapshots(s1, s2, D2, {"A", "B"}), D2)

    t = hist.table()
    a = t[t["isin"] == "A"].sort_values("version")
    assert list(a["version"]) == [1, 2]
    assert list(a["currency"]) == ["CHF", "EUR"]
    assert a.iloc[0]["valid_to"] == D2 and not a.iloc[0]["is_current"]
    assert pd.isna(a.iloc[1]["valid_to"]) and a.iloc[1]["is_current"]

    b = t[t["isin"] == "B"]
    assert len(b) == 1 and b.iloc[0]["valid_to"] == D2 and not b.iloc[0]["is_current"]
