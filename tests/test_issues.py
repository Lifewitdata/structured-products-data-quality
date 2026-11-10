from datetime import date

import pandas as pd

from srp_dq.issues import build_issue_log
from srp_dq.rules import rules_table

DAYS = [date(2026, 11, d) for d in (2, 3, 4, 5)]


def qc(rows):
    return pd.DataFrame(rows, columns=["snapshot_date", "isin", "rule_id"])


def presence(mapping):
    return pd.DataFrame([(d, i) for d, isins in mapping.items() for i in isins],
                        columns=["snapshot_date", "isin"])


def test_issue_lifecycle_open_resolved_and_removed():
    failures = qc([
        (DAYS[0], "FIXED", "R05"),                       # fixed next day
        (DAYS[0], "GONE", "R05"), (DAYS[1], "GONE", "R05"),  # product delisted on day 3
        (DAYS[2], "STILL", "R05"), (DAYS[3], "STILL", "R05"),  # open at latest snapshot
        (DAYS[0], "FLAP", "R05"), (DAYS[2], "FLAP", "R05"),    # two separate episodes
    ])
    seen = presence({
        DAYS[0]: ["FIXED", "GONE", "STILL", "FLAP"],
        DAYS[1]: ["FIXED", "GONE", "STILL", "FLAP"],
        DAYS[2]: ["FIXED", "STILL", "FLAP"],
        DAYS[3]: ["FIXED", "STILL", "FLAP"],
    })
    log = build_issue_log(failures, DAYS, seen, rules_table()).set_index("issue_id")

    fixed = log.loc["R05-FIXED-0"]
    assert (fixed["status"], fixed["resolution"], fixed["days_to_resolve"]) == \
        ("RESOLVED", "NO_LONGER_FAILING", 1)

    gone = log.loc["R05-GONE-0"]
    assert (gone["status"], gone["resolution"], gone["days_failing"]) == ("RESOLVED", "ABSENT_FROM_SNAPSHOT", 2)

    still = log.loc["R05-STILL-0"]
    assert still["status"] == "OPEN" and pd.isna(still["resolution"])

    assert {"R05-FLAP-0", "R05-FLAP-1"} <= set(log.index)
    assert log.loc["R05-FLAP-1", "status"] == "RESOLVED"
    assert log.loc["R05-FLAP-0", "severity"] == "HIGH"
