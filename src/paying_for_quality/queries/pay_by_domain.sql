-- Median hourly pay (USD) by segment and domain, over current, Core-accepted postings.
-- "Current" = latest snapshot of each listing, latest accepted extraction of that snapshot.
-- Each posting contributes one value: the average midpoint of its normalizable pay quotes.
-- The median uses window functions so the same SQL runs on SQLite and Postgres.
WITH latest_raw AS (
    SELECT rp.id, rp.source_id
    FROM raw_posting rp
    WHERE rp.id = (SELECT MAX(r2.id) FROM raw_posting r2
                   WHERE r2.source_id = rp.source_id AND r2.external_id = rp.external_id)
),
current_posting AS (
    SELECT p.id, p.domain, s.segment
    FROM posting p
    JOIN latest_raw lr ON lr.id = p.raw_posting_id
    JOIN source s ON s.id = lr.source_id
    WHERE p.extraction_run_id = (SELECT MAX(p2.extraction_run_id) FROM posting p2
                                 WHERE p2.raw_posting_id = p.raw_posting_id)
),
posting_pay AS (
    SELECT cp.id, cp.segment, COALESCE(cp.domain, 'unknown') AS domain,
           AVG((q.hourly_min_usd + q.hourly_max_usd) / 2.0) AS hourly_mid
    FROM current_posting cp
    JOIN pay_quote q ON q.posting_id = cp.id
    WHERE q.hourly_min_usd IS NOT NULL
    GROUP BY cp.id, cp.segment, cp.domain
),
ranked AS (
    SELECT segment, domain, hourly_mid,
           ROW_NUMBER() OVER (PARTITION BY segment, domain ORDER BY hourly_mid) AS rn,
           COUNT(*) OVER (PARTITION BY segment, domain) AS n
    FROM posting_pay
)
SELECT segment, domain, n, ROUND(AVG(hourly_mid), 2) AS median_hourly_usd
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY segment, domain, n
ORDER BY median_hourly_usd DESC, domain
