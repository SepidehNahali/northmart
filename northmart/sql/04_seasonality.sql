-- sql/04_seasonality.sql
--
-- Monthly revenue and transaction volume by category.
-- Used in Power BI to build the seasonality heat-map and
-- align staffing model to transaction demand.

SELECT
    d.year,
    d.month,
    d.month_name,
    p.category,
    COUNT(DISTINCT f.transaction_id)  AS txn_count,
    SUM(f.quantity)                   AS units_sold,
    ROUND(SUM(f.net_revenue), 0)      AS net_revenue,
    ROUND(SUM(f.margin), 0)           AS total_margin,
    ROUND(AVG(f.net_revenue), 2)      AS avg_basket_value
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
JOIN dim_date    d ON f.date_key    = d.date_key
GROUP BY d.year, d.month, d.month_name, p.category
ORDER BY d.year, d.month, p.category;
