# Interactive Dashboard & KPI Visualizations — E-Commerce

An interactive executive dashboard (Streamlit + Plotly) built on the cleaned e-commerce
transactions from the earlier cleaning and EDA tasks.

**Live app:** _paste your Streamlit Community Cloud URL here after deploying_
**Static export:** [`docs/Dashboard_Export.pdf`](docs/Dashboard_Export.pdf)

## Executive KPIs

| KPI | Definition |
|---|---|
| **Revenue** | Σ quantity × unit price × (1 − discount) on **Completed** orders |
| **Average Order Value** | Revenue ÷ completed orders |
| **Customer Acquisition Cost (CAC)** | Allocated marketing spend ÷ new customers (a customer's first completed order) |
| **Churn rate** | Of customers active at the start of a month (completed order in the trailing 90 days), the share with no completed order in the trailing 90 days by month-end |

Each card shows the change versus the equal-length period immediately before the selected one.

## Requirements → where implemented

| Requirement | Implementation |
|---|---|
| Executive KPIs | Four KPI cards with period-over-period deltas |
| Dashboard cards | `st.metric` cards in bordered containers |
| Trendline area chart | Area chart with linear trendline; switchable metric (Revenue, AOV, Orders, New customers) and granularity (Year / Quarter / Month) |
| Geographic heatmap | India bubble map by region, colour and size by Revenue or AOV |
| Slicers | Sidebar: period range, region, product category, payment method, marketing-spend scale |
| Temporal drill-down | Year → Quarter selectors re-scope the trend chart |
| Categorical drill-down | Category → product breakdown |
| Visual hierarchy | Top-down: headline KPIs → trend → geography and categories → diagnostics → detail tables and definitions |

## Repo layout

```
app.py                       Streamlit dashboard
kpi_logic.py                 KPI computation shared by the app and the PDF
build_pdf.py                 Generates docs/Dashboard_Export.pdf
generate_marketing_spend.py  Generates the illustrative spend input
data/clean_dataset.csv       Cleaned orders (from the data-cleaning task)
data/marketing_spend_monthly.csv   Illustrative marketing spend (see limitations)
tests/test_kpis.py           Automated KPI sanity tests
docs/Dashboard_Export.pdf    Static two-page export
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py          # dashboard
python build_pdf.py           # regenerate the PDF
pytest -q                     # run the KPI tests
```

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to <https://share.streamlit.io>, sign in with GitHub, click **Create app**.
3. Choose this repository, branch `main`, main file path `app.py`, then **Deploy**.
4. Copy the resulting `https://….streamlit.app` URL into the line at the top of this README.

## Data notes and limitations

- **CAC uses illustrative spend.** The orders data contains no marketing costs, so
  `data/marketing_spend_monthly.csv` is an assumption (about ₹150k a month with mild seasonality).
  The dashboard flags this and lets you flex it with a slider. Replace the file with finance data to
  make CAC a true KPI. Under filters, spend is allocated to a segment in proportion to its share of
  that month's revenue.
- **CAC rises over time mainly as a data artifact.** The dataset draws from a finite pool of about
  3,000 customer IDs, so first-time customers fall from about 140 a month to about 30. Treat the
  trend as a property of this data, not a business finding.
- **Geography is region-level.** The data holds 5 regions (North, South, East, West, Central), not
  cities or states, so bubbles sit on a representative city per region.
- **Churn** cannot be computed for the first 3 months of data (the 90-day window is not yet
  observable), and is shown as n/a there.
- **The latest month (Sep 2026) is partial** (data ends 20 Sep) and is excluded by default;
  a checkbox includes it. Partial quarters and years are labelled, e.g. `2026 Q3 (2 mo)`.
- 24 rows flagged as cleaning artifacts in the EDA task (margin below −100%) are excluded.
