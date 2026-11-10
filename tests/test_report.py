import pandas as pd
from openpyxl import load_workbook

from helpers import make_isin, row, six_file
from srp_dq.pipeline import process, write_db
from srp_dq.report import export_reports, safe_text


def test_spreadsheet_formula_injection_is_escaped():
    source = pd.DataFrame({'text': ['=CMD()', ' +SUM(1,2)', '@SUM(1)', '-1+2', 'normal', None]})
    safe = safe_text(source)
    assert safe.text.iloc[0] == "'=CMD()"
    assert safe.text.iloc[1] == "' +SUM(1,2)"
    assert safe.text.iloc[4] == 'normal'
    assert source.text.iloc[0] == '=CMD()'


def test_excel_and_csv_reports_reconcile(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / 'derivatives_2026-11-10.csv').write_text(six_file([
        row(ISIN=make_isin('CH000000001'), DerivativeSecTypeCodeDesc=''),
    ]))
    db = tmp_path / 'test.duckdb'
    write_db(process(raw), db)
    reports = tmp_path / 'reports'
    stats = export_reports(db, reports)
    assert stats['product_day_records'] == 1
    workbook = load_workbook(reports / 'srp_quality_report.xlsx')
    assert 'read_first' in workbook.sheetnames
    assert workbook['daily_quality'].freeze_panes == 'A2'
    assert workbook['high_exceptions'].max_row == 2
    assert len(workbook['daily_quality'].tables) == 1
    assert pd.read_csv(reports / 'daily_quality.csv')['products'].iloc[0] == 1
    assert pd.read_csv(reports / 'high_exceptions.csv')['rule_id'].tolist() == ['R05']
    workbook.close()
