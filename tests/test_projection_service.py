"""Testes do projection_service (Módulo 15, Fase 5)."""

import pandas as pd
import pytest

from sifp.services import projection_service as proj


def test_average_monthly_saldo_uses_last_n_months():
    monthly = pd.DataFrame({
        "month": ["2026-01", "2026-02", "2026-03", "2026-04"],
        "Saldo": [1000.0, -500.0, 300.0, 700.0],
    })
    # janela=3 -> ultimos 3 meses: -500, 300, 700 -> media 166.67
    assert proj.average_monthly_saldo(monthly, janela=3) == pytest.approx(500.0 / 3)


def test_average_monthly_saldo_fewer_months_than_janela():
    monthly = pd.DataFrame({"month": ["2026-01", "2026-02"], "Saldo": [100.0, 300.0]})
    assert proj.average_monthly_saldo(monthly, janela=3) == pytest.approx(200.0)


def test_average_monthly_saldo_empty():
    monthly = pd.DataFrame(columns=["month", "Saldo"])
    assert proj.average_monthly_saldo(monthly) == 0.0


def test_saldo_range_uses_min_max_observado_na_janela():
    monthly = pd.DataFrame({
        "month": ["2026-01", "2026-02", "2026-03", "2026-04"],
        "Saldo": [1000.0, -500.0, 300.0, 700.0],
    })
    # janela=3 -> ultimos 3 meses: -500, 300, 700
    result = proj.saldo_range(monthly, janela=3)
    assert result == {"pior": -500.0, "media": pytest.approx(500.0 / 3), "melhor": 700.0}


def test_saldo_range_fewer_months_than_janela():
    monthly = pd.DataFrame({"month": ["2026-01", "2026-02"], "Saldo": [100.0, 300.0]})
    result = proj.saldo_range(monthly, janela=3)
    assert result == {"pior": 100.0, "media": pytest.approx(200.0), "melhor": 300.0}


def test_saldo_range_empty():
    monthly = pd.DataFrame(columns=["month", "Saldo"])
    assert proj.saldo_range(monthly) == {"pior": 0.0, "media": 0.0, "melhor": 0.0}


def test_project_patrimonio_linear_growth():
    result = proj.project_patrimonio(patrimonio_atual=1000.0, saldo_medio_mensal=100.0, meses=3)
    assert list(result["mes_offset"]) == [1, 2, 3]
    assert list(result["patrimonio_projetado"]) == [1100.0, 1200.0, 1300.0]


def test_project_patrimonio_negative_saldo_decreases():
    result = proj.project_patrimonio(patrimonio_atual=1000.0, saldo_medio_mensal=-50.0, meses=2)
    assert list(result["patrimonio_projetado"]) == [950.0, 900.0]


def test_project_goal_eta_months_already_reached():
    assert proj.project_goal_eta_months(valor_necessario=1000.0, valor_acumulado=1000.0, saldo_medio_mensal=100.0) == 0
    assert proj.project_goal_eta_months(valor_necessario=1000.0, valor_acumulado=1500.0, saldo_medio_mensal=100.0) == 0


def test_project_goal_eta_months_rounds_up():
    # faltam 250, saldo medio 100/mes -> 2.5 -> arredonda pra 3
    assert proj.project_goal_eta_months(valor_necessario=1000.0, valor_acumulado=750.0, saldo_medio_mensal=100.0) == 3


def test_project_goal_eta_months_never_reaches_with_zero_or_negative_saldo():
    assert proj.project_goal_eta_months(valor_necessario=1000.0, valor_acumulado=0.0, saldo_medio_mensal=0.0) is None
    assert proj.project_goal_eta_months(valor_necessario=1000.0, valor_acumulado=0.0, saldo_medio_mensal=-50.0) is None


def test_weighted_avg_rentabilidade_ponders_by_saldo():
    assets = pd.DataFrame({
        "saldo_liquido": [1000.0, 3000.0],
        "rentabilidade_12m_pct": [10.0, 20.0],
    })
    # (1000*10 + 3000*20) / 4000 = 17.5
    assert proj.weighted_avg_rentabilidade(assets) == pytest.approx(17.5)


def test_weighted_avg_rentabilidade_ignores_nan_rows():
    assets = pd.DataFrame({
        "saldo_liquido": [1000.0, 3000.0],
        "rentabilidade_12m_pct": [10.0, None],
    })
    assert proj.weighted_avg_rentabilidade(assets) == pytest.approx(10.0)


def test_weighted_avg_rentabilidade_accepts_other_field():
    assets = pd.DataFrame({
        "saldo_liquido": [1000.0, 1000.0],
        "rentabilidade_12m_pct": [10.0, 20.0],
        "rentabilidade_mes_pct": [1.0, 3.0],
    })
    assert proj.weighted_avg_rentabilidade(assets, campo="rentabilidade_mes_pct") == pytest.approx(2.0)


def test_weighted_avg_rentabilidade_missing_column_returns_none():
    assets = pd.DataFrame({"saldo_liquido": [1000.0], "rentabilidade_12m_pct": [10.0]})
    assert proj.weighted_avg_rentabilidade(assets, campo="benchmark_mes_pct") is None


def test_weighted_avg_rentabilidade_empty_or_all_nan():
    assert proj.weighted_avg_rentabilidade(pd.DataFrame(columns=["saldo_liquido", "rentabilidade_12m_pct"])) is None
    assets = pd.DataFrame({"saldo_liquido": [1000.0], "rentabilidade_12m_pct": [None]})
    assert proj.weighted_avg_rentabilidade(assets) is None


def test_project_patrimonio_com_rendimento_compounds_monthly():
    # taxa anual 0% -> deve se comportar igual ao modelo linear simples
    result = proj.project_patrimonio_com_rendimento(
        patrimonio_atual=1000.0, saldo_medio_mensal=100.0, taxa_anual_pct=0.0, meses=3
    )
    assert list(result["patrimonio_projetado"]) == pytest.approx([1100.0, 1200.0, 1300.0])


def test_project_patrimonio_com_rendimento_applies_monthly_rate():
    result = proj.project_patrimonio_com_rendimento(
        patrimonio_atual=1000.0, saldo_medio_mensal=0.0, taxa_anual_pct=12.68, meses=1
    )
    # taxa mensal equivalente a 12.68% a.a. -> ~1% a.m.
    taxa_mensal = (1 + 12.68 / 100) ** (1 / 12) - 1
    assert result.iloc[0]["patrimonio_projetado"] == pytest.approx(1000.0 * (1 + taxa_mensal))
