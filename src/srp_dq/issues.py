"""Turn daily QC failures into an issue log with open/resolved lifecycle."""
import pandas as pd


def build_issue_log(qc: pd.DataFrame, snapshot_dates: list, presence: pd.DataFrame,
                    rules: pd.DataFrame) -> pd.DataFrame:
    """Group consecutive daily failures of the same rule on the same ISIN into one issue.

    presence: DataFrame with columns snapshot_date, isin for every product in every snapshot.
    """
    dates = sorted(snapshot_dates)
    idx = {d: i for i, d in enumerate(dates)}
    latest = dates[-1]

    q = qc[["snapshot_date", "isin", "rule_id"]].copy()
    q["day_idx"] = q["snapshot_date"].map(idx)
    q = q.sort_values(["rule_id", "isin", "day_idx"])
    gap = q.groupby(["rule_id", "isin"])["day_idx"].diff().fillna(1) != 1
    q["episode"] = gap.groupby([q["rule_id"], q["isin"]]).cumsum()

    issues = (q.groupby(["rule_id", "isin", "episode"])
                .agg(first_seen=("snapshot_date", "min"), last_seen=("snapshot_date", "max"),
                     last_idx=("day_idx", "max"), days_failing=("day_idx", "size"))
                .reset_index())

    issues["status"] = issues["last_seen"].map(lambda d: "OPEN" if d == latest else "RESOLVED")
    next_idx = issues["last_idx"] + 1
    issues["resolved_on"] = [dates[i] if s == "RESOLVED" else None
                             for i, s in zip(next_idx.clip(upper=len(dates) - 1), issues["status"])]

    present = set(zip(presence["snapshot_date"], presence["isin"]))
    issues["resolution"] = [
        None if st == "OPEN"
        else "NO_LONGER_FAILING" if (res, isin) in present
        else "ABSENT_FROM_SNAPSHOT"
        for st, res, isin in zip(issues["status"], issues["resolved_on"], issues["isin"])
    ]
    issues["days_to_resolve"] = [
        (pd.Timestamp(r) - pd.Timestamp(f)).days if r is not None else None
        for f, r in zip(issues["first_seen"], issues["resolved_on"])
    ]
    issues = issues.merge(rules[["rule_id", "rule_name", "severity", "category", "action"]],
                          on="rule_id", how="left")
    issues["issue_id"] = (issues["rule_id"] + "-" + issues["isin"] + "-"
                          + issues["episode"].astype(int).astype(str))
    cols = ["issue_id", "rule_id", "rule_name", "severity", "category", "isin", "first_seen",
            "last_seen", "days_failing", "status", "resolved_on", "resolution",
            "days_to_resolve", "action"]
    return issues[cols].sort_values(["status", "severity", "first_seen"]).reset_index(drop=True)
