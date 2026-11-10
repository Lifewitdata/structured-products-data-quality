"""Parse a SIX daily structured-products CSV into a typed DataFrame plus load metadata."""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

SOURCE_COLUMNS = [
    "ShortName", "ISIN", "ValorSymbol", "ValorNumber", "ClosingPrice", "DailyHighPrice",
    "DailyLowPrice", "LatestTradeDate", "PreviousClosingPrice", "OpeningPrice", "OnMarketVolume",
    "TotalVolume", "TradingBaseCurrency", "YearlyHighDate", "YearlyHighPrice", "YearlyLowDate",
    "YearlyLowPrice", "FirstTradingDate", "LastTradingDate", "Exchange", "SecTypeCode",
    "GeographicalAreaCode", "Tminus1Volume", "TotalTrades", "TotalTurnover",
    "DerivativeSecTypeCodeDesc",
]
RENAME = {
    "ShortName": "short_name", "ISIN": "isin", "ValorSymbol": "valor_symbol",
    "ValorNumber": "valor_number", "ClosingPrice": "closing_price",
    "DailyHighPrice": "daily_high", "DailyLowPrice": "daily_low",
    "LatestTradeDate": "latest_trade_date", "PreviousClosingPrice": "previous_close",
    "OpeningPrice": "opening_price", "OnMarketVolume": "on_market_volume",
    "TotalVolume": "total_volume", "TradingBaseCurrency": "currency",
    "YearlyHighDate": "yearly_high_date", "YearlyHighPrice": "yearly_high",
    "YearlyLowDate": "yearly_low_date", "YearlyLowPrice": "yearly_low",
    "FirstTradingDate": "first_trading_date", "LastTradingDate": "last_trading_date",
    "Exchange": "exchange", "SecTypeCode": "sec_type_code",
    "GeographicalAreaCode": "geo_area_code", "Tminus1Volume": "t_minus_1_volume",
    "TotalTrades": "total_trades", "TotalTurnover": "total_turnover",
    "DerivativeSecTypeCodeDesc": "product_type",
}
NUMERIC = [
    "closing_price", "daily_high", "daily_low", "previous_close", "opening_price",
    "on_market_volume", "total_volume", "yearly_high", "yearly_low", "t_minus_1_volume",
    "total_trades", "total_turnover",
]
DATES = [
    "latest_trade_date", "yearly_high_date", "yearly_low_date",
    "first_trading_date", "last_trading_date",
]
FILE_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
FOOTER_RE = re.compile(r"^Produced at:\s*(\d{2}:\d{2}:\d{2})\s+(\d{4}-\d{2}-\d{2})")


@dataclass
class LoadResult:
    data: pd.DataFrame
    snapshot_date: date
    file_name: str
    produced_at: datetime | None
    raw_lines: int
    header_lines: int
    bad_lines: list[str] = field(default_factory=list)
    unparseable_values: int = 0


def _parse_dates(s: pd.Series) -> tuple[pd.Series, int]:
    parsed = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
    return parsed.dt.date, int((parsed.isna() & s.notna()).sum())


def _parse_numbers(s: pd.Series) -> tuple[pd.Series, int]:
    parsed = pd.to_numeric(s, errors="coerce")
    return parsed, int((parsed.isna() & s.notna()).sum())


def parse_text(text: str, file_name: str) -> LoadResult:
    m = FILE_DATE_RE.search(file_name)
    snapshot_date = date.fromisoformat(m.group(1)) if m else None
    produced_at = None
    header_lines = 0
    bad_lines: list[str] = []
    rows: list[list[str]] = []
    lines = text.splitlines()

    for line in lines:
        if not line.strip():
            continue
        if line.startswith("ShortName;"):
            header = [f.strip() for f in next(csv.reader([line], delimiter=";"))]
            if header[:25] != SOURCE_COLUMNS[:25] or header[25:] not in [[SOURCE_COLUMNS[25]], [""]]:
                raise ValueError(f"Unexpected header schema in {file_name}")
            header_lines += 1
            continue
        footer = FOOTER_RE.match(line)
        if footer:
            produced_at = datetime.fromisoformat(f"{footer.group(2)}T{footer.group(1)}")
            continue
        fields = [f.strip() for f in next(csv.reader(io.StringIO(line), delimiter=";"))]
        if len(fields) != len(SOURCE_COLUMNS):
            bad_lines.append(line)
            continue
        rows.append(fields)

    df = pd.DataFrame(rows, columns=SOURCE_COLUMNS).rename(columns=RENAME)
    df = df.replace("", pd.NA)
    unparseable = 0
    for col in NUMERIC:
        df[col], n = _parse_numbers(df[col])
        unparseable += n
    for col in DATES:
        df[col], n = _parse_dates(df[col])
        unparseable += n
    df.insert(0, "snapshot_date", snapshot_date)

    return LoadResult(
        data=df,
        snapshot_date=snapshot_date,
        file_name=file_name,
        produced_at=produced_at,
        raw_lines=len(lines),
        header_lines=header_lines,
        bad_lines=bad_lines,
        unparseable_values=unparseable,
    )


def load_file(path: Path) -> LoadResult:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return parse_text(text, path.name)
