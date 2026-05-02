"""
etl/ingest.py

Loads raw POS CSV into an in-process SQLite database that mirrors the
SQL Server staging schema used in production.  SQLite is used here so
the repo runs without any external dependencies; swap the engine URL
for a real SQL Server connection string in production.

    python etl/ingest.py
    python etl/ingest.py --db path/to/northmart.db --src data/northmart_pos_raw.csv
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

EXPECTED_COLUMNS = {
    "transaction_id",
    "txn_date",
    "store_id",
    "city",
    "province",
    "sku",
    "category",
    "unit_price",
    "quantity",
    "discount_rate",
    "gross_revenue",
    "discount_amount",
    "net_revenue",
    "margin",
}

NUMERIC_COLS = ["unit_price", "quantity", "discount_rate", "gross_revenue",
                "discount_amount", "net_revenue", "margin"]


def validate(df: pd.DataFrame) -> pd.DataFrame:
    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"source is missing columns: {missing}")

    before = len(df)

    df = df.drop_duplicates(subset=["transaction_id"])
    dupes_dropped = before - len(df)
    if dupes_dropped:
        log.warning("dropped %d duplicate transaction_id rows", dupes_dropped)

    null_mask = df[["transaction_id", "txn_date", "store_id", "sku", "net_revenue"]].isnull().any(axis=1)
    if null_mask.sum():
        log.warning("dropping %d rows with nulls in key fields", null_mask.sum())
        df = df[~null_mask]

    for col in NUMERIC_COLS:
        bad = df[col] < 0
        if bad.sum():
            log.warning("zeroing %d negative values in %s", bad.sum(), col)
            df.loc[bad, col] = 0.0

    disc_bad = df["discount_rate"] > 1.0
    if disc_bad.sum():
        log.warning("clamping %d discount_rate values > 1.0", disc_bad.sum())
        df.loc[disc_bad, "discount_rate"] = 1.0

    log.info("validation complete: %d rows accepted (dropped %d total)",
             len(df), before - len(df))
    return df


def load(df: pd.DataFrame, engine, table: str = "stg_pos_transactions") -> None:
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df["loaded_at"] = pd.Timestamp.utcnow()

    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table}"))

    df.to_sql(table, engine, if_exists="replace", index=False, chunksize=10_000)
    log.info("loaded %d rows into %s", len(df), table)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default="data/northmart_pos_raw.csv")
    parser.add_argument("--db",  default="northmart.db")
    args = parser.parse_args()

    src = Path(args.src)
    if not src.exists():
        raise FileNotFoundError(f"{src} not found — run data/generate_dataset.py first")

    log.info("reading %s", src)
    df = pd.read_csv(src, parse_dates=["txn_date"])

    df = validate(df)

    engine = create_engine(f"sqlite:///{args.db}")
    load(df, engine)
    log.info("done → %s", args.db)


if __name__ == "__main__":
    main()
