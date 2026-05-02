"""
Generate NorthMart POS transaction data (2023–2024).

No external API needed — all data is synthesised with a fixed seed so
results are fully reproducible. Run this once before anything else.

    python data/generate_dataset.py
    python data/generate_dataset.py --out path/to/custom.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

STORES: dict[str, tuple[str, str]] = {
    "S01": ("North York",    "Ontario"),
    "S02": ("Scarborough",   "Ontario"),
    "S03": ("Mississauga",   "Ontario"),
    "S04": ("Brampton",      "Ontario"),
    "S05": ("Markham",       "Ontario"),
    "S06": ("Richmond Hill", "Ontario"),
    "S07": ("Vaughan",       "Ontario"),
    "S08": ("Oakville",      "Ontario"),
    "S09": ("Burlington",    "Ontario"),
    "S10": ("Oshawa",        "Ontario"),
    "S11": ("Ajax",          "Ontario"),
    "S12": ("Pickering",     "Ontario"),
}

CATEGORIES: dict[str, dict] = {
    "Electronics":       {"skus": [f"EL{i:03d}" for i in range(1, 21)], "price_range": (29.99, 899.99), "base_margin": 0.18},
    "Health & Wellness": {"skus": [f"HW{i:03d}" for i in range(1, 16)], "price_range": (4.99, 149.99),  "base_margin": 0.42},
    "Apparel":           {"skus": [f"AP{i:03d}" for i in range(1, 26)], "price_range": (9.99, 199.99),  "base_margin": 0.55},
    "Home & Kitchen":    {"skus": [f"HK{i:03d}" for i in range(1, 21)], "price_range": (5.99, 299.99),  "base_margin": 0.38},
    "Grocery":           {"skus": [f"GR{i:03d}" for i in range(1, 31)], "price_range": (0.99, 29.99),   "base_margin": 0.22},
    "Sports":            {"skus": [f"SP{i:03d}" for i in range(1, 16)], "price_range": (7.99, 349.99),  "base_margin": 0.44},
}

# Month index 0–11
SEASONAL_WEIGHTS: dict[str, list[float]] = {
    "Electronics":       [0.8, 0.7, 0.8, 0.9, 0.9, 0.9, 0.9, 0.9, 1.0, 1.1, 1.6, 2.2],
    "Health & Wellness": [1.3, 1.2, 1.1, 1.0, 1.0, 0.9, 0.9, 0.9, 1.0, 1.1, 1.1, 1.0],
    "Apparel":           [0.8, 0.8, 1.1, 1.2, 1.1, 1.0, 1.0, 1.1, 1.2, 1.1, 1.4, 1.8],
    "Home & Kitchen":    [0.9, 0.9, 1.0, 1.2, 1.3, 1.1, 1.0, 1.0, 1.1, 1.1, 1.3, 1.5],
    "Grocery":           [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.3],
    "Sports":            [0.8, 0.8, 1.1, 1.3, 1.5, 1.4, 1.4, 1.3, 1.1, 0.9, 0.8, 0.9],
}

# YoY adjustments applied in 2024 to simulate real business dynamics:
#   Electronics: excess discounting compresses revenue ~18%
#   Health & Wellness: demand surge but understocked, +31% revenue
YOY_FACTORS_2024: dict[str, dict] = {
    "Electronics":       {"revenue_factor": (0.78, 0.88), "extra_discount": 0.12},
    "Health & Wellness": {"revenue_factor": (1.25, 1.40), "extra_discount": 0.00},
}


def _build_rows(rng: np.random.Generator) -> list[dict]:
    rows: list[dict] = []
    txn_counter = 100_000

    for year in [2023, 2024]:
        for month in range(1, 13):
            days_in_month = pd.Period(f"{year}-{month:02d}").days_in_month

            for store_id, (city, province) in STORES.items():
                for cat, meta in CATEGORIES.items():
                    base_txns = int(rng.integers(180, 420))
                    seasonal = SEASONAL_WEIGHTS[cat][month - 1]
                    store_noise = 1.0 + rng.uniform(-0.15, 0.25)
                    volume = int(base_txns * seasonal * store_noise)

                    yoy_cfg = YOY_FACTORS_2024.get(cat, {}) if year == 2024 else {}
                    if yoy_cfg:
                        lo_f, hi_f = yoy_cfg["revenue_factor"]
                        volume = max(10, int(volume * rng.uniform(lo_f, hi_f)))
                    else:
                        volume = max(10, int(volume * rng.uniform(0.95, 1.08))) if year == 2024 else volume

                    lo_p, hi_p = meta["price_range"]
                    extra_disc = yoy_cfg.get("extra_discount", 0.0)

                    for _ in range(volume):
                        txn_counter += 1
                        day = int(rng.integers(1, days_in_month + 1))
                        unit_price = round(float(rng.uniform(lo_p, hi_p)), 2)
                        qty = int(rng.integers(1, 5))
                        disc_rate = round(
                            float(rng.uniform(0, 0.05) + extra_disc * rng.uniform(0, 1)),
                            3,
                        )
                        disc_rate = min(disc_rate, 0.40)
                        gross = round(unit_price * qty, 2)
                        discount_amt = round(gross * disc_rate, 2)
                        net_revenue = round(gross - discount_amt, 2)
                        margin = round(net_revenue * meta["base_margin"] * (1 - disc_rate * 0.5), 2)

                        rows.append(
                            {
                                "transaction_id":  f"TXN{txn_counter}",
                                "txn_date":        f"{year}-{month:02d}-{day:02d}",
                                "store_id":        store_id,
                                "city":            city,
                                "province":        province,
                                "sku":             rng.choice(meta["skus"]),
                                "category":        cat,
                                "unit_price":      unit_price,
                                "quantity":        qty,
                                "discount_rate":   disc_rate,
                                "gross_revenue":   gross,
                                "discount_amount": discount_amt,
                                "net_revenue":     net_revenue,
                                "margin":          margin,
                            }
                        )
    return rows


def generate(out_path: Path, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = _build_rows(rng)
    df = pd.DataFrame(rows)
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"wrote {len(df):,} rows → {out_path}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/northmart_pos_raw.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(Path(args.out), seed=args.seed)


if __name__ == "__main__":
    main()
