# Structured Products Data Quality & Audit Pipeline

**A real-data analyst project that turns daily SIX structured-product files into a validated database, traceable change history and actionable quality reports.**

Built with **Python, pandas, SQL, DuckDB, pytest and Excel**, this project demonstrates the sourcing, quality control, audit and documentation work expected in a structured-products data operation.

> Independent portfolio work aligned with SRP-style data-management responsibilities. This is not a Derivia Intelligence/SRP system, an endorsed project or a reproduction of their proprietary database.

## Project at a glance

| Measure | Initial study result |
|---|---:|
| Source | Official SIX structured-products daily CSVs |
| Study window | October 15 - November 10, 2026 |
| Daily snapshots | 19 |
| Product-day records | 1,973,871 |
| Distinct observed ISINs | 129,237 |
| Products in the latest snapshot | 103,675 |
| Audit events, including the initial load | 204,631 |
| Product-level quality rules | 18 |
| Snapshot-level review triggers | 3 |
| Automated tests | 63 passing in the verified build |

A **product-day record** is one product observed in one daily file, not a separate product or transaction. Counts describe the downloaded study window, not the whole European market.

## Start with the deliverables

You can review the results without installing Python:

- **[Executed analysis notebook](notebooks/01_quality_analysis.ipynb):** source profiling, quality-rule reconciliation, anomaly investigation, charts and written interpretation. GitHub can display the saved outputs.
- **[Excel quality report](reports/srp_quality_report.xlsx):** daily KPIs, quality-objective status, exception lists, issue summaries and interpretation notes. Download and open in Excel.
- **[Operating procedure](docs/SOP.txt):** acquisition, acceptance checks, review priorities, escalation recommendations and change management.
- **[Build summary](reports/build_summary.json):** machine-readable study counts and limitations.
- **[HTML analysis report](reports/01_quality_analysis.html):** the executed notebook in a browser-readable format. Download and open locally; GitHub's file viewer is not a hosted dashboard.

CSV aggregates and exception extracts in [reports](reports) can be imported into Tableau. **A Tableau dashboard is not included.**

## 1. Business problem

Structured-product records change over time. Product classifications may disappear temporarily, termination dates may move, and products may appear or disappear from a daily feed. An analyst needs to answer more than "does the file load?":

1. Is the source file structurally acceptable?
2. Are identifiers, dates, currencies and required fields valid?
3. What changed compared with the previous available snapshot?
4. Which exceptions remain open, and which are no longer observed?
5. Can another analyst reproduce the result and understand the review procedure?

The project addresses these questions with reproducible checks and an audit trail rather than silently cleaning away exceptions.

### Connection to the SRP data-analyst role

| Data-team responsibility | Evidence in this project |
|---|---|
| Maintain a high-quality product database | Typed SQL tables, identifier checks, quality rules and acceptance gates |
| Maintain an audit of changes | Field-level old/new values and SCD Type 2 reference history |
| Track issues and resolutions | Rule-based issue episodes with observed open/resolved status |
| Monitor delivery quality and highlight risks | Daily quality objectives and snapshot anomaly triggers |
| Keep procedures current | Versioned operating procedure and documented limitations |

Quality targets here are **project-defined demonstration objectives**, not actual client contract SLAs. The source does not provide team processing-time or cost records.

## 2. Real data source and scope

