"""Build docs/Dashboard_Export.pdf - a static, two-page export of the dashboard.

Uses the same kpi_logic module as the Streamlit app, so every number matches the live dashboard
(reporting window = last 12 complete months vs the 12 months before, all filters at 'All').
Run:  python build_pdf.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

import kpi_logic as k

BLUE, TEAL, ORANGE, GREY, GREEN, RED = "#1F4E78", "#2A9D8F", "#E76F51", "#8A94A6", "#2E8B57", "#C0392B"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#B8C0CC", "axes.titleweight": "bold", "axes.titlesize": 10})

df, spend = k.load_orders(), k.load_spend()
M = k.monthly_kpis(df, df, spend)
END = k.last_complete_month(df)
START = END - pd.DateOffset(months=11)
M = M.loc[:END]
cur_block, prev_block = M.loc[START:END], k.previous_window(M, START, END)
cur, prev = k.summarize(cur_block), k.summarize(prev_block)
window_df = df[(df["month"] >= START) & (df["month"] <= END)]


def card(fig, rect, title, value, delta_txt, good):
    ax = fig.add_axes(rect)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.06", fc="white",
                                ec="#D5DAE3", lw=1, transform=ax.transAxes))
    ax.add_patch(FancyBboxPatch((0, 0), 0.025, 1, boxstyle="square,pad=0", fc=BLUE, ec="none", transform=ax.transAxes))
    ax.text(0.09, 0.78, title, fontsize=9.5, color="#5B6577", transform=ax.transAxes)
    ax.text(0.09, 0.40, value, fontsize=21, fontweight="bold", color="#1B2333", transform=ax.transAxes)
    ax.text(0.09, 0.12, delta_txt, fontsize=8.5, color=GREEN if good else RED, transform=ax.transAxes)


def delta_rel(key, higher_is_better=True):
    c = k.pct_change(cur[key], prev[key])
    up = c >= 0
    return f"{'▲' if up else '▼'} {abs(c):.1%} vs prior 12 mo", (up == higher_is_better)


def money_axis(ax):
    ax.yaxis.set_major_formatter(lambda v, _: f"{v / 1e5:.0f}L" if v >= 1e5 else f"{v:,.0f}")


# =========================================================================== PAGE 1
fig1 = plt.figure(figsize=(11.69, 8.27))
fig1.text(0.05, 0.945, "E-Commerce Executive Dashboard", fontsize=20, fontweight="bold", color=BLUE)
fig1.text(0.05, 0.915, f"Reporting window {START:%b %Y} – {END:%b %Y} (last 12 complete months) · completed orders only · "
                       "all regions, categories and payment methods", fontsize=8.8, color="#5B6577")

churn_txt = f"{'▲' if cur['churn'] >= prev['churn'] else '▼'} {abs(cur['churn'] - prev['churn']) * 100:.1f} pp vs prior 12 mo"
t, g = delta_rel("revenue"); card(fig1, [0.05, 0.775, 0.215, 0.115], "Revenue", k.fmt_inr(cur["revenue"]), t, g)
t, g = delta_rel("aov"); card(fig1, [0.285, 0.775, 0.215, 0.115], "Average Order Value", k.fmt_inr(cur["aov"]), t, g)
t, g = delta_rel("cac", False); card(fig1, [0.52, 0.775, 0.215, 0.115], "Customer Acquisition Cost*", k.fmt_inr(cur["cac"]), t, g)
card(fig1, [0.755, 0.775, 0.195, 0.115], "Monthly Churn Rate", f"{cur['churn']:.1%}", churn_txt, cur["churn"] <= prev["churn"])

# --- revenue area chart with trendline
ax = fig1.add_axes([0.06, 0.435, 0.53, 0.28])
x = np.arange(len(M))
ax.fill_between(x, M["revenue"], color=BLUE, alpha=0.18)
ax.plot(x, M["revenue"], color=BLUE, lw=2, marker="o", ms=3, label="Monthly revenue")
slope, icpt = np.polyfit(x, M["revenue"].to_numpy(dtype=float), 1)
ax.plot(x, icpt + slope * x, color=ORANGE, lw=1.8, ls=":", label="Linear trend")
i0 = M.index.get_loc(START)
ax.axvspan(i0 - 0.5, len(M) - 0.5, color="#F1F5FA", zorder=0)
ax.text(i0 + 0.3, ax.get_ylim()[1] * 0.02 + M["revenue"].min() * 0.05, "reporting window", fontsize=7.5, color=GREY)
ax.set_xticks(x[::3]); ax.set_xticklabels(M.index.strftime("%b %y")[::3], fontsize=7.5)
ax.set_ylim(0, M["revenue"].max() * 1.15); money_axis(ax); ax.tick_params(axis="y", labelsize=7.5)
ax.set_title("Monthly revenue with linear trend (₹, L = lakh)", loc="left"); ax.legend(fontsize=7.5, frameon=False, loc="lower left", ncol=2)
ax.grid(axis="y", color="#EEF0F4")

# --- region tile map (geographic heat, schematic layout: N top, W left, C middle, E right, S bottom)
R = k.region_table(window_df).set_index("region")
axm = fig1.add_axes([0.63, 0.435, 0.33, 0.28]); axm.axis("off"); axm.set_xlim(0, 3); axm.set_ylim(0, 3)
axm.set_title("Revenue by region (heat tiles, schematic layout)", loc="left")
pos = {"North": (1, 2), "West": (0, 1), "Central": (1, 1), "East": (2, 1), "South": (1, 0)}
cmap = plt.get_cmap("YlOrRd"); lo, hi = R["revenue"].min(), R["revenue"].max()
for reg, (cx, cy) in pos.items():
    v = R.loc[reg, "revenue"]; shade = 0.12 + 0.5 * (v - lo) / (hi - lo) if hi > lo else 0.4
    axm.add_patch(FancyBboxPatch((cx + 0.05, cy + 0.05), 0.9, 0.9, boxstyle="round,pad=0,rounding_size=0.08",
                                 fc=cmap(shade), ec="white", lw=2))
    axm.text(cx + 0.5, cy + 0.62, reg, ha="center", fontsize=9, fontweight="bold", color="#1B2333")
    axm.text(cx + 0.5, cy + 0.38, k.fmt_inr(v), ha="center", fontsize=8.5, color="#1B2333")
    axm.text(cx + 0.5, cy + 0.20, f"{v / R['revenue'].sum():.0%} of total", ha="center", fontsize=7, color="#3B4557")

# --- bottom row: category bars, CAC, churn
cats = k.breakdown(window_df, "product_category").sort_values("revenue")
axc = fig1.add_axes([0.14, 0.09, 0.19, 0.24])
axc.barh(cats["product_category"], cats["revenue"], color=BLUE)
for i, (v, s) in enumerate(zip(cats["revenue"], cats["share"])):
    axc.text(v, i, f" {s:.0%}", va="center", fontsize=7.5)
axc.set_xlim(0, cats["revenue"].max() * 1.22); axc.set_xticks([]); axc.tick_params(axis="y", labelsize=8)
axc.spines["bottom"].set_visible(False); axc.set_title("Revenue by category", loc="left")

axa = fig1.add_axes([0.42, 0.09, 0.24, 0.24])
axa.plot(np.arange(len(M)), M["cac"], color=ORANGE, lw=2, marker="o", ms=3)
axa.set_xticks(np.arange(len(M))[::6]); axa.set_xticklabels(M.index.strftime("%b %y")[::6], fontsize=7.5)
axa.tick_params(axis="y", labelsize=7.5); axa.grid(axis="y", color="#EEF0F4")
axa.set_title("CAC by month (₹, illustrative spend)", loc="left")

axh = fig1.add_axes([0.73, 0.09, 0.22, 0.24])
axh.plot(np.arange(len(M)), M["churn_rate"], color=TEAL, lw=2, marker="o", ms=3)
axh.set_xticks(np.arange(len(M))[::6]); axh.set_xticklabels(M.index.strftime("%b %y")[::6], fontsize=7.5)
axh.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); axh.tick_params(axis="y", labelsize=7.5)
axh.set_ylim(0.15, 0.45); axh.grid(axis="y", color="#EEF0F4"); axh.set_title("Monthly churn rate", loc="left")

fig1.text(0.05, 0.03, "*CAC uses an illustrative marketing-spend assumption (the source data has no marketing costs). "
                      "CAC trend reflects a shrinking new-customer pool in this dataset. Churn = customers active in the "
                      "trailing 90 days who lapse within the month.", fontsize=7, color="#5B6577", wrap=True)

# =========================================================================== PAGE 2
fig2 = plt.figure(figsize=(11.69, 8.27))
fig2.text(0.05, 0.945, "Drill-down & methodology", fontsize=18, fontweight="bold", color=BLUE)
fig2.text(0.05, 0.915, "Categorical drill-down (category → product) and quarterly KPI history. "
                       "The live Streamlit app adds year → quarter → month drill-down and slicers.", fontsize=8.8, color="#5B6577")

prod = k.breakdown(window_df, ["product_category", "product_name"]).head(10).iloc[::-1]
cat_colors = dict(zip(sorted(df["product_category"].unique()), plt.get_cmap("tab10").colors))
axp = fig2.add_axes([0.25, 0.60, 0.57, 0.27])
axp.barh(prod["product_name"] + "  (" + prod["product_category"] + ")", prod["revenue"],
         color=[cat_colors[c] for c in prod["product_category"]])
axp.tick_params(axis="y", labelsize=8); axp.xaxis.set_major_formatter(lambda v, _: f"{v / 1e5:.0f}L")
axp.tick_params(axis="x", labelsize=7.5); axp.set_title("Top 10 products by revenue, reporting window (₹ lakh)", loc="left")
from matplotlib.patches import Patch
axp.legend(handles=[Patch(color=cat_colors[c], label=c) for c in sorted(prod["product_category"].unique())],
           fontsize=7.5, frameon=False, loc="upper left", bbox_to_anchor=(1.03, 1.0), title="Category", title_fontsize=8)

Q = k.aggregate(M, "Quarter")
cells = [[q, k.fmt_inr(r.revenue), f"{int(r.orders):,}", k.fmt_inr(r.aov), f"{int(r.new_customers):,}", k.fmt_inr(r.cac),
          "n/a" if np.isnan(r.churn_rate) else f"{r.churn_rate:.1%}"] for q, r in Q.iterrows()]
axt = fig2.add_axes([0.05, 0.16, 0.90, 0.38]); axt.axis("off")
axt.set_title("Quarterly KPI history", loc="left")
tbl = axt.table(cellText=cells, colLabels=["Quarter", "Revenue", "Orders", "AOV", "New customers", "CAC*", "Churn"],
                loc="upper center", cellLoc="center")
tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1, 1.25)
for (r, c), cell in tbl.get_celld().items():
    cell.set_edgecolor("#D5DAE3")
    if r == 0:
        cell.set_facecolor(BLUE); cell.set_text_props(color="white", fontweight="bold")
    elif r % 2 == 0:
        cell.set_facecolor("#F4F6F9")

notes = ("Definitions: Revenue = Σ quantity × unit price × (1 − discount) on Completed orders · AOV = revenue ÷ completed orders · "
         "CAC = allocated marketing spend ÷ new customers (first completed order) · Churn = share of customers active in the trailing "
         "90 days at month start with no order in the trailing 90 days at month end.\n"
         "Assumptions & limits: marketing spend is illustrative (data/marketing_spend_monthly.csv); geography is region-level (5 regions); "
         "24 rows with margin below −100% (cleaning artifacts) are excluded; the partial latest month (Sep 2026) is excluded; "
         "churn is not computable for the first 3 months of data (so 2024 Q1 shows n/a); periods with fewer than a full quarter of months are labelled, e.g. 2026 Q3 (2 mo).")
import textwrap
notes = "\n".join(textwrap.fill(par, 185) for par in notes.split("\n"))
fig2.text(0.05, 0.04, notes, fontsize=7.2, color="#3B4557", va="bottom")

with PdfPages("docs/Dashboard_Export.pdf") as pdf:
    pdf.savefig(fig1)
    pdf.savefig(fig2)
    d = pdf.infodict()
    d["Title"] = "E-Commerce Executive Dashboard - Export"
print("wrote docs/Dashboard_Export.pdf")
