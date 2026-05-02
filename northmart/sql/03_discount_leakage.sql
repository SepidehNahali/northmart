-- sql/03_discount_leakage.sql
--
-- Quantify discount leakage: total revenue given away vs margin impact.
-- Buckets transactions by discount depth to show where deep discounting
-- erodes margin without proportional volume uplift.

WITH disc_buckets AS (
    SELECT
        p.category,
        d.year,
        CASE
            WHEN f.discount_rate = 0              THEN '0%'
            WHEN f.discount_rate <= 0.05          THEN '1–5%'
            WHEN f.discount_rate <= 0.10          THEN '6–10%'
            WHEN f.discount_rate <= 0.20          THEN '11–20%'
            ELSE                                       '>20%'
        END AS discount_bucket,
        COUNT(*)              AS txn_count,
        SUM(f.gross_revenue)  AS gross_revenue,
        SUM(f.discount_amount) AS discount_given,
        SUM(f.net_revenue)    AS net_revenue,
        SUM(f.margin)         AS total_margin
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    JOIN dim_date    d ON f.date_key    = d.date_key
    GROUP BY p.category, d.year, discount_bucket
)
SELECT
    category,
    year,
    discount_bucket,
    txn_count,
    ROUND(gross_revenue, 0)                                          AS gross_revenue,
    ROUND(discount_given, 0)                                         AS discount_given,
    ROUND(net_revenue, 0)                                            AS net_revenue,
    ROUND(total_margin, 0)                                           AS total_margin,
    ROUND(discount_given * 100.0 / NULLIF(gross_revenue, 0), 1)     AS disc_pct_of_gross,
    ROUND(total_margin * 100.0 / NULLIF(net_revenue, 0), 1)         AS margin_rate_pct
FROM disc_buckets
ORDER BY category, year, discount_bucket;
