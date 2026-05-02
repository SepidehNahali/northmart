[README.md](https://github.com/user-attachments/files/27302892/README.md)
# NorthMart Retail Sales Pipeline

A fictional Ontario retailer's finance team had no reliable way to attribute revenue shifts — YoY declines were blamed on "market conditions" with no data to back it up. This project builds the pipeline that changes that: raw POS transactions → validated staging → star schema → self-serve Power BI dashboard with an anomaly detection layer.

Data is synthetic (590K transactions, 12 stores, 2023–2024) with realistic seasonality and deliberate business dynamics baked in — excess discounting in Electronics, a demand surge in Health & Wellness — so the analytical layer produces meaningful, non-trivial findings.

**Stack:** Python · SQL Server / SQLite · T-SQL · Power BI · DAX · scikit-learn

---

## Pipeline

```
CSV (daily POS export)
  → ingest.py          schema validation, dedup, null handling
  → transform.py       star schema: fact_sales + 4 dim tables
  → SQL queries        revenue decomposition, store P&L, discount leakage, seasonality
  → detect_anomalies.py  Isolation Forest on store-day aggregates → anomaly_watchlist table
  → Power BI           DirectQuery on fact_sales + anomaly_watchlist, RLS by region
```

The SQL layer is written in T-SQL (SQL Server). The repo runs on SQLite with no external dependencies — swap one engine string to point at a real server (see [Production notes](#production-notes)).

---

## Anomaly detection

`detect_anomalies.py` aggregates each (store, day) pair into four features — `net_revenue`, `txn_count`, `avg_basket_value`, `avg_discount_rate` — then fits an Isolation Forest (`contamination=0.03`). Flagged rows land in an `anomaly_watchlist` table that feeds a watch-list tile in Power BI, giving the ops team early warning before month-end close.

---

## Repo layout

```
northmart/
├── data/
│   └── generate_dataset.py     # produces northmart_pos_raw.csv
├── etl/
│   ├── ingest.py               # validates CSV and loads into staging
│   └── transform.py            # staging → star schema
├── sql/
│   ├── 01_revenue_decomposition.sql
│   ├── 02_store_pl.sql
│   ├── 03_discount_leakage.sql
│   └── 04_seasonality.sql
├── analysis/
│   └── revenue_analysis.py     # runs SQL queries, exports CSVs + charts
├── anomaly/
│   └── detect_anomalies.py     # Isolation Forest on store-day aggregates
└── tests/
    └── test_pipeline.py
```

---

## Quickstart

```bash
pip install pandas numpy sqlalchemy scikit-learn matplotlib

# 1. generate the dataset
python data/generate_dataset.py

# 2. ingest + transform
python etl/ingest.py
python etl/transform.py

# 3. run analysis
python analysis/revenue_analysis.py

# 4. flag anomalies
python anomaly/detect_anomalies.py

# 5. run tests
pytest tests/
```

All artefacts land in `analysis/outputs/` and `anomaly/outputs/`.

---

## Key findings

| Category | 2023 Revenue | 2024 Revenue | Delta |
|---|---|---|---|
| Electronics | $54.3M | $41.6M | −23% |
| Health & Wellness | $9.0M | $11.8M | +31% |

- Electronics decline traced to excess discounting, not demand loss (`03_discount_leakage.sql`)
- Health & Wellness demand outpaced stock; reorder model built in DAX
- 3 stores account for 61% of margin compression (`02_store_pl.sql`)

---

## Production notes

Swap the SQLite engine string in `etl/ingest.py` and `etl/transform.py` for a SQL Server URL:

```python
engine = create_engine("mssql+pyodbc://user:pass@server/NorthMart?driver=ODBC+Driver+17+for+SQL+Server")
```

The watermark table pattern in `ingest.py` supports incremental daily loads. Power BI DirectQuery connects to the `fact_sales` and `anomaly_watchlist` tables with row-level security scoped by region.
