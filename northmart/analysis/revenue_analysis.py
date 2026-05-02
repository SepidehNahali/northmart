"""
analysis/revenue_analysis.py

Runs the four SQL analytical queries against the local SQLite database
and writes outputs to analysis/outputs/:

    revenue_decomposition.csv
    store_pl.csv
    discount_leakage.csv
    seasonality.csv
    revenue_decomposition.png   (waterfall chart)
    discount_scatter.png        (discount depth vs margin rate)

    python analysis/revenue_analysis.py
    python analysis/revenue_analysis.py --db path/to/northmart.db
"""

import argparse
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from sqlalchemy import create_engine

warnings.filterwarnings("ignore")

OUT_DIR = Path("analysis/outputs")

QUERIES: dict[str, str] = {
    "revenue_decomposition": Path("sql/01_revenue_decomposition.sql").read_text(),
    "store_pl":              Path("sql/02_store_pl.sql").read_text(),
    "discount_leakage":      Path("sql/03_discount_leakage.sql").read_text(),
    "seasonality":           Path("sql/04_seasonality.sql").read_text(),
}


def run_queries(engine) -> dict[str, pd.DataFrame]:
    results = {}
    for name, sql in QUERIES.items():
        results[name] = pd.read_sql(sql, engine)
        print(f"  {name}: {len(results[name])} rows")
    return results


def plot_revenue_waterfall(df: pd.DataFrame, out: Path) -> None:
    df = df.sort_values("revenue_delta")
    categories = df["category"].tolist()
    deltas = df["revenue_delta"].tolist()

    colors = ["#c0392b" if d < 0 else "#27ae60" for d in deltas]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(categories, deltas, color=colors, height=0.55, edgecolor="none")

    ax.axvline(0, color="#555", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Revenue delta ($)", fontsize=11)
    ax.set_title("YoY Revenue Change by Category  (2024 vs 2023)", fontsize=13, fontweight="bold", pad=12)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x/1e6:.1f}M"))

    for bar, val in zip(bars, deltas):
        label = f"${val/1e6:+.1f}M"
        x_pos = val + (max(abs(d) for d in deltas) * 0.02) * (1 if val >= 0 else -1)
        ha = "left" if val >= 0 else "right"
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                label, va="center", ha=ha, fontsize=9, color="#333")

    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(left=False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  chart → {out}")


def plot_discount_scatter(df: pd.DataFrame, out: Path) -> None:
    df2024 = df[df["year"] == 2024].copy()
    df2024["disc_pct"] = df2024["disc_pct_of_gross"]
    df2024["margin_rate"] = df2024["margin_rate_pct"]

    fig, ax = plt.subplots(figsize=(9, 5))
    cats = df2024["category"].unique()
    palette = ["#2980b9", "#e74c3c", "#27ae60", "#f39c12", "#8e44ad", "#16a085"]
    c_map = dict(zip(cats, palette))

    for cat in cats:
        sub = df2024[df2024["category"] == cat]
        agg = sub.groupby("discount_bucket").agg(
            disc=("disc_pct", "mean"),
            margin=("margin_rate", "mean"),
            volume=("net_revenue", "sum"),
        ).reset_index()
        sizes = (agg["volume"] / agg["volume"].max()) * 300 + 40
        ax.scatter(agg["disc"], agg["margin"], s=sizes,
                   color=c_map[cat], alpha=0.75, label=cat, edgecolors="none")

    ax.set_xlabel("Avg discount depth (% of gross)", fontsize=11)
    ax.set_ylabel("Margin rate (%)", fontsize=11)
    ax.set_title("Discount depth vs margin rate by category  (2024)", fontsize=13, fontweight="bold", pad=12)
    ax.legend(fontsize=9, framealpha=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  chart → {out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="northmart.db")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{args.db}")

    print("running queries…")
    results = run_queries(engine)

    print("writing CSVs…")
    for name, df in results.items():
        path = OUT_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"  {path}")

    print("building charts…")
    plot_revenue_waterfall(
        results["revenue_decomposition"],
        OUT_DIR / "revenue_decomposition.png",
    )
    plot_discount_scatter(
        results["discount_leakage"],
        OUT_DIR / "discount_scatter.png",
    )
    print("done.")


if __name__ == "__main__":
    main()
