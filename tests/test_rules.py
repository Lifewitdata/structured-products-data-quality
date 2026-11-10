import pandas as pd
import pytest

from helpers import make_isin, row, six_file
from srp_dq.enrich import enrich, load_reference
from srp_dq.load import parse_text
from srp_dq.rules import PRODUCT_RULES, run_product_rules, run_snapshot_checks, rules_table

CLEAN = make_isin("CH000000001")
CASES = {
    "R01": dict(ISIN="CH00000000XX"),
    "R02": dict(ISIN=CLEAN[:-1] + str((int(CLEAN[-1]) + 1) % 10)),
    "R05": dict(DerivativeSecTypeCodeDesc=""),
    "R06": dict(DerivativeSecTypeCodeDesc="Brand New Certificate"),
    "R07": dict(ShortName="ABCDEV NOBODY C 12/27"),
    "R08": dict(ShortName="ABCDEV BKSVR C 12/27"),
    "R09": dict(TradingBaseCurrency="FRF"),
    "R10": dict(GeographicalAreaCode="10"),
    "R11": dict(FirstTradingDate="20270101", LastTradingDate="20261201"),
    "R12": dict(LastTradingDate="20261101"),
    "R13": dict(LatestTradeDate="20261201"),
    "R14": dict(ClosingPrice=""),
    "R15": dict(ClosingPrice="0"),
    "R16": dict(DailyHighPrice="1.0", DailyLowPrice="2.0"),
    "R17": dict(OnMarketVolume="500", TotalTrades="0"),
    "R18": dict(LatestTradeDate="20250101"),
}


def build(rows):
    issuers, types = load_reference()
    issuers.loc[issuers["issuer_code"] == "VON", "verified"] = True
    res = parse_text(six_file(rows), "derivatives_2026-11-10.csv")
    return enrich(res.data, issuers, types)


@pytest.fixture(scope="module")
def results():
    rows = [row(ISIN=CLEAN)]
    isins = {}
    for i, (rule_id, overrides) in enumerate(CASES.items(), start=2):
        isin = overrides.get("ISIN") or make_isin(f"CH{i:09d}")
        isins[rule_id] = isin
        rows.append(row(**{**overrides, "ISIN": isin, "ValorNumber": str(1000 + i)}))
    return run_product_rules(build(rows)), isins


def test_clean_row_passes_every_rule(results):
    qc, _ = results
    assert CLEAN not in set(qc["isin"])


@pytest.mark.parametrize("rule_id", sorted(CASES))
def test_each_rule_catches_its_bad_row(results, rule_id):
    qc, isins = results
    hits = set(qc.loc[qc["rule_id"] == rule_id, "isin"])
    assert isins[rule_id] in hits


def test_duplicates_flagged():
    dup = make_isin("CH000000009")
    qc = run_product_rules(build([
        row(ISIN=dup, ValorNumber="1"),
        row(ISIN=dup, ValorNumber="2"),
        row(ISIN=make_isin("CH000000008"), ValorNumber="2"),
    ]))
    assert (qc["rule_id"] == "R03").sum() == 2
    assert set(qc.loc[qc["rule_id"] == "R04", "isin"]) == {dup, make_isin("CH000000008")}


def test_rules_table_is_complete_and_unique():
    t = rules_table()
    assert len(t) == len(PRODUCT_RULES)
    assert t["rule_id"].is_unique
    assert set(t["severity"]) <= {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def test_snapshot_checks_detect_swing_spike_and_late_file():
    days = pd.to_datetime(["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]).date
    snaps = pd.DataFrame({
        "snapshot_date": days,
        "row_count": [100_000, 100_100, 96_000, 96_050],
        "produced_at": pd.to_datetime(["2026-11-02 23:45", "2026-11-03 23:45",
                                       "2026-11-04 23:45", "2026-11-05 18:45"]),
    })
    missing = pd.Series([180, 182, 2_000, 181], index=days)
    found = run_snapshot_checks(snaps, missing)
    by_day = found.groupby("snapshot_date")["check_id"].apply(set).to_dict()
    assert by_day[days[2]] == {"S01", "S02"}
    assert by_day[days[3]] == {"S03"}
    assert days[1] not in by_day
