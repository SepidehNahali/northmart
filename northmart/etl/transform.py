"""
etl/transform.py

Reads stg_pos_transactions and builds a star schema:

    dim_date      — calendar attributes
    dim_store     — store master
    dim_product   — SKU / category master
    fact_sales    — grain: one row per line item

Run after ingest.py:

    python etl/transform.py
    python etl/transform.py --db path/to/northmart.db
"""

import argparse
import logging

import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# dimension builders
# ------------------------------------------------------------------

def build_dim_date(dates: pd.Series) -> pd.DataFrame:
    all_dates = pd.date_range(dates.min(), dates.max(), freq="D")
    df = pd.DataFrame({"full_date": all_dates})
    df["date_key"]    = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["year"]        = df["full_date"].dt.year
    df["quarter"]     = df["full_date"].dt.quarter
    df["month"]       = df["full_date"].dt.month
    df["month_name"]  = df["full_date"].dt.strftime("%B")
    df["week"]        = df["full_date"].dt.isocalendar().week.astype(int)
    df["day_of_week"] = df["full_date"].dt.day_name()
    df["is_weekend"]  = df["full_date"].dt.dayofweek >= 5
    df["fiscal_year"] = df["year"]   # fiscal year == calendar year for NorthMart
    df["fiscal_quarter"] = "FY" + df["year"].astype(str) + "-Q" + df["quarter"].astype(str)
    return df


def build_dim_store(raw: pd.DataFrame) -> pd.DataFrame:
    df = (
        raw[["store_id", "city", "province"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    df["store_key"] = df.index + 1
    # Reorder so surrogate key is first
    return df[["store_key", "store_id", "city", "province"]]


def build_dim_product(raw: pd.DataFrame) -> pd.DataFrame:
    df = (
        raw[["sku", "category"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    df["product_key"] = df.index + 1
    return df[["product_key", "sku", "category"]]


def build_fact_sales(
    raw: pd.DataFrame,
    dim_date: pd.DataFrame,
    dim_store: pd.DataFrame,
    dim_product: pd.DataFrame,
) -> pd.DataFrame:
    df = raw.copy()

    # join date key
    df["date_key"] = df["txn_date"].dt.strftime("%Y%m%d").astype(int)

    # join store key
    df = df.merge(dim_store[["store_key", "store_id"]], on="store_id", how="left")

    # join product key
    df = df.merge(dim_product[["product_key", "sku"]], on="sku", how="left")

    fact = df[[
        "transaction_id",
        "date_key",
        "store_key",
        "product_key",
        "quantity",
        "unit_price",
        "discount_rate",
        "gross_revenue",
        "discount_amount",
        "net_revenue",
        "margin",
    ]].copy()

    nulls = fact[["date_key", "store_key", "product_key"]].isnull().sum()
    if nulls.any():
        log.warning("unresolved FK nulls:\n%s", nulls[nulls > 0])

    return fact


# ------------------------------------------------------------------
# orchestration
# ------------------------------------------------------------------

def transform(db_path: str) -> None:
    engine = create_engine(f"sqlite:///{db_path}")

    log.info("reading staging table")
    raw = pd.read_sql("SELECT * FROM stg_pos_transactions", engine, parse_dates=["txn_date"])
    log.info("%d rows in staging", len(raw))

    dim_date    = build_dim_date(raw["txn_date"])
    dim_store   = build_dim_store(raw)
    dim_product = build_dim_product(raw)
    fact_sales  = build_fact_sales(raw, dim_date, dim_store, dim_product)

    tables = {
        "dim_date":    dim_date,
        "dim_store":   dim_store,
        "dim_product": dim_product,
        "fact_sales":  fact_sales,
    }

    with engine.begin() as conn:
        for name in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {name}"))

    for name, df in tables.items():
        df.to_sql(name, engine, if_exists="replace", index=False)
        log.info("wrote %s: %d rows", name, len(df))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="northmart.db")
    args = parser.parse_args()
    transform(args.db)


if __name__ == "__main__":
    main()
