"""KPI logic shared by the Streamlit dashboard (app.py) and the PDF export (build_pdf.py).

KPI definitions (all revenue KPIs count only orders with order_status == 'Completed'):
  Revenue        = SUM(revenue) over completed orders
  Avg Order Val  = Revenue / number of completed orders
  New customers  = customers whose FIRST completed order falls in the period
  CAC            = allocated marketing spend / new customers
  Churn rate     = share of customers active at the start of a month (completed order in the
                   trailing 90 days) who are no longer active at the end of that month
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
CHURN_WINDOW_DAYS = 90

# Region centroids (approximate representative city) for the India bubble map.
REGION_COORDS = {
    "North": (28.61, 77.21),    # Delhi
    "South": (13.08, 80.27),    # Chennai
    "East": (22.57, 88.36),     # Kolkata
    "West": (19.08, 72.88),     # Mumbai
    "Central": (21.15, 79.09),  # Nagpur
}


# ----------------------------------------------------------------------------- loading
def load_orders(path: Path | str | None = None) -> pd.DataFrame:
    df = pd.read_csv(path or DATA_DIR / "clean_dataset.csv", parse_dates=["order_date"])
    # Exclude the 24 rows flagged as cleaning artifacts in the EDA task (margin < -100%).
    df = df[df["profit_margin_pct"] >= -100].copy()
    df["is_completed"] = df["order_status"].eq("Completed")
    df["month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df["year"] = df["order_date"].dt.year.astype(str)
    df["quarter"] = df["order_date"].dt.year.astype(str) + " Q" + df["order_date"].dt.quarter.astype(str)
    # Flag each customer's first completed order globally, so slicers never change who is "new".
    comp = df[df["is_completed"]].sort_values(["order_date", "transaction_id"])
    first_idx = comp.drop_duplicates("customer_id", keep="first").index
    df["is_new_customer_order"] = df.index.isin(first_idx)
    return df.reset_index(drop=True)


def load_spend(path: Path | str | None = None) -> pd.Series:
    s = pd.read_csv(path or DATA_DIR / "marketing_spend_monthly.csv", parse_dates=["month"])
    return s.set_index("month")["marketing_spend_inr"]


def last_complete_month(df: pd.DataFrame) -> pd.Timestamp:
    """Latest month whose data runs to month-end (the newest month is usually partial)."""
    end = df["order_date"].max()
    latest = end.to_period("M").to_timestamp()
    return latest if end == (latest + pd.offsets.MonthEnd(0)) else latest - pd.offsets.MonthBegin(1)


# ----------------------------------------------------------------------------- monthly table
def monthly_kpis(df_seg: pd.DataFrame, df_all: pd.DataFrame, spend: pd.Series,
                 spend_scale: float = 1.0) -> pd.DataFrame:
    """One row per month for the (already segment-filtered) orders in df_seg."""
    months = pd.date_range(df_all["month"].min(), df_all["month"].max(), freq="MS")
    comp = df_seg[df_seg["is_completed"]]

    M = pd.DataFrame(index=months)
    M["revenue"] = comp.groupby("month")["revenue"].sum()
    M["orders"] = comp.groupby("month")["transaction_id"].nunique()
    M["new_customers"] = comp[comp["is_new_customer_order"]].groupby("month").size()
    M = M.fillna(0.0)

    # Spend is company-wide; a filtered segment is allocated spend in proportion to its share
    # of that month's total completed revenue.
    total_rev = df_all[df_all["is_completed"]].groupby("month")["revenue"].sum().reindex(months)
    share = (M["revenue"] / total_rev.replace(0, np.nan)).fillna(0.0)
    M["marketing_spend"] = spend.reindex(months).fillna(0.0) * spend_scale * share

    # Churn on a rolling 90-day active base.
    comp_sorted = comp.sort_values("order_date")
    dates = comp_sorted["order_date"].to_numpy()
    codes = pd.factorize(comp_sorted["customer_id"])[0]
    window = np.timedelta64(CHURN_WINDOW_DAYS, "D")
    data_start = np.datetime64(df_all["order_date"].min())

    def active(day: np.datetime64) -> np.ndarray:
        lo = np.searchsorted(dates, day - window, side="right")
        hi = np.searchsorted(dates, day, side="right")
        return np.unique(codes[lo:hi])

    base, churned = [], []
    for m in months:
        d0 = np.datetime64(m - pd.Timedelta(days=1))
        d1 = np.datetime64(m + pd.offsets.MonthEnd(0))
        if d0 - window < data_start:          # warm-up: base window not fully observable yet
            base.append(np.nan)
            churned.append(np.nan)
            continue
        a0, a1 = active(d0), active(d1)
        base.append(len(a0))
        churned.append(len(np.setdiff1d(a0, a1)))
    M["churn_base"] = base
    M["churned"] = churned
    return finish(M)


def finish(M: pd.DataFrame) -> pd.DataFrame:
    """Derive ratio KPIs from additive columns (works on monthly rows or aggregated periods)."""
    M = M.copy()
    M["aov"] = M["revenue"] / M["orders"].replace(0, np.nan)
    M["cac"] = M["marketing_spend"] / M["new_customers"].replace(0, np.nan)
    M["churn_rate"] = M["churned"] / M["churn_base"].replace(0, np.nan)
    return M


def aggregate(M: pd.DataFrame, level: str) -> pd.DataFrame:
    """Roll monthly rows up to 'Year', 'Quarter' or 'Month' (labels sort chronologically)."""
    if level == "Month":
        out = M.copy()
        out.index = out.index.strftime("%Y-%m")
    else:
        key = M.index.year.astype(str) if level == "Year" else (
            M.index.year.astype(str) + " Q" + M.index.quarter.astype(str))
        out = M.groupby(key)[["revenue", "orders", "new_customers", "marketing_spend"]].sum()
        out[["churn_base", "churned"]] = M.groupby(key)[["churn_base", "churned"]].sum(min_count=1)
        # Flag periods with fewer months than a full quarter/year so partial totals aren't misread.
        expected = 12 if level == "Year" else 3
        counts = M.groupby(key).size()
        out.index = [f"{lab} ({c} mo)" if c < expected else lab for lab, c in counts.items()]
    return finish(out[["revenue", "orders", "new_customers", "marketing_spend", "churn_base", "churned"]])


def summarize(M: pd.DataFrame) -> dict:
    """Headline KPIs for a block of months."""
    rev, orders = M["revenue"].sum(), M["orders"].sum()
    new, spend = M["new_customers"].sum(), M["marketing_spend"].sum()
    base = M["churn_base"].sum(min_count=1)
    return {
        "revenue": rev,
        "orders": orders,
        "aov": rev / orders if orders else np.nan,
        "new_customers": new,
        "cac": spend / new if new else np.nan,
        "churn": (M["churned"].sum(min_count=1) / base) if base and base > 0 else np.nan,
    }


def previous_window(M: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
    """The equal-length block of months immediately before [start, end], if it exists."""
    n = len(M.loc[start:end])
    i0 = M.index.get_loc(start)
    return M.iloc[i0 - n:i0] if i0 - n >= 0 else None


# ----------------------------------------------------------------------------- breakdowns
def region_table(df_seg_window: pd.DataFrame) -> pd.DataFrame:
    comp = df_seg_window[df_seg_window["is_completed"]]
    t = comp.groupby("region").agg(revenue=("revenue", "sum"), orders=("transaction_id", "nunique"),
                                   new_customers=("is_new_customer_order", "sum"))
    t["aov"] = t["revenue"] / t["orders"]
    t["lat"] = [REGION_COORDS[r][0] for r in t.index]
    t["lon"] = [REGION_COORDS[r][1] for r in t.index]
    return t.reset_index()


def breakdown(df_seg_window: pd.DataFrame, by: str, where: dict | None = None) -> pd.DataFrame:
    comp = df_seg_window[df_seg_window["is_completed"]]
    for k, v in (where or {}).items():
        comp = comp[comp[k] == v]
    t = comp.groupby(by).agg(revenue=("revenue", "sum"), orders=("transaction_id", "nunique"))
    t["aov"] = t["revenue"] / t["orders"]
    t["share"] = t["revenue"] / t["revenue"].sum()
    return t.sort_values("revenue", ascending=False).reset_index()


# ----------------------------------------------------------------------------- formatting
def fmt_inr(x: float) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    return f"₹{x:,.0f}"


def pct_change(cur: float, prev: float) -> float | None:
    if prev is None or np.isnan(prev) or prev == 0 or cur is None or np.isnan(cur):
        return None
    return cur / prev - 1
