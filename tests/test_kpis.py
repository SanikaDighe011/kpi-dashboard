"""Sanity tests for the KPI logic. Run: pytest -q"""
import numpy as np
import pandas as pd
import pytest

import kpi_logic as k


@pytest.fixture(scope="module")
def data():
    df, spend = k.load_orders(), k.load_spend()
    return df, spend, k.monthly_kpis(df, df, spend)


def test_revenue_matches_direct_calculation(data):
    df, _, M = data
    assert M["revenue"].sum() == pytest.approx(df.loc[df["is_completed"], "revenue"].sum())


def test_segments_add_up_to_total(data):
    df, spend, M = data
    parts = sum(k.monthly_kpis(df[df["region"] == r], df, spend)["revenue"].sum() for r in df["region"].unique())
    assert parts == pytest.approx(M["revenue"].sum())


def test_every_customer_is_new_exactly_once(data):
    df, _, _ = data
    comp = df[df["is_completed"]]
    assert comp["is_new_customer_order"].sum() == comp["customer_id"].nunique()


def test_churn_is_a_valid_rate_and_warmup_is_blank(data):
    _, _, M = data
    assert M["churn_rate"].dropna().between(0, 1).all()
    assert M["churn_rate"].iloc[:3].isna().all()          # first 3 months cannot be measured


def test_spend_allocation_never_exceeds_budget(data):
    df, spend, _ = data
    parts = sum(k.monthly_kpis(df[df["region"] == r], df, spend)["marketing_spend"].sum() for r in df["region"].unique())
    assert parts == pytest.approx(spend.reindex(pd.date_range(df["month"].min(), df["month"].max(), freq="MS")).sum())


def test_partial_periods_are_labelled(data):
    _, _, M = data
    labels = k.aggregate(M.loc[:"2026-08-01"], "Quarter").index
    assert any("(2 mo)" in lab for lab in labels)


def test_last_complete_month_excludes_partial_september(data):
    df, _, _ = data
    assert k.last_complete_month(df) == pd.Timestamp("2026-08-01")
