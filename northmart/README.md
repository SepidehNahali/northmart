# NorthMart Retail Sales Pipeline

End-to-end data engineering project: raw POS transactions → star schema → Power BI dashboard.

**Stack:** Python · SQLite / SQL Server · T-SQL · Power BI / DAX · scikit-learn

---

## What this does

1. Generates a synthetic POS dataset (602K transactions, 12 stores, 2023–2024)
2. Validates and loads it into a staging table
3. Transforms it into a star schema (`fact_sales` + four dimension tables)
4. Runs four analytical SQL queries to surface revenue drivers
5. Flags anomalous store-days with Isolation Forest, writes a watch-list table

The SQL layer targets SQL Server syntax; the repo runs on SQLite so no external DB is needed.

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
