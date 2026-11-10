"""Data quality rules. Each product rule returns a boolean mask where True means the row fails."""
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

import pandas as pd
import pycountry

from srp_dq.isin import is_valid_format, is_valid_isin

ISO_CURRENCIES = {c.alpha_3 for c in pycountry.currencies}
SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    severity: str
    category: str
    description: str
    action: str
    check: Callable[[pd.DataFrame], pd.Series]


def _snap(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["snapshot_date"])


def _dt(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_datetime(df[col])


PRODUCT_RULES: list[Rule] = [
    Rule("R01", "ISIN_FORMAT", "CRITICAL", "Identifier",
         "ISIN is not 2 letters + 9 alphanumerics + 1 digit",
         "Reject row; request corrected identifier from exchange",
         lambda d: ~d["isin"].map(is_valid_format)),
    Rule("R02", "ISIN_CHECK_DIGIT", "CRITICAL", "Identifier",
         "ISIN check digit fails ISO 6166 Luhn validation",
         "Reject row; confirm ISIN against issuer term sheet",
         lambda d: d["isin"].map(is_valid_format) & ~d["isin"].map(is_valid_isin)),
    Rule("R03", "DUPLICATE_ISIN", "CRITICAL", "Identifier",
         "Same ISIN appears more than once in one snapshot",
         "Keep the latest record; raise duplicate with exchange",
         lambda d: d["isin"].duplicated(keep=False)),
    Rule("R04", "DUPLICATE_VALOR", "HIGH", "Identifier",
         "Same Valor number mapped to more than one ISIN",
         "Check Valor-ISIN mapping in SIX product search",
         lambda d: d["valor_number"].notna() & d["valor_number"].duplicated(keep=False)),
    Rule("R05", "MISSING_PRODUCT_TYPE", "HIGH", "Classification",
         "Product type (DerivativeSecTypeCodeDesc) is blank",
         "Classify from term sheet / SIX product page; escalate if source gap persists",
         lambda d: d["product_type"].isna()),
    Rule("R06", "UNMAPPED_PRODUCT_TYPE", "MEDIUM", "Classification",
         "Product type not found in EUSIPA reference table",
         "Add the new type to reference/product_types.csv with EUSIPA code",
         lambda d: d["product_type"].notna() & d["eusipa_code"].isna()),
    Rule("R07", "UNKNOWN_ISSUER", "MEDIUM", "Reference data",
         "Issuer code parsed from ShortName is not in the issuer reference table",
         "Identify issuer from term sheet and add to reference/issuers.csv",
         lambda d: d["issuer_code"].isna() | d["verified"].isna()),
    Rule("R08", "UNVERIFIED_ISSUER", "LOW", "Reference data",
         "Issuer code is known but its legal name is not yet verified",
         "Confirm legal entity name from final terms and set verified=true",
         lambda d: d["verified"].eq(False)),
    Rule("R09", "INVALID_CURRENCY", "HIGH", "Reference data",
         "Trading currency is not an ISO 4217 code",
         "Correct currency from term sheet",
         lambda d: ~d["currency"].isin(ISO_CURRENCIES)),
    Rule("R10", "NON_ISO_GEO_AREA", "LOW", "Reference data",
         "Source uses a numeric regional code; this is informational, not invalid geography",
         "Preserve the source code; obtain SIX codebook before interpreting geography",
         lambda d: d["geo_area_code"].fillna("").str.fullmatch(r"\d+")),
    Rule("R11", "MATURITY_BEFORE_LISTING", "HIGH", "Dates",
         "Last trading date is earlier than first trading date",
         "Correct dates from final terms",
         lambda d: _dt(d, "last_trading_date") < _dt(d, "first_trading_date")),
    Rule("R12", "EXPIRED_STILL_LISTED", "HIGH", "Lifecycle",
         "Last trading date has passed but product is still in the file",
         "Confirm delisting / early redemption with exchange notice",
         lambda d: _dt(d, "last_trading_date") < _snap(d)),
    Rule("R13", "LATEST_TRADE_IN_FUTURE", "HIGH", "Dates",
         "Latest trade date is after the snapshot date",
         "Investigate timestamp error at source",
         lambda d: _dt(d, "latest_trade_date") > _snap(d)),
    Rule("R14", "MISSING_CLOSING_PRICE", "HIGH", "Pricing",
         "Closing price is blank",
         "Re-request price; carry forward previous close only with a flag",
         lambda d: d["closing_price"].isna()),
    Rule("R15", "NON_POSITIVE_PRICE", "MEDIUM", "Pricing",
         "Closing price is zero or negative",
         "Check for knock-out / redemption event; otherwise request correction",
         lambda d: d["closing_price"] <= 0),
    Rule("R16", "DAILY_HIGH_BELOW_LOW", "HIGH", "Pricing",
         "Daily high price is below daily low price",
         "Request corrected OHLC from exchange",
         lambda d: d["daily_high"] < d["daily_low"]),
    Rule("R17", "VOLUME_WITHOUT_TRADES", "MEDIUM", "Pricing",
         "On-market volume is positive but trade count is zero",
         "Reconcile volume and trade count with exchange",
         lambda d: (d["on_market_volume"] > 0) & (d["total_trades"] == 0)),
    Rule("R18", "STALE_LAST_TRADE", "LOW", "Pricing",
         "Product has not traded on-exchange for more than 365 days",
         "Review trading inactivity; do not infer stale quoted prices or delisting",
         lambda d: _dt(d, "latest_trade_date") < _snap(d) - timedelta(days=365)),
]
RULES_BY_ID = {r.rule_id: r for r in PRODUCT_RULES}


def run_product_rules(df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for rule in PRODUCT_RULES:
        mask = rule.check(df).fillna(False).astype(bool)
        if mask.any():
            hit = df.loc[mask, ["snapshot_date", "isin"]].copy()
            hit["rule_id"] = rule.rule_id
            frames.append(hit)
    if not frames:
        return pd.DataFrame(columns=["snapshot_date", "isin", "rule_id"])
    return pd.concat(frames, ignore_index=True)


def rules_table() -> pd.DataFrame:
    return pd.DataFrame(
        [(r.rule_id, r.name, r.severity, r.category, r.description, r.action) for r in PRODUCT_RULES],
        columns=["rule_id", "rule_name", "severity", "category", "description", "action"],
    )


def run_snapshot_checks(snapshots: pd.DataFrame, missing_type_counts: pd.Series,
                        row_change_pct: float = 1.5, spike_factor: float = 3.0,
                        time_tolerance_min: int = 60) -> pd.DataFrame:
    """File-level checks: row-count swings, missing-value spikes, unusual production time."""
    s = snapshots.sort_values("snapshot_date").reset_index(drop=True).copy()
    s["prev_rows"] = s["row_count"].shift()
    s["row_change_pct"] = (s["row_count"] / s["prev_rows"] - 1) * 100
    s["missing_type"] = s["snapshot_date"].map(missing_type_counts).fillna(0).astype(int)
    baseline_missing = s["missing_type"].median()
    minutes = pd.to_datetime(s["produced_at"]).dt.hour * 60 + pd.to_datetime(s["produced_at"]).dt.minute
    s["produced_minutes_from_median"] = minutes - minutes.median()

    findings = []
    for _, r in s.iterrows():
        if pd.notna(r["row_change_pct"]) and abs(r["row_change_pct"]) > row_change_pct:
            findings.append((r["snapshot_date"], "S01", "ROW_COUNT_SWING", "MEDIUM",
                             f"Row count changed {r['row_change_pct']:+.2f}% vs previous file"))
        if baseline_missing and r["missing_type"] > spike_factor * baseline_missing:
            findings.append((r["snapshot_date"], "S02", "MISSING_TYPE_SPIKE", "HIGH",
                             f"{r['missing_type']} products without type vs median {baseline_missing:.0f}"))
        if abs(r["produced_minutes_from_median"]) > time_tolerance_min:
            findings.append((r["snapshot_date"], "S03", "PRODUCTION_TIME_DEVIATION", "MEDIUM",
                             f"File produced at {pd.Timestamp(r['produced_at']):%H:%M}, "
                             f"{r['produced_minutes_from_median']:+.0f} min from usual time"))
    return pd.DataFrame(findings, columns=["snapshot_date", "check_id", "check_name", "severity", "detail"])
