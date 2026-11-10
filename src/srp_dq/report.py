"""Export reproducible analyst reports and Tableau-ready aggregates."""
import json
from pathlib import Path

import duckdb
import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo

from srp_dq.pipeline import DB_PATH, ROOT

REPORT_DIR = ROOT / "reports"
QUERIES = {
    "daily_quality": "SELECT * FROM v_daily_quality",
    "sla_status": "SELECT * FROM v_sla_status ORDER BY snapshot_date, metric",
    "rule_summary": "SELECT * FROM v_rule_summary",
    "snapshot_checks": "SELECT * FROM snapshot_checks ORDER BY snapshot_date",
    "change_summary": "SELECT * FROM v_change_summary",
    "issue_kpis": "SELECT * FROM v_issue_kpis",
    "issuer_quality": "SELECT * FROM v_issuer_quality",
    "type_mix": """SELECT COALESCE(p.product_type, 'Missing') AS product_type,
                          COUNT(*) AS listed_products
                   FROM products p WHERE is_listed GROUP BY 1 ORDER BY 2 DESC""",
    "high_exceptions": """SELECT l.* FROM issue_log l
                          WHERE severity IN ('CRITICAL', 'HIGH') AND status = 'OPEN'
                          ORDER BY rule_id, isin""",
    "priority_review": """SELECT * FROM issue_log
                          WHERE status = 'OPEN' AND rule_id IN ('R07', 'R18')
                          ORDER BY rule_id, isin""",
}


def safe_text(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.select_dtypes(include=["object", "string"]).columns:
        out[c] = out[c].map(lambda x: "'" + x if isinstance(x, str)
                           and x.lstrip().startswith(("=", "+", "-", "@")) else x)
    return out


def export_reports(db_path: Path = DB_PATH, report_dir: Path = REPORT_DIR) -> dict:
    report_dir.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path), read_only=True) as con:
        frames = {name: con.execute(sql).fetchdf() for name, sql in QUERIES.items()}
        overview = con.execute("""SELECT MIN(snapshot_date), MAX(snapshot_date), COUNT(*)
                                  FROM snapshots""").fetchone()
        stats = {
            "start_date": str(overview[0]), "end_date": str(overview[1]), "snapshots": overview[2],
            "product_day_records": con.execute("SELECT COUNT(*) FROM daily_market").fetchone()[0],
            "distinct_products": con.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "audit_events_including_initial_load": con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
            "missing_type_peak": con.execute("""SELECT snapshot_date, COUNT(*) n FROM qc_results
                                                WHERE rule_id = 'R05' GROUP BY 1 ORDER BY 2 DESC LIMIT 1""").fetchone(),
            "limitations": [
                "Targets are project-defined quality objectives, not Derivia client SLAs.",
                "Issuer names and EUSIPA mapping are provisional; issuer verification is intentionally false.",
                "Numeric geography codes and old trades are review flags, not proven source errors.",
                "REMOVED means absent from next snapshot; NEW_LISTING means first observed, not confirmed issuance.",
                "NO_LONGER_FAILING does not prove a manual or source correction.",
                "No actual processing-time, cost, coupon, barrier or payoff data is available in this CSV.",
            ],
        }
    for name, df in frames.items():
        safe_text(df).to_csv(report_dir / f"{name}.csv", index=False)
    with pd.ExcelWriter(report_dir / "srp_quality_report.xlsx", engine="openpyxl") as writer:
        for name, df in frames.items():
            safe_text(df).to_excel(writer, sheet_name=name, index=False)
        pd.DataFrame({"interpretation_notes": stats["limitations"]}).to_excel(
            writer, sheet_name="read_first", index=False)
        for i, sheet in enumerate(writer.book.worksheets):
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.fill = PatternFill("solid", fgColor="17365D")
                cell.font = Font(color="FFFFFF", bold=True)
            for cells in sheet.columns:
                letter = cells[0].column_letter
                width = max(len(str(c.value or "")) for c in list(cells)[:200])
                sheet.column_dimensions[letter].width = min(60, max(14, width + 2))
            if sheet.max_row > 1:
                table = Table(displayName=f"ReportTable{i}", ref=sheet.dimensions)
                table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
                sheet.add_table(table)
    (report_dir / "build_summary.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    print(f"Reports written to {report_dir}")
    return stats


if __name__ == "__main__":
    export_reports()
