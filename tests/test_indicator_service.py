"""
Testes do IndicatorService (Módulo 9). O caso mais importante é a
regressão do "fluxo falso": uma transferência para a própria conta
investimento não pode contar como receita nem despesa.
"""

import pandas as pd
import pytest

from sifp.domain.categories import SELF_TRANSFER_CATEGORY
from sifp.services import indicator_service as ind


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "date": ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"],
            "description": ["Salario", "Mercado", "Uber", "Transferencia p/ investimento", "Uber"],
            "value": [5000.0, -300.0, -20.0, -1000.0, -15.0],
            "category": ["Salário/Receita", "Mercado", "Transporte", SELF_TRANSFER_CATEGORY, "Transporte"],
            "merchant": ["Salario", "Amigao Brasil", "Uber", "Fulano De Tal", "Uber"],
        }
    )


def test_exclude_self_transfers(sample_df):
    result = ind.exclude_self_transfers(sample_df)
    assert SELF_TRANSFER_CATEGORY not in result["category"].values
    assert len(result) == 4


def test_period_summary_excludes_self_transfer_from_flow(sample_df):
    real = ind.exclude_self_transfers(sample_df)
    summary = ind.period_summary(real)

    assert summary["receitas"] == pytest.approx(5000.0)
    assert summary["despesas"] == pytest.approx(335.0)  # 300 + 20 + 15, SEM os 1000 da transferencia interna
    assert summary["saldo"] == pytest.approx(4665.0)
    assert summary["taxa_poupanca"] == pytest.approx(4665.0 / 5000.0 * 100)


def test_period_summary_without_exclusion_would_show_false_flow(sample_df):
    """Prova que a exclusão realmente faz diferença: sem ela, a
    transferência interna infla a despesa (o 'fluxo falso' que motivou o módulo)."""
    summary_with_leak = ind.period_summary(sample_df)
    assert summary_with_leak["despesas"] == pytest.approx(1335.0)  # inclui os 1000 indevidamente


def test_self_transfer_total(sample_df):
    assert ind.self_transfer_total(sample_df) == pytest.approx(1000.0)


def test_category_breakdown_percentages_sum_to_100(sample_df):
    real = ind.exclude_self_transfers(sample_df)
    by_cat = ind.category_breakdown(real)
    assert by_cat["pct"].sum() == pytest.approx(100.0)
    # Mercado (-300) é a maior categoria de gasto, mesmo com só 1 lançamento
    assert by_cat.iloc[0]["category"] == "Mercado"
    assert by_cat.iloc[0]["value_abs"] == pytest.approx(300.0)
    transporte = by_cat[by_cat["category"] == "Transporte"].iloc[0]
    assert transporte["value_abs"] == pytest.approx(35.0)  # 2x Uber somados


def test_category_breakdown_empty_when_no_expenses():
    df = pd.DataFrame({"date": ["2026-06-01"], "value": [100.0], "category": ["Salário/Receita"]})
    result = ind.category_breakdown(df)
    assert result.empty


def test_merchant_concentration_groups_by_canonical_name(sample_df):
    real = ind.exclude_self_transfers(sample_df)
    result = ind.merchant_concentration(real)
    uber_row = result[result["merchant"] == "Uber"].iloc[0]
    assert uber_row["n_transacoes"] == 2
    assert uber_row["value_abs"] == pytest.approx(35.0)


def test_top_expenses_ordered_descending(sample_df):
    real = ind.exclude_self_transfers(sample_df)
    top = ind.top_expenses(real, n=2)
    assert list(top["value_abs"]) == sorted(top["value_abs"], reverse=True)
    assert top.iloc[0]["description"] == "Mercado"


def test_month_over_month_delta_none_when_no_previous():
    current = {"receitas": 100, "despesas": 50, "saldo": 50}
    delta = ind.month_over_month_delta(current, None)
    assert delta == {"receitas": None, "despesas": None, "saldo": None}


def test_month_over_month_delta_percent_change():
    current = {"receitas": 150, "despesas": 100, "saldo": 50}
    previous = {"receitas": 100, "despesas": 100, "saldo": 0}
    delta = ind.month_over_month_delta(current, previous)
    assert delta["receitas"] == pytest.approx(50.0)
    assert delta["despesas"] == pytest.approx(0.0)
    assert delta["saldo"] is None  # divisão por zero (saldo anterior era 0) -> None, não crash


