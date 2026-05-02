"""
anomaly/detect_anomalies.py

Flags unusual store-day revenue patterns using Isolation Forest.
Each observation is one (store, day) pair with features:
    net_revenue, txn_count, avg_basket_value, avg_discount_rate

Anomalies are written to anomaly/outputs/anomaly_watchlist.csv
and to the `anomaly_watchlist` table in the database — which the
Power BI "watch list" tile reads via DirectQuery.

    python anomaly/detect_anomalies.py
    python anomaly/detect_anomalies.py --db northmart.db --contamination 0.03
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

FEATURE_COLS = ["net_revenue", "txn_count", "avg_basket", "avg_discount_rate"]

AGG_QUERY = """
SELECT
    s.store_id,
    s.city,
    d.full_date,
    d.year,
    d.month,
    d.day_of_week,
    d.is_weekend,
    COUNT(DISTINCT f.transaction_id)              AS txn_count,
    ROUND(SUM(f.net_revenue), 2)                  AS net_revenue,
    ROUND(AVG(f.net_revenue), 2)                  AS avg_basket,
    ROUND(AVG(f.discount_rate), 4)                AS avg_discount_rate,
    ROUND(SUM(f.margin), 2)                       AS total_margin
FROM fact_sales f
JOIN dim_store s ON f.store_key = s.store_key
JOIN dim_date  d ON f.date_key  = d.date_key
GROUP BY s.store_id, s.city, d.full_date, d.year, d.month, d.day_of_week, d.is_weekend
"""


def add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["store_id", "full_date"])
    for col in ["net_revenue", "txn_count"]:
        df[f"{col}_roll7"] = (
            df.groupby("store_id")[col]
            .transform(lambda x: x.rolling(7, min_periods=3).mean())
        )
        df[f"{col}_deviation"] = df[col] - df[f"{col}_roll7"]
    return df


def train_and_score(df: pd.DataFrame, contamination: float) -> pd.DataFrame:
    features = df[FEATURE_COLS].copy()

    # a small number of rows may have NaN rolling features — drop them for fitting
    mask = features.notna().all(axis=1)
    X = features[mask]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    iso = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    iso.fit(X_scaled)

    scores = pd.Series(index=df.index, dtype=float)
    preds  = pd.Series(index=df.index, dtype=int)
    scores[mask] = iso.decision_function(X_scaled)
    preds[mask]  = iso.predict(X_scaled)

    df = df.copy()
    df["anomaly_score"] = scores.round(4)
    # IsolationForest returns -1 for anomalies, +1 for inliers
    df["is_anomaly"] = (preds == -1).astype(int)
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",            default="northmart.db")
    parser.add_argument("--contamination", type=float, default=0.03,
                        help="expected fraction of anomalies (default 0.03)")
    args = parser.parse_args()

    engine = create_engine(f"sqlite:///{args.db}")

    log.info("aggregating store-day features")
    daily = pd.read_sql(AGG_QUERY, engine, parse_dates=["full_date"])
    log.info("%d store-day observations", len(daily))

    daily = add_rolling_features(daily)

    log.info("fitting Isolation Forest  (contamination=%.2f)", args.contamination)
    daily = train_and_score(daily, args.contamination)

    anomalies = daily[daily["is_anomaly"] == 1].sort_values("anomaly_score")
    log.info("%d anomalous store-days flagged", len(anomalies))

    out_dir = Path("anomaly/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    anomalies.to_csv(out_dir / "anomaly_watchlist.csv", index=False)
    log.info("wrote anomaly_watchlist.csv")

    # write back to DB for Power BI DirectQuery
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS anomaly_watchlist"))
    anomalies.to_sql("anomaly_watchlist", engine, if_exists="replace", index=False)
    log.info("wrote anomaly_watchlist table to %s", args.db)

    # summary
    print("\nTop 10 most anomalous store-days:")
    cols = ["full_date", "store_id", "city", "net_revenue", "txn_count", "avg_discount_rate", "anomaly_score"]
    print(anomalies[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
