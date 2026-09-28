"""Generate the ILLUSTRATIVE monthly marketing-spend input used for the CAC KPI.

The source orders dataset contains no marketing cost data, so Customer Acquisition Cost
cannot be computed from it alone. This script produces a clearly-labelled assumption
(a ~INR 150k/month budget with mild seasonality and noise). Replace data/marketing_spend_monthly.csv
with real finance data to make CAC a real KPI.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
months = pd.date_range("2024-01-01", "2026-09-01", freq="MS")
seasonal = {11: 1.15, 12: 1.15, 1: 0.95, 2: 0.95}
spend = [round(150_000 * seasonal.get(m.month, 1.0) * rng.uniform(0.93, 1.07), -2) for m in months]
pd.DataFrame({"month": months.strftime("%Y-%m-%d"), "marketing_spend_inr": spend}).to_csv(
    "data/marketing_spend_monthly.csv", index=False)
print(f"wrote {len(months)} months")