def test_net_worth_history_sums_multiple_assets_same_date():
    assets = pd.DataFrame({
        "data_referencia": ["2026-05-31", "2026-05-31", "2026-06-30", "2026-06-30"],
        "saldo_liquido": [1000.0, 500.0, 1100.0, 520.0],
    })
    result = ind.net_worth_history(assets)
    assert list(result["patrimonio_total"]) == [1500.0, 1620.0]
    assert list(result["data_referencia"]) == ["2026-05-31", "2026-06-30"]


def test_net_worth_history_single_snapshot():
    assets = pd.DataFrame({"data_referencia": ["2026-06-30"], "saldo_liquido": [3006.49]})
    result = ind.net_worth_history(assets)
    assert len(result) == 1
    assert result.iloc[0]["patrimonio_total"] == pytest.approx(3006.49)


def test_net_worth_history_empty():
    assets = pd.DataFrame(columns=["data_referencia", "saldo_liquido"])
    result = ind.net_worth_history(assets)
    assert result.empty


def test_category_trend_breaks_down_by_month_and_category():
    df = pd.DataFrame({
        "date": ["2026-05-01", "2026-05-15", "2026-06-01", "2026-06-10"],
        "value": [-100.0, -50.0, -150.0, -30.0],
        "category": ["Lazer", "Mercado", "Lazer", "Mercado"],
    })
    trend = ind.category_trend(df)
    lazer_mai = trend[(trend["month"] == "2026-05") & (trend["category"] == "Lazer")].iloc[0]
    lazer_jun = trend[(trend["month"] == "2026-06") & (trend["category"] == "Lazer")].iloc[0]
    assert lazer_mai["value_abs"] == pytest.approx(100.0)
    assert lazer_jun["value_abs"] == pytest.approx(150.0)


def test_category_trend_empty_when_no_expenses():
    df = pd.DataFrame({"date": ["2026-06-01"], "value": [100.0], "category": ["Salário/Receita"]})
    assert ind.category_trend(df).empty


def test_average_spend_by_category_uses_last_n_months():
    df = pd.DataFrame({
        "date": ["2026-04-01", "2026-05-01", "2026-06-01", "2026-06-15"],
        "value": [-100.0, -200.0, -60.0, -30.0],
        "category": ["Lazer", "Lazer", "Lazer", "Lazer"],
    })
    result = ind.average_spend_by_category(df, janela=3)
    # 3 meses (abr, mai, jun) -> total 390 / 3 = 130
    lazer = result[result["category"] == "Lazer"].iloc[0]
    assert lazer["media_mensal"] == pytest.approx(130.0)


def test_average_spend_by_category_sorted_descending():
    df = pd.DataFrame({
        "date": ["2026-06-01", "2026-06-01"],
        "value": [-50.0, -500.0],
        "category": ["Lazer", "Mercado"],
    })
    result = ind.average_spend_by_category(df, janela=3)
    assert list(result["category"]) == ["Mercado", "Lazer"]


def test_average_spend_by_category_empty_when_no_expenses():
    df = pd.DataFrame({"date": ["2026-06-01"], "value": [100.0], "category": ["Salário/Receita"]})
    assert ind.average_spend_by_category(df).empty


def test_weekend_vs_weekday_spending():
    df = pd.DataFrame({
        # 2026-06-06 = sabado, 2026-06-07 = domingo, 2026-06-08 = segunda, 2026-06-09 = terca
        "date": ["2026-06-06", "2026-06-07", "2026-06-08", "2026-06-09"],
        "value": [-200.0, -100.0, -50.0, -30.0],
    })
    result = ind.weekend_vs_weekday_spending(df)
    assert result["media_fim_de_semana"] == pytest.approx(150.0)  # (200+100)/2
    assert result["media_dia_util"] == pytest.approx(40.0)        # (50+30)/2
    assert result["dias_fim_de_semana"] == 2
    assert result["dias_uteis"] == 2


def test_weekend_vs_weekday_spending_empty():
    df = pd.DataFrame(columns=["date", "value"])
    result = ind.weekend_vs_weekday_spending(df)
    assert result["media_fim_de_semana"] == 0.0
    assert result["media_dia_util"] == 0.0


def test_average_balance():
    balances = pd.DataFrame({"date": ["2026-06-01", "2026-06-02", "2026-06-03"], "balance": [1000.0, 2000.0, 3000.0]})
    result = ind.average_balance(balances)
    assert result["saldo_medio"] == pytest.approx(2000.0)
    assert result["dias"] == 3


def test_average_balance_empty():
    balances = pd.DataFrame(columns=["date", "balance"])
    result = ind.average_balance(balances)
    assert result == {"saldo_medio": 0.0, "dias": 0}
