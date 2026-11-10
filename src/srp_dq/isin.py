"""ISIN structure and check-digit validation (ISO 6166, Luhn over letter-expanded digits)."""
import re

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def isin_check_digit(body: str) -> int:
    digits = "".join(str(int(c, 36)) for c in body)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10


def is_valid_format(isin: str | None) -> bool:
    return isinstance(isin, str) and bool(ISIN_RE.match(isin))


def is_valid_isin(isin: str | None) -> bool:
    return is_valid_format(isin) and isin_check_digit(isin[:11]) == int(isin[11])
