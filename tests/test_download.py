import pytest

from helpers import make_isin, row, six_file
from srp_dq.download import list_files, validate_payload


def test_valid_payload_and_bad_response():
    validate_payload(six_file([row(ISIN=make_isin("CH000000001"))]).encode(),
                     "derivatives_2026-11-10.csv")
    with pytest.raises(ValueError):
        validate_payload(b"<html>Access denied</html>", "derivatives_2026-11-10.csv")


def test_wrong_footer_date_rejected():
    payload = six_file([row(ISIN=make_isin("CH000000001"))], produced="23:45:05 2026-11-09")
    with pytest.raises(ValueError):
        validate_payload(payload.encode(), "derivatives_2026-11-10.csv")


def test_index_http_errors_are_not_silenced():
    class Response:
        def raise_for_status(self):
            raise RuntimeError("HTTP 503")

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    with pytest.raises(RuntimeError, match="HTTP 503"):
        list_files(Session())


def test_reordered_header_rejected():
    from helpers import HEADER
    payload = six_file([row(ISIN=make_isin("CH000000001"))])
    payload = payload.replace(HEADER, HEADER.replace("ClosingPrice; DailyHighPrice", "DailyHighPrice; ClosingPrice"))
    with pytest.raises(ValueError, match="header schema"):
        validate_payload(payload.encode(), "derivatives_2026-11-10.csv")
