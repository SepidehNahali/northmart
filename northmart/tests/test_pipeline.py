"""
tests/test_pipeline.py

Data-integrity and unit tests for the ETL pipeline.
Run with:  pytest tests/
"""

import pandas as pd
import pytest
from sqlalchemy import create_engine

from etl.ingest import validate
from etl.transform import build_dim_date, build_dim_product, build_dim_store, build_fact_sales


# ------------------------------------------------------------------
# fixtures
# ------------------------------------------------------------------

@pytest.fixture
def sample_raw() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "transaction_id":  ["TXN001", "TXN002", "TXN003"],
            "txn_date":        ["2024-01-15", "2024-02-20", "2024-03-05"],
            "store_id":        ["S01", "S02", "S01"],
            "city":            ["North York", "Scarborough", "North York"],
            "province":        ["Ontario", "Ontario", "Ontario"],
            "sku":             ["EL001", "HW003", "EL001"],
            "category":        ["Electronics", "Health & Wellness", "Electronics"],
            "unit_price":      [199.99, 24.99, 199.99],
            "quantity":        [1, 2, 3],
            "discount_rate":   [0.0, 0.05, 0.10],
            "gross_revenue":   [199.99, 49.98, 599.97],
            "discount_amount": [0.0, 2.499, 59.997],
            "net_revenue":     [199.99, 47.481, 539.973],
            "margin":          [35.998, 19.94, 97.195],
        }
    )


# ------------------------------------------------------------------
# ingest / validation
# ------------------------------------------------------------------

def test_validate_passes_clean_data(sample_raw):
    df = sample_raw.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    result = validate(df)
    assert len(result) == 3


def test_validate_drops_duplicates(sample_raw):
    df = pd.concat([sample_raw, sample_raw.iloc[[0]]], ignore_index=True)
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    result = validate(df)
    assert len(result) == 3


def test_validate_drops_null_key_fields(sample_raw):
    df = sample_raw.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df.loc[0, "net_revenue"] = None
    result = validate(df)
    assert len(result) == 2


def test_validate_zeroes_negative_values(sample_raw):
    df = sample_raw.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df.loc[1, "net_revenue"] = -50.0
    result = validate(df)
    assert result.loc[result["transaction_id"] == "TXN002", "net_revenue"].iloc[0] == 0.0


def test_validate_clamps_discount_rate(sample_raw):
    df = sample_raw.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df.loc[0, "discount_rate"] = 1.5
    result = validate(df)
    assert result.loc[result["transaction_id"] == "TXN001", "discount_rate"].iloc[0] == 1.0


def test_validate_raises_on_missing_columns(sample_raw):
    df = sample_raw.drop(columns=["net_revenue"])
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    with pytest.raises(ValueError, match="missing columns"):
        validate(df)


# ------------------------------------------------------------------
# dimension builders
# ------------------------------------------------------------------

def test_dim_date_covers_full_range(sample_raw):
    dates = pd.to_datetime(sample_raw["txn_date"])
    dim = build_dim_date(dates)
    assert dim["full_date"].min() <= pd.Timestamp("2024-01-15")
    assert dim["full_date"].max() >= pd.Timestamp("2024-03-05")
    assert set(dim.columns) >= {"date_key", "year", "month", "quarter", "is_weekend"}


def test_dim_date_key_is_unique(sample_raw):
    dates = pd.to_datetime(sample_raw["txn_date"])
    dim = build_dim_date(dates)
    assert dim["date_key"].is_unique


def test_dim_store_deduplicates(sample_raw):
    dim = build_dim_store(sample_raw)
    assert len(dim) == 2   # S01 and S02
    assert "store_key" in dim.columns
    assert dim["store_key"].is_unique


def test_dim_product_deduplicates(sample_raw):
    dim = build_dim_product(sample_raw)
    assert len(dim) == 2   # EL001 and HW003
    assert dim["product_key"].is_unique


# ------------------------------------------------------------------
# fact table FK integrity
# ------------------------------------------------------------------

def test_fact_sales_no_null_fks(sample_raw):
    raw = sample_raw.copy()
    raw["txn_date"] = pd.to_datetime(raw["txn_date"])
    dim_date    = build_dim_date(raw["txn_date"])
    dim_store   = build_dim_store(raw)
    dim_product = build_dim_product(raw)
    fact        = build_fact_sales(raw, dim_date, dim_store, dim_product)

    assert fact["date_key"].isnull().sum()    == 0
    assert fact["store_key"].isnull().sum()   == 0
    assert fact["product_key"].isnull().sum() == 0


def test_fact_sales_row_count_matches_raw(sample_raw):
    raw = sample_raw.copy()
    raw["txn_date"] = pd.to_datetime(raw["txn_date"])
    dim_date    = build_dim_date(raw["txn_date"])
    dim_store   = build_dim_store(raw)
    dim_product = build_dim_product(raw)
    fact        = build_fact_sales(raw, dim_date, dim_store, dim_product)

    assert len(fact) == len(raw)


def test_fact_sales_revenue_sum_preserved(sample_raw):
    raw = sample_raw.copy()
    raw["txn_date"] = pd.to_datetime(raw["txn_date"])
    dim_date    = build_dim_date(raw["txn_date"])
    dim_store   = build_dim_store(raw)
    dim_product = build_dim_product(raw)
    fact        = build_fact_sales(raw, dim_date, dim_store, dim_product)

    assert abs(fact["net_revenue"].sum() - raw["net_revenue"].sum()) < 0.01
