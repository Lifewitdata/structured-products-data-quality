-- Core tables for the SIX structured-products data quality database.

CREATE TABLE snapshots (
    snapshot_date      DATE PRIMARY KEY,
    file_name          VARCHAR NOT NULL,
    produced_at        TIMESTAMP,
    raw_lines          INTEGER,
    header_lines       INTEGER,
    bad_lines          INTEGER,
    unparseable_values INTEGER,
    row_count          INTEGER NOT NULL
);

CREATE TABLE issuers (
    issuer_code VARCHAR PRIMARY KEY,
    issuer_name VARCHAR,
    verified    BOOLEAN NOT NULL
);

CREATE TABLE product_types (
    product_type    VARCHAR PRIMARY KEY,
    eusipa_code     INTEGER NOT NULL,
    eusipa_category VARCHAR NOT NULL,
    asset_class     VARCHAR NOT NULL
);

CREATE TABLE qc_rules (
    rule_id     VARCHAR PRIMARY KEY,
    rule_name   VARCHAR NOT NULL,
    severity    VARCHAR NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    category    VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    action      VARCHAR NOT NULL
);

-- Latest known reference data per product (one row per ISIN).
CREATE TABLE products (
    isin               VARCHAR PRIMARY KEY,
    short_name         VARCHAR,
    valor_symbol       VARCHAR,
    valor_number       VARCHAR,
    issuer_code        VARCHAR,
    product_type       VARCHAR,
    sec_type_code      VARCHAR,
    currency           VARCHAR,
    geo_area_code      VARCHAR,
    first_trading_date DATE,
    last_trading_date  DATE,
    first_seen         DATE NOT NULL,
    last_seen          DATE NOT NULL,
    is_listed          BOOLEAN NOT NULL
);

-- SCD Type 2: every version of a product's reference data.
CREATE TABLE product_history (
    isin               VARCHAR NOT NULL,
    version            INTEGER NOT NULL,
    short_name         VARCHAR,
    valor_symbol       VARCHAR,
    valor_number       VARCHAR,
    issuer_code        VARCHAR,
    product_type       VARCHAR,
    sec_type_code      VARCHAR,
    currency           VARCHAR,
    geo_area_code      VARCHAR,
    first_trading_date DATE,
    last_trading_date  DATE,
    valid_from         DATE NOT NULL,
    valid_to           DATE,
    is_current         BOOLEAN NOT NULL,
    PRIMARY KEY (isin, version)
);

CREATE TABLE daily_market (
    snapshot_date    DATE NOT NULL,
    isin             VARCHAR NOT NULL,
    closing_price    DOUBLE,
    previous_close   DOUBLE,
    daily_high       DOUBLE,
    daily_low        DOUBLE,
    latest_trade_date DATE,
    on_market_volume DOUBLE,
    total_trades     DOUBLE,
    total_turnover   DOUBLE,
    PRIMARY KEY (snapshot_date, isin)
);

CREATE TABLE audit_log (
    audit_id      BIGINT PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    isin          VARCHAR NOT NULL,
    change_type   VARCHAR NOT NULL
        CHECK (change_type IN ('INITIAL_LOAD', 'NEW_LISTING', 'RELISTED', 'REMOVED', 'FIELD_CHANGE')),
    field         VARCHAR,
    old_value     VARCHAR,
    new_value     VARCHAR
);

CREATE TABLE qc_results (
    snapshot_date DATE NOT NULL,
    isin          VARCHAR NOT NULL,
    rule_id       VARCHAR NOT NULL REFERENCES qc_rules (rule_id),
    PRIMARY KEY (snapshot_date, isin, rule_id)
);

CREATE TABLE snapshot_checks (
    snapshot_date DATE NOT NULL,
    check_id      VARCHAR NOT NULL,
    check_name    VARCHAR NOT NULL,
    severity      VARCHAR NOT NULL,
    detail        VARCHAR,
    PRIMARY KEY (snapshot_date, check_id)
);

CREATE TABLE issue_log (
    issue_id        VARCHAR PRIMARY KEY,
    rule_id         VARCHAR NOT NULL REFERENCES qc_rules (rule_id),
    rule_name       VARCHAR NOT NULL,
    severity        VARCHAR NOT NULL,
    category        VARCHAR NOT NULL,
    isin            VARCHAR NOT NULL,
    first_seen      DATE NOT NULL,
    last_seen       DATE NOT NULL,
    days_failing    INTEGER NOT NULL,
    status          VARCHAR NOT NULL CHECK (status IN ('OPEN', 'RESOLVED')),
    resolved_on     DATE,
    resolution      VARCHAR,
    days_to_resolve INTEGER,
    action          VARCHAR
);

CREATE TABLE sla_targets (
    metric      VARCHAR PRIMARY KEY,
    target      DOUBLE NOT NULL,
    direction   VARCHAR NOT NULL CHECK (direction IN ('min', 'max')),
    description VARCHAR NOT NULL
);

INSERT INTO sla_targets VALUES
    ('product_type_completeness_pct', 99.5, 'min', 'Share of listed products with a product type'),
    ('issuer_mapped_pct',             99.0, 'min', 'Share of products whose issuer resolves to the reference table'),
    ('critical_failures',              0.0, 'max', 'Products failing any CRITICAL rule'),
    ('clean_record_pct',              95.0, 'min', 'Share of products with no CRITICAL/HIGH failure');
