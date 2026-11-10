from srp_dq.isin import isin_check_digit, is_valid_format, is_valid_isin


def make_isin(body: str) -> str:
    return body + str(isin_check_digit(body))


HEADER = ("ShortName; ISIN; ValorSymbol; ValorNumber; ClosingPrice; DailyHighPrice; DailyLowPrice; "
          "LatestTradeDate; PreviousClosingPrice; OpeningPrice; OnMarketVolume; TotalVolume; "
          "TradingBaseCurrency; YearlyHighDate; YearlyHighPrice; YearlyLowDate; YearlyLowPrice; "
          "FirstTradingDate; LastTradingDate; Exchange; SecTypeCode; GeographicalAreaCode; "
          "Tminus1Volume; TotalTrades; TotalTurnover;DerivativeSecTypeCodeDesc")
FIELDS = ["ShortName", "ISIN", "ValorSymbol", "ValorNumber", "ClosingPrice", "DailyHighPrice",
          "DailyLowPrice", "LatestTradeDate", "PreviousClosingPrice", "OpeningPrice",
          "OnMarketVolume", "TotalVolume", "TradingBaseCurrency", "YearlyHighDate",
          "YearlyHighPrice", "YearlyLowDate", "YearlyLowPrice", "FirstTradingDate",
          "LastTradingDate", "Exchange", "SecTypeCode", "GeographicalAreaCode", "Tminus1Volume",
          "TotalTrades", "TotalTurnover", "DerivativeSecTypeCodeDesc"]
DEFAULTS = {
    "ShortName": "ABCDEV VON C 12/27", "ValorSymbol": "ABCDEV", "ValorNumber": "100",
    "ClosingPrice": "1.5", "DailyHighPrice": "", "DailyLowPrice": "", "LatestTradeDate": "20261105",
    "PreviousClosingPrice": "1.4", "OpeningPrice": "", "OnMarketVolume": "0", "TotalVolume": "0",
    "TradingBaseCurrency": "CHF", "YearlyHighDate": "", "YearlyHighPrice": "", "YearlyLowDate": "",
    "YearlyLowPrice": "", "FirstTradingDate": "20260101", "LastTradingDate": "20271217",
    "Exchange": "XQMH", "SecTypeCode": "OW", "GeographicalAreaCode": "CH", "Tminus1Volume": "0",
    "TotalTrades": "0", "TotalTurnover": "0", "DerivativeSecTypeCodeDesc": "Warrant",
}


def row(**overrides) -> str:
    values = {**DEFAULTS, **overrides}
    return "; ".join(values[f] for f in FIELDS[:-1]) + ";" + values[FIELDS[-1]]


def six_file(rows: list[str], produced: str = "23:45:05 2026-11-10") -> str:
    return "\n".join([HEADER, *rows, "", f"Produced at: {produced}"]) + "\n"


__all__ = ["make_isin", "row", "six_file", "is_valid_format", "is_valid_isin"]
