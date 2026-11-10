"""Day-over-day change detection and SCD Type 2 product history."""
from datetime import date

import pandas as pd

TRACKED_FIELDS = [
    "short_name", "valor_symbol", "valor_number", "product_type", "sec_type_code", "currency",
    "geo_area_code", "first_trading_date", "last_trading_date", "issuer_code",
]
AUDIT_COLUMNS = ["snapshot_date", "isin", "change_type", "field", "old_value", "new_value"]


def _as_text(s: pd.Series) -> pd.Series:
    return s.astype("string")


def diff_snapshots(prev: pd.DataFrame | None, curr: pd.DataFrame, snapshot_date: date,
                   ever_seen: set[str]) -> pd.DataFrame:
    """Compare two snapshots keyed on ISIN and return audit events."""
    curr = curr.set_index("isin")[TRACKED_FIELDS]
    if prev is None:
        events = pd.DataFrame({"isin": curr.index, "change_type": "INITIAL_LOAD"})
        events[["field", "old_value", "new_value"]] = None
        events.insert(0, "snapshot_date", snapshot_date)
        return events[AUDIT_COLUMNS]

    prev = prev.set_index("isin")[TRACKED_FIELDS]
    added = curr.index.difference(prev.index)
    removed = prev.index.difference(curr.index)
    common = curr.index.intersection(prev.index)

    frames = []
    if len(added):
        relisted = added.isin(list(ever_seen))
        frames.append(pd.DataFrame({
            "isin": added,
            "change_type": ["RELISTED" if r else "NEW_LISTING" for r in relisted],
        }))
    if len(removed):
        frames.append(pd.DataFrame({"isin": removed, "change_type": "REMOVED"}))

    p, c = prev.loc[common], curr.loc[common]
    for col in TRACKED_FIELDS:
        old, new = _as_text(p[col]), _as_text(c[col])
        changed = ~((old == new).fillna(False) | (old.isna() & new.isna()))
        if changed.any():
            frames.append(pd.DataFrame({
                "isin": common[changed.to_numpy()],
                "change_type": "FIELD_CHANGE",
                "field": col,
                "old_value": old[changed].to_numpy(),
                "new_value": new[changed].to_numpy(),
            }))

    if not frames:
        return pd.DataFrame(columns=AUDIT_COLUMNS)
    events = pd.concat(frames, ignore_index=True)
    events.insert(0, "snapshot_date", snapshot_date)
    return events.reindex(columns=AUDIT_COLUMNS)


class ProductHistory:
    """Maintains an SCD Type 2 table: one row per version of each product's reference data."""

    def __init__(self) -> None:
        self._closed: list[pd.DataFrame] = []
        self.current = pd.DataFrame(columns=["isin", *TRACKED_FIELDS, "valid_from"])

    def apply(self, curr: pd.DataFrame, events: pd.DataFrame, snapshot_date: date) -> None:
        touched = set(events.loc[events["change_type"] != "REMOVED", "isin"])
        ended = set(events.loc[events["change_type"].isin(["REMOVED", "FIELD_CHANGE"]), "isin"])

        if ended:
            closing = self.current[self.current["isin"].isin(ended)].copy()
            closing["valid_to"] = snapshot_date
            self._closed.append(closing)
            self.current = self.current[~self.current["isin"].isin(ended)]

        if touched:
            new_versions = curr.loc[curr["isin"].isin(touched), ["isin", *TRACKED_FIELDS]].copy()
            new_versions["valid_from"] = snapshot_date
            self.current = pd.concat([self.current, new_versions], ignore_index=True)

    def table(self) -> pd.DataFrame:
        cur = self.current.copy()
        cur["valid_to"] = pd.NaT
        out = pd.concat([*self._closed, cur], ignore_index=True)
        out["is_current"] = out["valid_to"].isna()
        out["version"] = out.sort_values("valid_from").groupby("isin").cumcount() + 1
        return out.sort_values(["isin", "version"]).reset_index(drop=True)
