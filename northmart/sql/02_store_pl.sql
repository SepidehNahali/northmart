-- sql/02_store_pl.sql
--
-- Store-level P&L drill-through.
-- Surfaces which stores are responsible for margin compression
-- and whether the driver is volume, discount depth, or mix shift.

WITH store_year AS (
    SELECT
        s.store_id,
        s.city,
        d.year,
        COUNT(DISTINCT f.transaction_id)                   AS txn_count,
        SUM(f.quantity)                                    AS units_sold,
        SUM(f.gross_revenue)                               AS gross_revenue,
        SUM(f.discount_amount)                             AS total_discount,
        SUM(f.net_revenue)                                 AS net_revenue,
        SUM(f.margin)                                      AS total_margin,
        AVG(f.discount_rate)                               AS avg_discount_rate
    FROM fact_sales f
    JOIN dim_store s ON f.store_key = s.store_key
    JOIN dim_date  d ON f.date_key  = d.date_key
    GROUP BY s.store_id, s.city, d.year
),
pivoted AS (
    SELECT
        store_id,
        city,
        MAX(CASE WHEN year = 2023 THEN net_revenue   END) AS rev_2023,
        MAX(CASE WHEN year = 2024 THEN net_revenue   END) AS rev_2024,
        MAX(CASE WHEN year = 2023 THEN total_margin  END) AS margin_2023,
        MAX(CASE WHEN year = 2024 THEN total_margin  END) AS margin_2024,
        MAX(CASE WHEN year = 2023 THEN avg_discount_rate END) AS disc_2023,
        MAX(CASE WHEN year = 2024 THEN avg_discount_rate END) AS disc_2024
    FROM store_year
    GROUP BY store_id, city
)
SELECT
    store_id,
    city,
    ROUND(rev_2023, 0)                                                    AS rev_2023,
    ROUND(rev_2024, 0)                                                    AS rev_2024,
    ROUND(rev_2024 - rev_2023, 0)                                         AS rev_delta,
    ROUND((rev_2024 - rev_2023) * 100.0 / NULLIF(rev_2023, 0), 1)        AS rev_pct,
    ROUND(margin_2023, 0)                                                 AS margin_2023,
    ROUND(margin_2024, 0)                                                 AS margin_2024,
    ROUND((margin_2024 - margin_2023) * 100.0 / NULLIF(margin_2023, 0), 1) AS margin_pct,
    ROUND(disc_2023 * 100, 2)                                             AS avg_disc_pct_2023,
    ROUND(disc_2024 * 100, 2)                                             AS avg_disc_pct_2024,
    ROUND((disc_2024 - disc_2023) * 100, 2)                               AS disc_depth_change_pp
FROM pivoted
ORDER BY margin_pct ASC;