**Source:** [SIX Structured Products - Closing prices / Reference data](https://www.six-structured-products.com/en/latest-news/closing-prices).

The source publishes semicolon-separated daily files named `derivatives_YYYY-MM-DD.csv`. The initial study uses 19 downloaded files from October 15 through November 10, 2026. No synthetic market products or processing logs are mixed into the analysis. Hand-made records exist only in unit tests.

### Available fields

| Field group | Examples | How they are used |
|---|---|---|
| Identifiers | ISIN, Valor number, Valor symbol | Validation, product keys and snapshot matching |
| Product/reference data | Short name, product type, currency, security type, geographic area code | Classification, enrichment and reference-change monitoring |
| Trading dates | First trading date, last trading date, latest trade date | Date consistency and lifecycle review signals |
| Prices | Closing price, previous close, intraday and yearly ranges | Numeric parsing and consistency checks |
| Activity | On-market volume, trade count, turnover | Activity-context checks; selected fields retained in the daily market table |
| File metadata | Production timestamp in the footer | Snapshot-date validation and production-time review |

The source has **26 columns**. Not every field is persisted in the compact `daily_market` table; the raw-file loader and notebook retain access to the complete source schema.

**Scope matters:** this is a Swiss-exchange product universe containing many leveraged instruments. It is not a complete dataset of European retail issuance, issuer sales or client transactions.

### Source provenance and redistribution

The downloader records source URLs, byte counts, SHA-256 checksums and validation timestamps in a local acquisition manifest. Files cached before provenance tracking was introduced have unknown acquisition timestamps; those timestamps are not reconstructed.

Raw files, the local database and the virtual environment are excluded from Git. Public download access does not establish an unrestricted redistribution licence: review applicable SIX terms before redistributing raw data or derived extracts. No licence for SIX data is granted by this repository.

## 3. Workflow

```text
Official SIX download page
        |
        v
Discover links, validate payloads, cache CSVs and record checksums
        |
        v
Parse headers/footer, trim values and convert dates/numbers
        |
        v
Reject malformed files and ambiguous snapshot keys
        |
        v
Enrich issuer codes and provisional product classifications
        |
        +--> Run product-level QC and snapshot review checks
        |
        +--> Compare reference fields and maintain SCD Type 2 history
        |
        +--> Build observed issue episodes
        |
        v
Build DuckDB tables and reporting views
        |
        v
Executed notebook + Excel workbook + CSV reports + SOP
```

### What happens at each stage

1. **Acquire:** discover actual CSV links from the official page, validate downloads and write new files atomically.
2. **Parse:** remove repeated header blocks and the production footer from product rows; convert `YYYYMMDD` dates and numeric values.
3. **Accept or reject:** stop the build for malformed/unparseable snapshots, missing/mismatched footer dates, empty files or duplicate/null ISIN keys. A well-formed file can still have source omissions, so row-count swings remain review triggers.
4. **Enrich:** derive issuer codes from different short-name layouts and apply maintained reference tables. Issuer names and EUSIPA mappings are provisional, not authoritative legal-entity assignments.
5. **Validate:** apply product rules and inspect file-level volume, missing-classification and production-time anomalies.
6. **Audit:** compare reference fields by ISIN between adjacent available snapshots. Price movements are retained separately from reference-data changes.
7. **Monitor issues:** group consecutive observed ISIN/rule failures into episodes and track whether they remain open.
8. **Publish local outputs:** generate the database and analyst reports. A failed database build preserves the previous database through a staging file and transactional build.

## 4. Quality rules and review priorities

The [rule definitions](src/srp_dq/rules.py) contain **18 product-level checks**:

| Area | Examples |
|---|---|
| Identifiers | ISIN format/check digit, duplicate ISIN, duplicate Valor |
| Classification | Missing product type, unmapped product type |
| Reference data | Unknown or unverified issuer, invalid currency, numeric geographic code |
| Dates/lifecycle | Last trading date before first trading date, expired still present, future latest-trade date |
| Pricing/activity | Missing or non-positive close, daily high below low, positive volume without trades, old latest-trade date |

**Not all flags mean the source is wrong.**

- **Critical/high failures** prioritise identifier ambiguity, mandatory-field gaps and clear consistency problems for investigation.
- **Unverified issuer mappings** describe a local enrichment limitation. All issuer verification flags remain false pending dated supporting evidence.
- **Numeric geographic codes** can be legitimate regional codes. Preserve them until the source codebook is available.
- **Old last-trade dates** indicate trading inactivity, not necessarily stale quoted prices.
- **Zero prices** can require product-event context; do not automatically overwrite them.

Three snapshot-level review triggers identify:

- Absolute row-count movements greater than **1.5%** versus the previous file.
- Missing-type counts greater than **3 times** the study-window median.
- Production times more than **60 minutes** from the study-window median time of day.

These are transparent demonstration thresholds, not a validated forecasting model. Median-based checks use the collected study window retrospectively; they are not claimed as a production real-time alerting system.

### Project quality objectives

| Metric | Target | Interpretation |
|---|---:|---|
| Product-type completeness | >= 99.5% | Share of products with a non-missing product type |
| Issuer-code mapping coverage | >= 99.0% | Share whose parsed code exists in the reference table; not legal-entity verification |
| Products with critical failures | 0 | No product should fail a critical rule |
| Records without critical/high failures | >= 95.0% | Share passing those rule priorities, not every informational review flag |

Targets and reporting logic are defined in [schema.sql](sql/schema.sql) and [views.sql](sql/views.sql).

## 5. Audit history and issue tracking

### Reference-data audit

The audit log records snapshot date, ISIN, event type, field and old/new values for tracked reference fields. `product_history` stores **Slowly Changing Dimension Type 2 (SCD Type 2)** versions with half-open validity intervals: `[valid_from, valid_to)`.

| Audit label | What it establishes |
|---|---|
| `INITIAL_LOAD` | Baseline membership in the first downloaded snapshot |
| `NEW_LISTING` | First observed after the baseline; not confirmed issuance |
| `REMOVED` | Absent from the next available snapshot; not confirmed delisting |
| `RELISTED` | Observed again after absence; not a verified exchange relisting |
| `FIELD_CHANGE` | An observed difference in a tracked reference field |

Changes to last trading dates are **lifecycle signals**. A brought-forward date alone does not establish an autocall or barrier breach; confirmation requires an issuer notice or final terms.

### Issue episodes

Each consecutive observed failure of the same rule for an ISIN forms an issue episode:

- `OPEN`: still failing in the latest snapshot.
- `RESOLVED`: no longer observed failing in a subsequent snapshot.
- `NO_LONGER_FAILING`: present and passing the rule; not proof of a source or manual correction.
- `ABSENT_FROM_SNAPSHOT`: absent from the next observed file; not proof of redemption.

Resolution dates are observation bounds. Calendar days-to-resolve are not analyst handling times, and the study window censors episodes that began earlier or remain open at the end. The project does not fabricate human review decisions, approvals or root causes.

## 6. Main findings

The initial study identified **two temporary spikes in missing product classifications**:

| Snapshot | Products missing a type | Type completeness | Project completeness target |
|---|---:|---:|---|
| October 26, 2026 | 1,590 | 98.475% | Breached |
| November 9, 2026 | 2,885 | 97.239% | Breached |
| November 10, 2026 | 182 | 99.824% | Met |

The median missing-type count across the study was **182**. Both spikes were flagged by the snapshot checks and fell below the 99.5% completeness target. The notebook investigates issuer-code concentration and recovery on the next available day rather than automatically filling missing values.

Other observations:

- The recorded QC results show **no ISIN format/check-digit failures** in the study window.
- Snapshot volume changed **+1.66% on October 20** and **-2.23% on November 4**, triggering review of membership movements.
- The November 10 footer showed **18:45**, compared with the usual **23:45** production time. The source cutoff/timezone is not established here, so this is a review signal, not proof of an incomplete file.
- **182 high-priority classification issues** remained open in the latest snapshot.

**Recommended analyst action:** check the same ISIN across adjacent source files and confirm classification against final terms before correcting a value. Recovery suggests a transient observation gap; it does not establish the source's root cause.

Evidence: [daily quality](reports/daily_quality.csv), [snapshot checks](reports/snapshot_checks.csv), [rule summary](reports/rule_summary.csv) and the executed notebook.

## 7. Technology and repository structure

| Tool | Role |
|---|---|
| Python, requests, BeautifulSoup | Official-source link discovery and acquisition |
| pandas | Parsing, enrichment, comparisons and issue aggregation |
| DuckDB and SQL | Typed local database, keys/constraints and reporting views |
| pycountry | Currency-code reference |
| pytest | Unit and integration checks |
| Jupyter, matplotlib, seaborn | Executable investigation and charts |
| openpyxl | Styled Excel tables and workbook export |
| Git | Source and procedure version control |

```text
.
|-- README.md
|-- requirements.txt
|-- pyproject.toml
|-- src/srp_dq/                  # Acquisition, loading, QC, audit and reporting
|-- sql/                        # Schema and reporting views
|-- reference/                  # Provisional issuer and product-type mappings
|-- tests/                      # Unit and integration tests
|-- notebooks/                  # Executed analyst notebook
|-- reports/                    # Excel, HTML and CSV outputs
|-- docs/SOP.txt                # Operating procedure
`-- data/                       # Local raw files and database; excluded from Git
```

The Excel workbook contains styled tables and frozen headers, **not native PivotTables**. A web application, deployed dashboard and CI pipeline are not included.

## 8. Run the project

The initial build was verified on **Windows with Python 3.12** in an isolated environment. The following commands assume `uv` is installed and the shell is open in the repository root.

### Windows PowerShell

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
$env:PYTHONPATH = "$PWD\src"

# Download and validate the currently available source files.
.\.venv\Scripts\python.exe -m srp_dq.download

# Build the DuckDB database, quality results, audit history and issue log.
.\.venv\Scripts\python.exe -m srp_dq.pipeline

# Export Excel and CSV reports.
.\.venv\Scripts\python.exe -m srp_dq.report

# Run the automated tests.
.\.venv\Scripts\python.exe -m pytest -q
```

### Windows Git Bash

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
export PYTHONPATH=src

.venv/Scripts/python -m srp_dq.download
.venv/Scripts/python -m srp_dq.pipeline
.venv/Scripts/python -m srp_dq.report
.venv/Scripts/python -m pytest -q
```

The download page has a rolling history. **A fresh download later may not reproduce the original dates or counts.** Preserve the original cached snapshots when reproducing this study. Raw data and the DuckDB database are not bundled in the repository.

### Execute and export the notebook

For a deterministic notebook environment, optionally register the project's Python kernel. This command changes your local Jupyter kernel configuration:

```powershell
.\.venv\Scripts\python.exe -m ipykernel install --user --name srp-dq --display-name "SRP DQ"

.\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=srp-dq --ExecutePreprocessor.timeout=600 notebooks/01_quality_analysis.ipynb

.\.venv\Scripts\python.exe -m jupyter nbconvert --to html --output-dir reports notebooks/01_quality_analysis.ipynb
```

The saved notebook already contains executed outputs. Registering a kernel is only needed for local re-execution when a suitable kernel is not already available. Notebook execution and HTML export are separate from `srp_dq.report`.

## 9. Testing and reproducibility

The verified build passed **63 tests**, covering:

- Known ISINs, malformed identifiers and incorrect check digits.
- Repeated source headers, footer metadata, malformed rows and parsing failures.
- Issuer-code extraction across different short-name layouts.
- Clean records and deliberately invalid cases for the product rules.
- Snapshot volume, missing-type and production-time triggers.
- New/removed/reappearing products and reference-field differences.
- SCD version windows and issue-episode status transitions.
- SQL reporting views and preservation of an existing database after a failed rebuild.
- Excel/CSV reconciliation and spreadsheet formula-injection escaping.

The executed notebook also recomputes the latest snapshot's QC counts against stored results and checks SCD intervals for overlap.

Tests validate implemented behaviour. They do not verify website availability, legal-entity mappings, product terms or data-redistribution rights. Rebuilding recalculates all dates using the current methodology; retain dated reports before changing rules or reference mappings.

## 10. Limitations and next steps

| Limitation | What additional evidence would be needed |
|---|---|
| Provisional issuer names and EUSIPA mappings | Dated authoritative classification and legal-entity sources |
| Observed membership changes, not confirmed issuance/delisting | Exchange listing notices and issuer lifecycle announcements |
| No coupon, barrier or underlying identifiers | Real final terms, KIDs or issuer reference data |
| No actual time/cost SLA data | Genuine workflow timestamps and documented contract targets |
| Swiss-exchange scope | Additional exchange/issuer datasets before European-market generalisation |
| Numeric region codes not interpreted | SIX geographic codebook |
| Short rolling source history | A longer retained acquisition history |

The current project deliberately does **not** claim barrier-breach detection, Monte Carlo pricing, coupon regression, automated human-approved corrections or verified client SLA compliance.

Practical extensions are to verify reference mappings, retain a longer source history and build a Tableau quality dashboard from the existing reports. These are next steps, not completed deliverables.
