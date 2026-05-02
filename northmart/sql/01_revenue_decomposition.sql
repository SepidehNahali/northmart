-- sql/01_revenue_decomposition.sql
--
-- Decompose year-over-year revenue delta by product category.
-- Run against the presentation layer (dim_* + fact_sales tables).
-- Requires: fact_sales, dim_product, dim_date

WITH base AS (
    SELECT
        p.category,
        SUM(CASE WHEN d.year = 2023 THEN f.net_revenue ELSE 0 END) AS rev_2023,
        SUM(CASE WHEN d.year = 2024 THEN f.net_revenue ELSE 0 END) AS rev_2024,
        SUM(CASE WHEN d.year = 2023 THEN f.margin ELSE 0 END)      AS margin_2023,
        SUM(CASE WHEN d.year = 2024 THEN f.margin ELSE 0 END)      AS margin_2024
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    JOIN dim_date    d ON f.date_key    = d.date_key
    GROUP BY p.category
)
SELECT
    category,
    ROUND(rev_2023, 2)                                                 AS rev_2023,
    ROUND(rev_2024, 2)                                                 AS rev_2024,
    ROUND(rev_2024 - rev_2023, 2)                                      AS revenue_delta,
    ROUND((rev_2024 - rev_2023) * 100.0 / NULLIF(rev_2023, 0), 1)     AS pct_change,
    ROUND(margin_2023, 2)                                              AS margin_2023,
    ROUND(margin_2024, 2)                                              AS margin_2024,
    ROUND((margin_2024 - margin_2023) * 100.0 / NULLIF(margin_2023, 0), 1) AS margin_pct_change
FROM base
ORDER BY revenue_delta ASC;
