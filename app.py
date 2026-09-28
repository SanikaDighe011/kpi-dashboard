"""Executive KPI dashboard (Streamlit + Plotly).

Run locally:  streamlit run app.py
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import kpi_logic as k

st.set_page_config(page_title="E-Commerce Executive Dashboard", page_icon="📊", layout="wide")

BLUE, TEAL, ORANGE, GREY = "#1F4E78", "#2A9D8F", "#E76F51", "#8A94A6"


def show(fig: go.Figure, key: str) -> None:
    """Render a Plotly chart full-width (compatible across Streamlit versions)."""
    try:
        st.plotly_chart(fig, width="stretch", key=f"chart_{key}")
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{key}")


def style(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), font=dict(size=12),
                      title_font=dict(size=15), plot_bgcolor="white", legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#EEF0F4")
    return fig


@st.cache_data
def get_data():
    return k.load_orders(), k.load_spend()


@st.cache_data
def get_monthly(regions, categories, payments, scale):
    df, spend = get_data()
    seg = df[df["region"].isin(regions) & df["product_category"].isin(categories)
             & df["payment_method"].isin(payments)]
    return k.monthly_kpis(seg, df, spend, scale)


df, spend = get_data()
all_months = list(pd.date_range(df["month"].min(), df["month"].max(), freq="MS"))
default_end = k.last_complete_month(df)

# ------------------------------------------------------------------ sidebar slicers
with st.sidebar:
    st.header("Filters")
    include_partial = st.checkbox("Include partial latest month", value=False,
                                  help=f"Data ends {df['order_date'].max():%d %b %Y}, so the newest month is incomplete.")
    options = all_months if include_partial else [m for m in all_months if m <= default_end]
    start, end = st.select_slider("Period", options=options, value=(options[0], options[-1]),
                                  format_func=lambda m: m.strftime("%b %Y"))
    regions = st.multiselect("Region", sorted(df["region"].unique()), default=sorted(df["region"].unique()))
    categories = st.multiselect("Product category", sorted(df["product_category"].unique()),
                                default=sorted(df["product_category"].unique()))
    payments = st.multiselect("Payment method", sorted(df["payment_method"].unique()),
                              default=sorted(df["payment_method"].unique()))
    st.divider()
    scale = st.slider("Marketing spend scale (%)", 50, 150, 100, step=10,
                      help="Flexes the illustrative marketing-spend assumption behind CAC.") / 100
    st.warning("**CAC uses illustrative spend.** The orders data has no marketing costs; "
               "spend comes from `data/marketing_spend_monthly.csv`. Replace it with finance data.")

if not (regions and categories and payments):
    st.warning("Select at least one value in every filter.")
    st.stop()

M = get_monthly(tuple(regions), tuple(categories), tuple(payments), scale)
M_sel = M.loc[start:end]
seg_window = df[df["region"].isin(regions) & df["product_category"].isin(categories)
                & df["payment_method"].isin(payments) & (df["month"] >= start) & (df["month"] <= end)]

# ------------------------------------------------------------------ title
st.title("E-Commerce Executive Dashboard")
st.caption(f"{start:%b %Y} – {end:%b %Y} · {len(M_sel)} months · completed orders only · "
           f"{len(regions)} region(s), {len(categories)} categor{'y' if len(categories) == 1 else 'ies'}, "
           f"{len(payments)} payment method(s)")

# ------------------------------------------------------------------ KPI cards (level 1 of hierarchy)
cur = k.summarize(M_sel)
prev_block = k.previous_window(M, start, end)
prev = k.summarize(prev_block) if prev_block is not None else None


def rel(key):
    if prev is None:
        return None
    c = k.pct_change(cur[key], prev[key])
    return None if c is None else f"{c:+.1%} vs prior period"


churn_delta = None
if prev is not None and not (np.isnan(cur["churn"]) or np.isnan(prev["churn"])):
    churn_delta = f"{(cur['churn'] - prev['churn']) * 100:+.1f} pp vs prior period"

c1, c2, c3, c4 = st.columns(4)
with c1.container(border=True):
    st.metric("Revenue", k.fmt_inr(cur["revenue"]), rel("revenue"))
with c2.container(border=True):
    st.metric("Average Order Value", k.fmt_inr(cur["aov"]), rel("aov"))
with c3.container(border=True):
    st.metric("Customer Acquisition Cost*", k.fmt_inr(cur["cac"]), rel("cac"), delta_color="inverse")
with c4.container(border=True):
    st.metric("Monthly Churn Rate", "n/a" if np.isnan(cur["churn"]) else f"{cur['churn']:.1%}",
              churn_delta, delta_color="inverse")
st.caption(f"{int(cur['orders']):,} completed orders · {int(cur['new_customers']):,} new customers · "
           "*CAC based on illustrative marketing spend · "
           "churn = customers active in the trailing 90 days who lapse within the month "
           "(not computable for the first 3 months of data)")

# ------------------------------------------------------------------ trend with temporal drill-down
st.subheader("Trend")
t1, t2, t3, t4 = st.columns([1.1, 1.1, 1.1, 1.3])
metric_label = t1.selectbox("Metric", ["Revenue", "Average Order Value", "Orders", "New customers"])
level = t2.radio("Granularity", ["Year", "Quarter", "Month"], index=2, horizontal=True)
years = sorted({d.year for d in M_sel.index})
drill_year = t3.selectbox("Drill into year", ["All years"] + [str(y) for y in years])
M_trend = M_sel
drill_label = "All years"
if drill_year != "All years":
    M_trend = M_sel[M_sel.index.year == int(drill_year)]
    drill_label = drill_year
    quarters = sorted({f"Q{d.quarter}" for d in M_trend.index})
    drill_q = t4.selectbox("Drill into quarter", ["All quarters"] + quarters)
    if drill_q != "All quarters":
        M_trend = M_trend[M_trend.index.quarter == int(drill_q[1])]
        drill_label = f"{drill_year} {drill_q}"

col_map = {"Revenue": "revenue", "Average Order Value": "aov", "Orders": "orders", "New customers": "new_customers"}
A = k.aggregate(M_trend, level)
y = A[col_map[metric_label]]
fig = go.Figure()
fig.add_trace(go.Scatter(x=A.index, y=y, mode="lines+markers", fill="tozeroy", name=metric_label,
                         line=dict(color=BLUE, width=2.5), fillcolor="rgba(31,78,120,0.18)"))
if len(A) >= 3:
    slope, intercept = np.polyfit(np.arange(len(A)), y.fillna(0).to_numpy(dtype=float), 1)
    fig.add_trace(go.Scatter(x=A.index, y=intercept + slope * np.arange(len(A)), mode="lines", name="Linear trend",
                             line=dict(color=ORANGE, width=2, dash="dot")))
fig.update_layout(title=f"{metric_label} by {level.lower()} · {drill_label}")
show(style(fig, 360), "trend")

# ------------------------------------------------------------------ geography + category drill-down
left, right = st.columns([1.15, 1])
with left:
    st.subheader("Geography")
    R = k.region_table(seg_window)
    geo_metric = st.radio("Colour / size by", ["Revenue", "Average Order Value"], horizontal=True, key="geo")
    gcol = "revenue" if geo_metric == "Revenue" else "aov"
    gfig = px.scatter_geo(R, lat="lat", lon="lon", size="revenue", color=gcol, hover_name="region",
                          hover_data={"revenue": ":,.0f", "aov": ":,.0f", "orders": True, "lat": False, "lon": False},
                          text="region", color_continuous_scale="YlOrRd", size_max=55)
    gfig.update_traces(textposition="top center")
    gfig.update_geos(scope="asia", center=dict(lat=22, lon=79), projection_scale=4.3, showcountries=True,
                     countrycolor="#B8C0CC", showland=True, landcolor="#F4F6F9", showocean=True, oceancolor="#EAF3FB")
    gfig.update_layout(coloraxis_colorbar=dict(title=geo_metric, thickness=12))
    show(style(gfig, 380), "geo")
    st.caption("Region-level view: the dataset holds 5 regions, not city or state coordinates. "
               "Bubbles sit on a representative city per region.")

with right:
    st.subheader("Category drill-down")
    cat_rows = k.breakdown(seg_window, "product_category")
    pick = st.selectbox("Drill into category", ["All categories"] + cat_rows["product_category"].tolist())
    if pick == "All categories":
        B = cat_rows.sort_values("revenue")
        bfig = px.bar(B, x="revenue", y="product_category", orientation="h", text=B["share"].map("{:.0%}".format),
                      color_discrete_sequence=[BLUE])
        bfig.update_layout(title="Revenue by category", yaxis_title=None, xaxis_title=None)
    else:
        B = k.breakdown(seg_window, "product_name", {"product_category": pick}).sort_values("revenue")
        bfig = px.bar(B, x="revenue", y="product_name", orientation="h", text=B["share"].map("{:.0%}".format),
                      color_discrete_sequence=[TEAL])
        bfig.update_layout(title=f"Revenue by product · {pick}", yaxis_title=None, xaxis_title=None)
    bfig.update_traces(textposition="outside", cliponaxis=False)
    show(style(bfig, 380), "cat")

# ------------------------------------------------------------------ CAC and churn diagnostics
st.subheader("Acquisition & retention diagnostics")
d1, d2 = st.columns(2)
cfig = go.Figure(go.Scatter(x=M_sel.index, y=M_sel["cac"], mode="lines+markers", line=dict(color=ORANGE, width=2.5)))
cfig.update_layout(title="Customer Acquisition Cost by month (illustrative spend)", yaxis_title="₹ per new customer")
with d1:
    show(style(cfig, 300), "cac")
    st.caption("CAC rises over time mainly because new-customer volume falls as the dataset's finite customer "
               "pool is exhausted, so treat the trend as a data property rather than a business finding.")
chfig = go.Figure(go.Scatter(x=M_sel.index, y=M_sel["churn_rate"], mode="lines+markers", line=dict(color=TEAL, width=2.5)))
chfig.update_layout(title="Monthly churn rate", yaxis_tickformat=".0%")
with d2:
    show(style(chfig, 300), "churn")
    st.caption("Share of customers active in the trailing 90 days who have lapsed by month-end.")

# ------------------------------------------------------------------ detail + method
with st.expander("Monthly KPI table"):
    T = M_sel[["revenue", "orders", "aov", "new_customers", "marketing_spend", "cac", "churn_rate"]].copy()
    T.index = T.index.strftime("%Y-%m")
    try:
        st.dataframe(T.round(3), width="stretch")
    except (TypeError, ValueError):
        st.dataframe(T.round(3), use_container_width=True)
    st.download_button("Download CSV", T.round(3).to_csv().encode(), "monthly_kpis.csv", "text/csv")

with st.expander("KPI definitions & assumptions"):
    st.markdown(
        "- **Revenue:** sum of `quantity × unit_price × (1 − discount)` over orders with status *Completed*.\n"
        "- **Average Order Value:** revenue ÷ completed orders.\n"
        "- **CAC:** allocated marketing spend ÷ new customers (a customer's first completed order). "
        "Spend is illustrative and, under filters, allocated by each segment's share of monthly revenue.\n"
        "- **Churn rate:** customers with a completed order in the trailing 90 days at the start of a month "
        "who have none in the trailing 90 days at month-end, ÷ that starting base.\n"
        "- **Deltas:** compare the selected period with the equal-length period immediately before it.\n"
        "- 24 rows flagged as cleaning artifacts (margin below −100%) are excluded, as in the EDA notebook.")
