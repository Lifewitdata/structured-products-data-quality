import duckdb

from helpers import make_isin, row, six_file
from srp_dq.pipeline import process, write_db

A, B, C = make_isin("CH000000001"), make_isin("CH000000002"), make_isin("CH000000003")


def test_end_to_end_build(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "derivatives_2026-11-09.csv").write_text(six_file([
        row(ISIN=A, ValorNumber="1"),
        row(ISIN=B, ValorNumber="2", DerivativeSecTypeCodeDesc=""),
    ], produced="23:45:05 2026-11-09"))
    (raw / "derivatives_2026-11-10.csv").write_text(six_file([
        row(ISIN=A, ValorNumber="1", LastTradingDate="20261110"),
        row(ISIN=C, ValorNumber="3"),
    ]))

    db = tmp_path / "test.duckdb"
    write_db(process(raw), db)
    con = duckdb.connect(str(db))

    changes = con.execute("SELECT change_type, COUNT(*) FROM audit_log GROUP BY 1").fetchall()
    assert dict(changes) == {"INITIAL_LOAD": 2, "FIELD_CHANGE": 1, "NEW_LISTING": 1, "REMOVED": 1}

    lifecycle = con.execute("SELECT isin, event_type FROM v_lifecycle_events").fetchall()
    assert lifecycle == [(A, "MATURITY_BROUGHT_FORWARD")]

    issue = con.execute("SELECT status, resolution FROM issue_log WHERE isin = ?", parameters=[B]).fetchone()
    assert issue == ("RESOLVED", "ABSENT_FROM_SNAPSHOT")

    assert con.execute("SELECT COUNT(*) FROM product_history WHERE isin = ?", parameters=[A]).fetchone()[0] == 2
    assert con.execute("SELECT is_listed FROM products WHERE isin = ?", parameters=[B]).fetchone()[0] is False

    sla = dict(con.execute("""SELECT metric, status FROM v_sla_status
                          WHERE snapshot_date = DATE '2026-11-09'""").fetchall())
    assert sla["product_type_completeness_pct"] == "BREACHED"
    assert sla["critical_failures"] == "MET"
    con.close()


def test_failed_rebuild_preserves_existing_database(tmp_path):
    import pytest
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "derivatives_2026-11-10.csv").write_text(six_file([row(ISIN=A)]))
    tables = process(raw)
    db = tmp_path / "test.duckdb"
    write_db(tables, db)
    original = db.read_bytes()
    tables["products"] = tables["products"].drop(columns="isin")
    with pytest.raises(KeyError):
        write_db(tables, db)
    assert db.read_bytes() == original
    assert not list(tmp_path.glob("srp-build-*"))


def test_duplicate_keys_reject_snapshot(tmp_path):
    import pytest
    (tmp_path / "derivatives_2026-11-10.csv").write_text(six_file([row(ISIN=A), row(ISIN=A)]))
    with pytest.raises(ValueError, match="ambiguous ISIN"):
        process(tmp_path)


def test_incomplete_snapshot_rejected(tmp_path):
    import pytest
    (tmp_path / "derivatives_2026-11-10.csv").write_text(six_file([row(ISIN=A), "bad;row"]))
    with pytest.raises(ValueError, match="incomplete or malformed"):
        process(tmp_path)
