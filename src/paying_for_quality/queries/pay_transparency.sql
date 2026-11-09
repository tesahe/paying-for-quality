-- Share of current, Core-accepted postings that state pay, by source.
WITH latest_raw AS (
    SELECT rp.id, rp.source_id
    FROM raw_posting rp
    WHERE rp.id = (SELECT MAX(r2.id) FROM raw_posting r2
                   WHERE r2.source_id = rp.source_id AND r2.external_id = rp.external_id)
),
current_posting AS (
    SELECT p.id, lr.source_id,
           CASE WHEN EXISTS (SELECT 1 FROM pay_quote q WHERE q.posting_id = p.id) THEN 1 ELSE 0 END AS has_pay
    FROM posting p
    JOIN latest_raw lr ON lr.id = p.raw_posting_id
    WHERE p.extraction_run_id = (SELECT MAX(p2.extraction_run_id) FROM posting p2
                                 WHERE p2.raw_posting_id = p.raw_posting_id)
)
SELECT s.slug AS source, s.segment, COUNT(*) AS postings, SUM(cp.has_pay) AS with_pay,
       ROUND(100.0 * SUM(cp.has_pay) / COUNT(*), 1) AS pct_with_pay
FROM current_posting cp
JOIN source s ON s.id = cp.source_id
GROUP BY s.slug, s.segment
ORDER BY s.slug
