-- Median hourly rate (USD) by domain and rater kind, across every rate source (FR-9).
-- Aggregate only: rate_observation has no company column, so no company can be named or ranked.
-- Each observation contributes its hourly midpoint. n_provenance counts the distinct kinds of source
-- (job board, government statistic, literature, dataset paper) behind each row.
-- The median uses window functions so the same SQL runs on SQLite and Postgres.
WITH rated AS (
    SELECT domain, rater_kind, provenance_kind, (hourly_min_usd + hourly_max_usd) / 2.0 AS hourly_mid
    FROM rate_observation
),
ranked AS (
    SELECT domain, rater_kind, hourly_mid,
           ROW_NUMBER() OVER (PARTITION BY domain, rater_kind ORDER BY hourly_mid) AS rn,
           COUNT(*) OVER (PARTITION BY domain, rater_kind) AS n
    FROM rated
),
medians AS (
    SELECT domain, rater_kind, n, ROUND(AVG(hourly_mid), 2) AS median_hourly_usd
    FROM ranked
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
    GROUP BY domain, rater_kind, n
),
provenance AS (
    SELECT domain, rater_kind, COUNT(DISTINCT provenance_kind) AS n_provenance
    FROM rated
    GROUP BY domain, rater_kind
)
SELECT m.domain, m.rater_kind, m.n, p.n_provenance, m.median_hourly_usd
FROM medians m
JOIN provenance p ON p.domain = m.domain AND p.rater_kind = m.rater_kind
ORDER BY m.domain, m.median_hourly_usd DESC, m.rater_kind
