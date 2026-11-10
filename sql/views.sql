-- Reporting views over the quality database.

CREATE OR REPLACE VIEW v_daily_quality AS
WITH listed AS (
    SELECT snapshot_date, COUNT(*) AS products FROM daily_market GROUP BY snapshot_date
),
fails AS (
    SELECT q.snapshot_date,
           COUNT(DISTINCT q.isin) FILTER (WHERE r.severity = 'CRITICAL')            AS critical_products,
           COUNT(DISTINCT q.isin) FILTER (WHERE r.severity IN ('CRITICAL', 'HIGH')) AS critical_high_products,
           COUNT(*) FILTER (WHERE q.rule_id = 'R05')                              AS missing_type,
           COUNT(*) FILTER (WHERE q.rule_id = 'R07')                              AS unknown_issuer
    FROM qc_results q JOIN qc_rules r USING (rule_id)
    GROUP BY q.snapshot_date
)
SELECT l.snapshot_date,
       l.products,
       COALESCE(f.critical_products, 0)                                         AS critical_failures,
       COALESCE(f.critical_high_products, 0)                                    AS critical_high_products,
       ROUND(100 - 100.0 * COALESCE(f.missing_type, 0) / l.products, 3)         AS product_type_completeness_pct,
       ROUND(100 - 100.0 * COALESCE(f.unknown_issuer, 0) / l.products, 3)       AS issuer_mapped_pct,
       ROUND(100 - 100.0 * COALESCE(f.critical_high_products, 0) / l.products, 3) AS clean_record_pct
FROM listed l LEFT JOIN fails f USING (snapshot_date)
ORDER BY l.snapshot_date;

CREATE OR REPLACE VIEW v_sla_daily AS
SELECT d.snapshot_date,
       t.metric,
       t.target,
       t.direction,
       CASE t.metric
           WHEN 'product_type_completeness_pct' THEN d.product_type_completeness_pct
           WHEN 'issuer_mapped_pct'             THEN d.issuer_mapped_pct
           WHEN 'critical_failures'             THEN d.critical_failures
           WHEN 'clean_record_pct'              THEN d.clean_record_pct
       END AS actual
FROM v_daily_quality d CROSS JOIN sla_targets t;

CREATE OR REPLACE VIEW v_sla_status AS
SELECT *,
       CASE WHEN (direction = 'min' AND actual >= target) OR (direction = 'max' AND actual <= target)
            THEN 'MET' ELSE 'BREACHED' END AS status
FROM v_sla_daily;

CREATE OR REPLACE VIEW v_rule_summary AS
SELECT r.rule_id, r.rule_name, r.severity, r.category,
       COUNT(q.isin) FILTER (WHERE q.snapshot_date = (SELECT MAX(snapshot_date) FROM snapshots)) AS failures_latest,
       COUNT(q.isin)                                                                             AS failures_all_days,
       COUNT(DISTINCT q.isin)                                                               AS distinct_products
FROM qc_rules r LEFT JOIN qc_results q USING (rule_id)
GROUP BY r.rule_id, r.rule_name, r.severity, r.category
ORDER BY r.rule_id;

CREATE OR REPLACE VIEW v_issuer_quality AS
WITH latest AS (SELECT MAX(snapshot_date) AS d FROM snapshots),
base AS (
    SELECT p.issuer_code, COALESCE(i.issuer_name, p.issuer_code) AS issuer, p.isin
    FROM products p LEFT JOIN issuers i USING (issuer_code)
    WHERE p.is_listed
),
fails AS (
    SELECT DISTINCT q.isin
    FROM qc_results q JOIN qc_rules r USING (rule_id), latest
    WHERE q.snapshot_date = latest.d AND r.severity IN ('CRITICAL', 'HIGH')
)
SELECT b.issuer,
       COUNT(*)                                          AS listed_products,
       COUNT(f.isin)                                     AS products_with_high_issues,
       ROUND(100.0 * COUNT(f.isin) / COUNT(*), 2)        AS high_issue_rate_pct
FROM base b LEFT JOIN fails f USING (isin)
GROUP BY b.issuer
ORDER BY listed_products DESC;

CREATE OR REPLACE VIEW v_change_summary AS
SELECT snapshot_date,
       COUNT(*) FILTER (WHERE change_type = 'NEW_LISTING')  AS new_listings,
       COUNT(*) FILTER (WHERE change_type = 'RELISTED')     AS relisted,
       COUNT(*) FILTER (WHERE change_type = 'REMOVED')      AS removed,
       COUNT(*) FILTER (WHERE change_type = 'FIELD_CHANGE') AS field_changes
FROM audit_log
WHERE change_type <> 'INITIAL_LOAD'
GROUP BY snapshot_date
ORDER BY snapshot_date;

CREATE OR REPLACE VIEW v_lifecycle_events AS
SELECT a.snapshot_date,
       a.isin,
       h.product_type,
       h.issuer_code,
       CASE
           WHEN a.old_value IS NULL                                THEN 'TERMINATION_DATE_SET'
           WHEN CAST(a.new_value AS DATE) < CAST(a.old_value AS DATE) THEN 'MATURITY_BROUGHT_FORWARD'
           WHEN CAST(a.new_value AS DATE) > CAST(a.old_value AS DATE) THEN 'MATURITY_EXTENDED'
           ELSE 'TERMINATION_DATE_REMOVED'
       END AS event_type,
       CAST(a.old_value AS DATE) AS old_last_trading_date,
       CAST(a.new_value AS DATE) AS new_last_trading_date
FROM audit_log a
JOIN product_history h ON a.isin = h.isin
    AND a.snapshot_date >= h.valid_from
    AND (h.valid_to IS NULL OR a.snapshot_date < h.valid_to)
WHERE a.change_type = 'FIELD_CHANGE' AND a.field = 'last_trading_date';

CREATE OR REPLACE VIEW v_issue_kpis AS
SELECT severity, rule_name,
       COUNT(*)                                       AS issues,
       COUNT(*) FILTER (WHERE status = 'OPEN')        AS open_issues,
       COUNT(*) FILTER (WHERE status = 'RESOLVED')    AS resolved_issues,
       ROUND(AVG(days_to_resolve), 2)                 AS avg_days_to_resolve,
       COUNT(*) FILTER (WHERE resolution = 'NO_LONGER_FAILING') AS no_longer_failing,
       COUNT(*) FILTER (WHERE resolution = 'ABSENT_FROM_SNAPSHOT')     AS absent_from_snapshot
FROM issue_log
GROUP BY severity, rule_name
ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END, issues DESC;
