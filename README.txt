SIX Structured Products Data Quality & Audit Pipeline

Independent data analyst portfolio aligned to SRP-style sourcing, validation, change monitoring and quality reporting. Not an SRP/Derivia system and not an authorised replica of their proprietary database.

REAL DATA
Official daily CSVs:
https://www.six-structured-products.com/en/latest-news/closing-prices
Initial study: 19 snapshots, 2026-10-15 to 2026-11-10.
1,973,871 product-day records; 129,237 distinct observed ISINs.
No synthetic products or processing logs. Small hand-made records are used only in tests.

SETUP (PowerShell, from this folder)
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m srp_dq.download
.\.venv\Scripts\python.exe -m srp_dq.pipeline
.\.venv\Scripts\python.exe -m srp_dq.report
.\.venv\Scripts\python.exe -m pytest -q

EXECUTE NOTEBOOK (PowerShell)
.\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=python3 --ExecutePreprocessor.timeout=600 notebooks/01_quality_analysis.ipynb
If no Python kernel is available, register this environment locally:
.\.venv\Scripts\python.exe -m ipykernel install --user --name srp-dq --display-name "SRP DQ"
Then use --ExecutePreprocessor.kernel_name=srp-dq. Kernel registration is optional and changes the user's local Jupyter configuration.

GIT BASH EQUIVALENT
PYTHONPATH=src .venv/Scripts/python -m srp_dq.pipeline
PYTHONPATH=src .venv/Scripts/python -m srp_dq.report
.venv/Scripts/python -m pytest -q

WHAT TO OPEN
notebooks/01_quality_analysis.ipynb: executable raw-data profiling, recomputed QC, source-spike investigation, audit/SCD checks and analyst interpretation.
reports/01_quality_analysis.html: browser-readable executed notebook.
reports/srp_quality_report.xlsx: styled Excel tables, frozen headers and interpretation notes; not native PivotTables.
reports/*.csv: Tableau-ready aggregates and exception extracts. No Tableau dashboard is claimed as built.
sql/schema.sql: typed DuckDB tables, primary keys, constraints and project quality targets.
sql/views.sql: reporting queries, lifecycle signals and quality-objective status.
docs/SOP.txt: sourcing, acceptance, review, escalation recommendations and change procedure.
data/srp_quality.duckdb: local database; excluded from Git.

KEY FINDINGS
Classification gaps spike on 2026-10-26 and 2026-11-09, relative to median 182 missing types. The notebook quantifies subsequent recovery and issuer concentration. All initially observed ISINs passed format/check-digit checks. These findings apply only to the downloaded study window and rules, not all SIX data.

LIMITATIONS
- The universe is Swiss-exchange listed products, predominantly leveraged instruments; it is not all European retail issuance.
- First/last trading dates are not necessarily issue/maturity dates.
- First observed / absent from next snapshot does not prove issuance / delisting.
- Old last trades do not prove quoted-price staleness. Numeric geographic codes can be valid regional values.
- Issuer names and EUSIPA assignments are provisional mappings. All issuer verified flags are false pending dated evidence. Mapped-code coverage does not imply legal-entity verification.
- Quality targets are project-defined, not client contracts. There are no real processing-time or cost logs, so no such SLA compliance claim is made.
- No coupon, barrier, underlying identifiers or formal lifecycle notices in the CSV: no barrier-breach engine, Monte Carlo pricing or coupon regression is claimed.
- The rolling download window may change on future runs. Acquisition timestamps for pre-manifest cached files are unknown, not reconstructed.
- Rebuilding uses the current methodology for all dates. Keep previous reports if changing rules or references.
- Check SIX licensing before publicly redistributing raw data or derived extracts. Git ignores raw files and the database; it does not grant redistribution rights.

TESTING
Unit/integration tests cover identifiers, parsing, all product rules, snapshot anomalies, issuer parsing, audit/SCD changes, issue episodes, database views and failed-build preservation. Live website availability and legal classifications are outside unit-test assurance.

VERSION CONTROL
This folder is an isolated Git repository. Raw CSVs, the local database and virtual environment are excluded from version control. Do not use the unrelated repository inherited from the Windows home folder.
