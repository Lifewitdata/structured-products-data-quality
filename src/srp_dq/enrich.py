"""Derive issuer and EUSIPA classification from SIX fields using maintained reference tables."""
import re
from pathlib import Path

import pandas as pd

REF_DIR = Path(__file__).resolve().parents[2] / "reference"
_NUMERIC = re.compile(r"^\d+(\.\d+)?$")
_MARKERS = {"C", "P", "Z"}


def parse_issuer_code(short_name: str | None, valor_symbol: str | None) -> str | None:
    if not isinstance(short_name, str):
        return None
    for tok in re.split(r"[\s/]+", short_name):
        if not tok or _NUMERIC.match(tok) or tok in _MARKERS or tok == valor_symbol:
            continue
        return tok
    return None


def load_reference(ref_dir: Path = REF_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    issuers = pd.read_csv(ref_dir / "issuers.csv", dtype={"issuer_code": str})
    issuers["verified"] = issuers["verified"].astype(str).str.lower() == "true"
    types = pd.read_csv(ref_dir / "product_types.csv", dtype={"eusipa_code": "Int64"})
    return issuers, types


def enrich(df: pd.DataFrame, issuers: pd.DataFrame, types: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["issuer_code"] = [
        parse_issuer_code(s, v) for s, v in zip(out["short_name"], out["valor_symbol"])
    ]
    out = out.merge(issuers, on="issuer_code", how="left", validate="many_to_one")
    out = out.merge(types, on="product_type", how="left", validate="many_to_one")
    out["isin_country"] = out["isin"].str[:2]
    return out
