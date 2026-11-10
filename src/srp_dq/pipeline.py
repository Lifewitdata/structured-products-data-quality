"""End-to-end build: raw SIX files -> enriched, validated, audited DuckDB database."""
import argparse
import os
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

from srp_dq.audit import TRACKED_FIELDS, ProductHistory, diff_snapshots
from srp_dq.enrich import enrich, load_reference
from srp_dq.issues import build_issue_log
from srp_dq.load import load_file
from srp_dq.rules import rules_table, run_product_rules, run_snapshot_checks

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "srp_quality.duckdb"
SQL_DIR = ROOT / "sql"
MARKET_COLS = ["snapshot_date", "isin", "closing_price", "previous_close", "daily_high", "daily_low",
               "latest_trade_date", "on_market_volume", "total_trades", "total_turnover"]


def process(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    files = sorted(raw_dir.glob("derivatives_*.csv"))
    if not files:
        raise FileNotFoundError(f"No SIX files in {raw_dir}; run `python -m srp_dq.download` first")
    issuers, types = load_reference()
    history = ProductHistory()
    ever_seen: set[str] = set()
    prev = None
    snapshots, market, qc, audit, missing_type = [], [], [], [], {}

    for path in files:
        res = load_file(path)
        day = res.snapshot_date
        if (day is None or res.produced_at is None or res.produced_at.date() != day
                or res.header_lines == 0 or res.data.empty
                or res.bad_lines or res.unparseable_values):
            raise ValueError(f"Rejected incomplete or malformed snapshot: {path.name}")
        if res.data["isin"].isna().any() or res.data["isin"].duplicated().any():
            raise ValueError(f"Rejected ambiguous ISIN keys: {path.name}")
        if snapshots and day <= snapshots[-1]["snapshot_date"]:
            raise ValueError(f"Snapshots must have unique increasing dates: {path.name}")
        df = enrich(res.data, issuers, types)
        snapshots.append({
            "snapshot_date": day, "file_name": res.file_name, "produced_at": res.produced_at,
            "raw_lines": res.raw_lines, "header_lines": res.header_lines,
            "bad_lines": len(res.bad_lines), "unparseable_values": res.unparseable_values,
            "row_count": len(df),
        })
        market.append(df[MARKET_COLS])
        qc.append(run_product_rules(df))
        missing_type[day] = int(df["product_type"].isna().sum())

        ref = df[["isin", *TRACKED_FIELDS]]
        events = diff_snapshots(prev, ref, day, ever_seen)
        history.apply(ref, events, day)
        audit.append(events)
        ever_seen |= set(ref["isin"])
        prev = ref
        print(f"{day}: {len(df):>7,} rows, {len(events):>7,} audit events")

    snapshots_df = pd.DataFrame(snapshots)
    market_df = pd.concat(market, ignore_index=True)
    qc_df = pd.concat(qc, ignore_index=True).drop_duplicates()
    audit_df = pd.concat(audit, ignore_index=True)
    audit_df.insert(0, "audit_id", range(1, len(audit_df) + 1))
    history_df = history.table()
    rules_df = rules_table()

    dates = snapshots_df["snapshot_date"].tolist()
    presence = market_df[["snapshot_date", "isin"]]
    seen = presence.groupby("isin")["snapshot_date"].agg(first_seen="min", last_seen="max")
    products = (history_df.sort_values("version").groupby("isin").tail(1)
                .drop(columns=["valid_from", "valid_to", "is_current", "version"])
                .join(seen, on="isin"))
    products["is_listed"] = products["last_seen"] == max(dates)

    return {
        "snapshots": snapshots_df,
        "issuers": issuers,
        "product_types": types,
        "qc_rules": rules_df,
        "products": products,
        "product_history": history_df,
        "daily_market": market_df,
        "audit_log": audit_df,
        "qc_results": qc_df,
        "snapshot_checks": run_snapshot_checks(snapshots_df, pd.Series(missing_type)),
        "issue_log": build_issue_log(qc_df, dates, presence, rules_df),
    }


def write_db(tables: dict[str, pd.DataFrame], db_path: Path = DB_PATH) -> None:
    fd, name = tempfile.mkstemp(prefix="srp-build-", suffix=".duckdb", dir=db_path.parent)
    os.close(fd)
    staging = Path(name)
    staging.unlink()
    try:
        with duckdb.connect(str(staging)) as con:
            con.execute("BEGIN TRANSACTION")
            con.execute((SQL_DIR / "schema.sql").read_text())
            for name, df in tables.items():
                cols = [r[0] for r in con.execute(f"DESCRIBE {name}").fetchall()]
                con.register("df_view", df[cols])
                con.execute(f"INSERT INTO {name} SELECT * FROM df_view")
                con.unregister("df_view")
            con.execute((SQL_DIR / "views.sql").read_text())
            con.execute("COMMIT")
        os.replace(staging, db_path)
    finally:
        staging.unlink(missing_ok=True)
        Path(str(staging) + ".wal").unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    tables = process(args.raw_dir)
    write_db(tables, args.db)
    for name, df in tables.items():
        print(f"  {name:<16} {len(df):>10,} rows")
    print(f"Database written to {args.db}")


if __name__ == "__main__":
    main()
