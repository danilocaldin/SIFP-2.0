"""
Testes do motor de diagnósticos (Módulo 10) — cada regra testada nos
limiares (dispara/não dispara) com dados sintéticos.
"""

import pandas as pd
import pytest

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO
from sifp.domain.models import DiagnosticSeverity
from sifp.intelligence import diagnostics as diag


# ---------------------------------------------------------------------
# saldo negativo recorrente
# ---------------------------------------------------------------------
def test_saldo_negativo_nao_dispara_com_1_mes_negativo():
    monthly = pd.DataFrame({
        "month": ["2026-04", "2026-05", "2026-06"],
        "Receitas": [5000, 5000, 5000],
        "Despesas": [4000, 4000, 6000],
        "Saldo": [1000, 1000, -1000],
    })
    assert diag.check_saldo_negativo_recorrente(monthly) == []


def test_saldo_negativo_dispara_com_2_de_3_meses():
    monthly = pd.DataFrame({
        "month": ["2026-04", "2026-05", "2026-06"],
        "Receitas": [5000, 5000, 7000],
        "Despesas": [6000, 6000, 6000],
        "Saldo": [-1000, -1000, 1000],
    })
    result = diag.check_saldo_negativo_recorrente(monthly)
    assert len(result) == 1
    assert result[0].codigo == "saldo_negativo_recorrente"
    assert result[0].severidade == DiagnosticSeverity.ALTA  # 2 de 3, nao todos
    assert result[0].impacto_financeiro == pytest.approx(-2000)


def test_saldo_negativo_critico_quando_todos_os_meses_negativos():
    monthly = pd.DataFrame({
        "month": ["2026-04", "2026-05", "2026-06"],
        "Receitas": [5000, 5000, 5000],
        "Despesas": [6000, 6000, 6000],
        "Saldo": [-1000, -1000, -1000],
    })
    result = diag.check_saldo_negativo_recorrente(monthly)
    assert result[0].severidade == DiagnosticSeverity.CRITICA


def test_saldo_negativo_ignora_meses_fora_da_janela():
    # 3 meses negativos antigos, mas os ultimos 3 (janela) estao ok
    monthly = pd.DataFrame({
        "month": ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"],
        "Receitas": [1, 1, 1, 1, 1, 1],
        "Despesas": [2, 2, 2, 0, 0, 0],
        "Saldo": [-1, -1, -1, 1, 1, 1],
    })
    assert diag.check_saldo_negativo_recorrente(monthly) == []


# ---------------------------------------------------------------------
# taxa de poupanca baixa
# ---------------------------------------------------------------------
def test_taxa_poupanca_nao_dispara_acima_do_limiar():
    summary = {"receitas": 5000, "despesas": 4000, "saldo": 1000, "taxa_poupanca": 20.0}
    assert diag.check_taxa_poupanca_baixa(summary, "Jun/2026") == []


def test_taxa_poupanca_dispara_alta_quando_positiva_mas_baixa():
    summary = {"receitas": 5000, "despesas": 4600, "saldo": 400, "taxa_poupanca": 8.0}
    result = diag.check_taxa_poupanca_baixa(summary, "Jun/2026")
    assert len(result) == 1
    assert result[0].severidade == DiagnosticSeverity.ALTA


def test_taxa_poupanca_critica_quando_negativa():
    summary = {"receitas": 5000, "despesas": 6000, "saldo": -1000, "taxa_poupanca": -20.0}
    result = diag.check_taxa_poupanca_baixa(summary, "Jun/2026")
    assert result[0].severidade == DiagnosticSeverity.CRITICA


def test_taxa_poupanca_ignora_mes_sem_receita():
    summary = {"receitas": 0, "despesas": 0, "saldo": 0, "taxa_poupanca": 0.0}
    assert diag.check_taxa_poupanca_baixa(summary, "Jun/2026") == []


# ---------------------------------------------------------------------
# concentracao por categoria
# ---------------------------------------------------------------------
def test_concentracao_nao_dispara_abaixo_do_limiar():
    by_cat = pd.DataFrame({
        "category": ["Mercado", "Lazer", "Transporte", "Saúde"],
        "value_abs": [250.0, 250.0, 250.0, 250.0],
        "pct": [25.0, 25.0, 25.0, 25.0],
    })
    assert diag.check_concentracao_categoria(by_cat, "Jun/2026") == []


def test_concentracao_dispara_acima_do_limiar():
    by_cat = pd.DataFrame({"category": ["Moradia"], "value_abs": [1000.0], "pct": [45.0]})
    result = diag.check_concentracao_categoria(by_cat, "Jun/2026")
    assert len(result) == 1
    assert "Moradia" in result[0].titulo
    assert result[0].impacto_financeiro == pytest.approx(1000.0)


def test_concentracao_ignora_periodo_sem_gastos():
    assert diag.check_concentracao_categoria(pd.DataFrame(columns=["category", "value_abs", "pct"]), "Jun/2026") == []


# ---------------------------------------------------------------------
# transacoes pendentes
# ---------------------------------------------------------------------
def test_pendentes_nao_dispara_com_poucas():
    all_tx = pd.DataFrame({"category": ["Mercado"] * 95 + [CATEGORIA_NAO_CATEGORIZADO] * 3})
    assert diag.check_transacoes_pendentes(all_tx) == []


def test_pendentes_dispara_por_quantidade_absoluta():
    all_tx = pd.DataFrame({"category": ["Mercado"] * 985 + [CATEGORIA_NAO_CATEGORIZADO] * 20})
    result = diag.check_transacoes_pendentes(all_tx)
    assert len(result) == 1
    assert result[0].severidade == DiagnosticSeverity.BAIXA


def test_pendentes_dispara_por_percentual():
    all_tx = pd.DataFrame({"category": ["Mercado"] * 90 + [CATEGORIA_NAO_CATEGORIZADO] * 10})
    result = diag.check_transacoes_pendentes(all_tx)
    assert len(result) == 1


# ---------------------------------------------------------------------
# reserva de emergencia
# ---------------------------------------------------------------------
def test_reserva_nao_dispara_com_patrimonio_suficiente():
    assert diag.check_reserva_emergencia(patrimonio_total=20000, despesa_media_mensal=5000) == []


def test_reserva_dispara_alta_quando_insuficiente_mas_positiva():
    result = diag.check_reserva_emergencia(patrimonio_total=5000, despesa_media_mensal=5000)
    assert len(result) == 1
    assert result[0].severidade == DiagnosticSeverity.ALTA  # 1 mes coberto, >=1


def test_reserva_dispara_critica_quando_menos_de_1_mes():
    result = diag.check_reserva_emergencia(patrimonio_total=1000, despesa_media_mensal=5000)
    assert result[0].severidade == DiagnosticSeverity.CRITICA


def test_reserva_ignora_quando_sem_despesa():
    assert diag.check_reserva_emergencia(patrimonio_total=1000, despesa_media_mensal=0) == []


# ---------------------------------------------------------------------
# orquestrador
# ---------------------------------------------------------------------
def test_run_diagnostics_orders_by_severity():
    monthly = pd.DataFrame({
        "month": ["2026-04", "2026-05", "2026-06"],
        "Receitas": [5000, 5000, 5000],
        "Despesas": [6000, 6000, 6000],
        "Saldo": [-1000, -1000, -1000],  # dispara CRITICA (saldo negativo)
    })
    summary = {"receitas": 5000, "despesas": 4900, "saldo": 100, "taxa_poupanca": 2.0}  # dispara ALTA (poupanca)
    by_cat = pd.DataFrame(columns=["category", "value_abs", "pct"])
    all_tx = pd.DataFrame({"category": ["Mercado"] * 10})

    result = diag.run_diagnostics(
        monthly=monthly, latest_summary=summary, latest_period_label="Jun/2026",
        latest_by_cat=by_cat, all_tx=all_tx,
    )
    assert len(result) == 2
    assert result[0].severidade == DiagnosticSeverity.CRITICA  # mais grave primeiro
    assert result[1].severidade == DiagnosticSeverity.ALTA


def test_run_diagnostics_empty_when_everything_healthy():
    monthly = pd.DataFrame({
        "month": ["2026-06"], "Receitas": [5000], "Despesas": [2000], "Saldo": [3000],
    })
    summary = {"receitas": 5000, "despesas": 2000, "saldo": 3000, "taxa_poupanca": 60.0}
    by_cat = pd.DataFrame({"category": ["Mercado"], "value_abs": [2000.0], "pct": [100.0]})
    all_tx = pd.DataFrame({"category": ["Mercado"] * 10})

    result = diag.run_diagnostics(
        monthly=monthly, latest_summary=summary, latest_period_label="Jun/2026",
        latest_by_cat=by_cat, all_tx=all_tx,
        patrimonio_total=50000, despesa_media_mensal=2000,
    )
    # concentracao vai disparar (100% numa categoria so), o resto nao
    codigos = {d.codigo for d in result}
    assert codigos == {"concentracao_categoria"}


# ---------------------------------------------------------------------
# orcamento estourado
# ---------------------------------------------------------------------
def test_orcamento_nao_dispara_sem_limites_configurados():
    by_cat = pd.DataFrame({"category": ["Lazer"], "value_abs": [500.0], "pct": [100.0]})
    assert diag.check_orcamento_estourado(by_cat, {}, "Jun/2026") == []


def test_orcamento_nao_dispara_dentro_do_limite():
    by_cat = pd.DataFrame({"category": ["Lazer"], "value_abs": [250.0], "pct": [100.0]})
    assert diag.check_orcamento_estourado(by_cat, {"Lazer": 300.0}, "Jun/2026") == []


def test_orcamento_dispara_media_quando_pouco_acima():
    by_cat = pd.DataFrame({"category": ["Lazer"], "value_abs": [330.0], "pct": [100.0]})
    result = diag.check_orcamento_estourado(by_cat, {"Lazer": 300.0}, "Jun/2026")
    assert len(result) == 1
    assert result[0].severidade == DiagnosticSeverity.MEDIA
    assert result[0].impacto_financeiro == pytest.approx(30.0)


def test_orcamento_dispara_alta_quando_muito_acima():
    by_cat = pd.DataFrame({"category": ["Lazer"], "value_abs": [500.0], "pct": [100.0]})
    result = diag.check_orcamento_estourado(by_cat, {"Lazer": 300.0}, "Jun/2026")
    assert result[0].severidade == DiagnosticSeverity.ALTA


def test_orcamento_ignora_categoria_sem_limite_configurado():
    by_cat = pd.DataFrame({
        "category": ["Lazer", "Mercado"], "value_abs": [500.0, 2000.0], "pct": [20.0, 80.0],
    })
    result = diag.check_orcamento_estourado(by_cat, {"Lazer": 300.0}, "Jun/2026")
    assert len(result) == 1
    assert "Lazer" in result[0].titulo


# ---------------------------------------------------------------------
# metas
# ---------------------------------------------------------------------
def test_meta_concluida_nao_dispara():
    goals = pd.DataFrame({
        "id": [1], "nome": ["Viagem"], "valor_necessario": [1000.0],
        "valor_acumulado": [1000.0], "prazo": ["2026-12-31"],
    })
    assert diag.check_metas(goals, hoje="2026-06-01") == []


def test_meta_atrasada_dispara_alta():
    goals = pd.DataFrame({
        "id": [1], "nome": ["Viagem"], "valor_necessario": [1000.0],
        "valor_acumulado": [200.0], "prazo": ["2026-05-01"],
    })
    result = diag.check_metas(goals, hoje="2026-06-01")
    assert len(result) == 1
    assert result[0].severidade == DiagnosticSeverity.ALTA
    assert "atrasada" in result[0].codigo


def test_meta_em_risco_quando_prazo_perto_e_progresso_baixo():
    goals = pd.DataFrame({
        "id": [1], "nome": ["Reserva"], "valor_necessario": [10000.0],
        "valor_acumulado": [1000.0], "prazo": ["2026-08-01"],  # ~60 dias a partir de 06/01
    })
    result = diag.check_metas(goals, hoje="2026-06-01")
    assert len(result) == 1
    assert result[0].severidade == DiagnosticSeverity.MEDIA
    assert "risco" in result[0].codigo


def test_meta_no_prazo_e_progresso_bom_nao_dispara():
    goals = pd.DataFrame({
        "id": [1], "nome": ["Reserva"], "valor_necessario": [10000.0],
        "valor_acumulado": [8000.0], "prazo": ["2026-08-01"],
    })
    assert diag.check_metas(goals, hoje="2026-06-01") == []


def test_meta_longe_do_prazo_com_progresso_baixo_nao_dispara_ainda():
    goals = pd.DataFrame({
        "id": [1], "nome": ["Reserva"], "valor_necessario": [10000.0],
        "valor_acumulado": [500.0], "prazo": ["2027-06-01"],  # 1 ano a frente
    })
    assert diag.check_metas(goals, hoje="2026-06-01") == []


def test_run_diagnostics_integra_orcamento_e_metas():
    monthly = pd.DataFrame({
        "month": ["2026-06"], "Receitas": [5000], "Despesas": [2000], "Saldo": [3000],
    })
    summary = {"receitas": 5000, "despesas": 2000, "saldo": 3000, "taxa_poupanca": 60.0}
    by_cat = pd.DataFrame({"category": ["Lazer"], "value_abs": [500.0], "pct": [100.0]})
    all_tx = pd.DataFrame({"category": ["Lazer"] * 10})
    goals = pd.DataFrame({
        "id": [1], "nome": ["Viagem"], "valor_necessario": [1000.0],
        "valor_acumulado": [200.0], "prazo": ["2026-05-01"],
    })

    result = diag.run_diagnostics(
        monthly=monthly, latest_summary=summary, latest_period_label="Jun/2026",
        latest_by_cat=by_cat, all_tx=all_tx,
        patrimonio_total=50000, despesa_media_mensal=2000,
        budget_limits={"Lazer": 300.0}, goals=goals, hoje="2026-06-01",
    )
    codigos = {d.codigo for d in result}
    assert "orcamento_estourado_Lazer" in codigos
    assert "meta_atrasada_1" in codigos


# ---------------------------------------------------------------------
# investimento abaixo do benchmark
# ---------------------------------------------------------------------
def test_investimento_nao_dispara_quando_rende_acima_do_benchmark():
    assets = pd.DataFrame({
        "identificador": ["cnpj1"], "nome": ["Fundo X"],
        "rentabilidade_12m_pct": [14.87], "benchmark": ["CDI"], "benchmark_12m_pct": [14.78],
    })
    assert diag.check_investimento_abaixo_benchmark(assets) == []


def test_investimento_nao_dispara_dentro_da_margem():
    # 0.3pp abaixo -- dentro da margem de 0.5pp, nao deveria disparar
    assets = pd.DataFrame({
        "identificador": ["cnpj1"], "nome": ["Fundo X"],
        "rentabilidade_12m_pct": [14.48], "benchmark": ["CDI"], "benchmark_12m_pct": [14.78],
    })
    assert diag.check_investimento_abaixo_benchmark(assets) == []


def test_investimento_dispara_media_quando_abaixo_do_benchmark():
    # 1.78pp abaixo -- dentro do limiar "media" (< 2pp de diferenca)
    assets = pd.DataFrame({
        "identificador": ["cnpj1"], "nome": ["Fundo X"],
        "rentabilidade_12m_pct": [13.0], "benchmark": ["CDI"], "benchmark_12m_pct": [14.78],
    })
    result = diag.check_investimento_abaixo_benchmark(assets)
    assert len(result) == 1
    assert result[0].severidade == DiagnosticSeverity.MEDIA
    assert "Fundo X" in result[0].titulo
    assert "CDI" in result[0].titulo


def test_investimento_dispara_alta_quando_muito_abaixo_do_benchmark():
    assets = pd.DataFrame({
        "identificador": ["cnpj1"], "nome": ["Fundo X"],
        "rentabilidade_12m_pct": [5.0], "benchmark": ["CDI"], "benchmark_12m_pct": [14.78],
    })
    result = diag.check_investimento_abaixo_benchmark(assets)
    assert result[0].severidade == DiagnosticSeverity.ALTA


def test_investimento_ignora_ativo_sem_benchmark_numerico():
    assets = pd.DataFrame({
        "identificador": ["cnpj1"], "nome": ["Fundo X"],
        "rentabilidade_12m_pct": [5.0], "benchmark": [None], "benchmark_12m_pct": [None],
    })
    assert diag.check_investimento_abaixo_benchmark(assets) == []


# ---------------------------------------------------------------------
# tendencia de categoria
# ---------------------------------------------------------------------
def _trend_df(valores_por_mes: dict, categoria: str = "Lazer") -> pd.DataFrame:
    rows = [{"month": m, "category": categoria, "value_abs": v} for m, v in valores_por_mes.items()]
    return pd.DataFrame(rows)


def test_tendencia_nao_dispara_com_historico_insuficiente():
    # so 4 meses -- precisa de 6 (2x janela de 3) pra comparar
    trend = _trend_df({"2026-03": 100, "2026-04": 100, "2026-05": 100, "2026-06": 100})
    assert diag.check_tendencia_categoria(trend) == []


def test_tendencia_nao_dispara_quando_crescimento_pequeno():
    trend = _trend_df({
        "2026-01": 100, "2026-02": 100, "2026-03": 100,  # media anterior = 100
        "2026-04": 105, "2026-05": 105, "2026-06": 105,  # media recente = 105 (+5%, abaixo do limiar de 25%)
    })
    assert diag.check_tendencia_categoria(trend) == []


def test_tendencia_dispara_quando_crescimento_grande():
    trend = _trend_df({
        "2026-01": 100, "2026-02": 100, "2026-03": 100,   # media anterior = 100
        "2026-04": 200, "2026-05": 200, "2026-06": 200,   # media recente = 200 (+100%)
    })
    result = diag.check_tendencia_categoria(trend)
    assert len(result) == 1
    assert result[0].codigo == "categoria_crescendo_Lazer"
    assert result[0].impacto_financeiro == pytest.approx(300.0)  # (200-100)*3


def test_tendencia_limita_ao_top_3_maiores_impactos():
    rows = []
    for i, categoria in enumerate(["A", "B", "C", "D"]):
        # todas crescem 100% mas com bases diferentes, pra ranquear por R$
        base = (i + 1) * 100
        for m, v in [("2026-01", base), ("2026-02", base), ("2026-03", base),
                     ("2026-04", base * 2), ("2026-05", base * 2), ("2026-06", base * 2)]:
            rows.append({"month": m, "category": categoria, "value_abs": v})
    trend = pd.DataFrame(rows)
    result = diag.check_tendencia_categoria(trend)
    assert len(result) == 3
    # categoria D tem a maior base, deveria ser a de maior impacto (primeira)
    assert result[0].codigo == "categoria_crescendo_D"


# ---------------------------------------------------------------------
# gasto fim de semana
# ---------------------------------------------------------------------
def test_fim_de_semana_nao_dispara_com_amostra_pequena():
    stats = {"media_fim_de_semana": 500.0, "media_dia_util": 100.0, "dias_fim_de_semana": 2, "dias_uteis": 2}
    assert diag.check_gasto_fim_de_semana(stats) == []


def test_fim_de_semana_nao_dispara_quando_diferenca_pequena():
    stats = {"media_fim_de_semana": 110.0, "media_dia_util": 100.0, "dias_fim_de_semana": 8, "dias_uteis": 20}
    assert diag.check_gasto_fim_de_semana(stats) == []


def test_fim_de_semana_dispara_quando_diferenca_grande():
    stats = {"media_fim_de_semana": 200.0, "media_dia_util": 100.0, "dias_fim_de_semana": 8, "dias_uteis": 20}
    result = diag.check_gasto_fim_de_semana(stats)
    assert len(result) == 1
    assert result[0].severidade == DiagnosticSeverity.BAIXA
    assert result[0].impacto_financeiro == pytest.approx(800.0)  # (200-100)*8


def test_run_diagnostics_integra_regras_narrativas():
    monthly = pd.DataFrame({
        "month": ["2026-06"], "Receitas": [5000], "Despesas": [2000], "Saldo": [3000],
    })
    summary = {"receitas": 5000, "despesas": 2000, "saldo": 3000, "taxa_poupanca": 60.0}
    by_cat = pd.DataFrame({"category": ["Mercado"], "value_abs": [2000.0], "pct": [100.0]})
    all_tx = pd.DataFrame({"category": ["Mercado"] * 10})
    assets = pd.DataFrame({
        "identificador": ["cnpj1"], "nome": ["Fundo X"],
        "rentabilidade_12m_pct": [5.0], "benchmark": ["CDI"], "benchmark_12m_pct": [14.78],
    })
    weekend_stats = {"media_fim_de_semana": 200.0, "media_dia_util": 100.0, "dias_fim_de_semana": 8, "dias_uteis": 20}

    result = diag.run_diagnostics(
        monthly=monthly, latest_summary=summary, latest_period_label="Jun/2026",
        latest_by_cat=by_cat, all_tx=all_tx,
        patrimonio_total=50000, despesa_media_mensal=2000,
        latest_assets=assets, weekend_stats=weekend_stats,
    )
    codigos = {d.codigo for d in result}
    assert "investimento_abaixo_benchmark_cnpj1" in codigos
    assert "gasto_fim_de_semana_elevado" in codigos


# ---------------------------------------------------------------------
# custo de dinheiro parado
# ---------------------------------------------------------------------
def test_dinheiro_parado_nao_dispara_sem_taxa_de_referencia():
    result = diag.check_custo_dinheiro_parado(
        saldo_medio_conta_corrente=5000.0, dias=30, taxa_anual_referencia=None, benchmark_nome=None,
    )
    assert result == []


def test_dinheiro_parado_nao_dispara_com_amostra_pequena():
    result = diag.check_custo_dinheiro_parado(
        saldo_medio_conta_corrente=5000.0, dias=5, taxa_anual_referencia=14.78, benchmark_nome="CDI",
    )
    assert result == []


def test_dinheiro_parado_nao_dispara_abaixo_do_limiar_de_valor():
    # saldo baixo + poucos dias -> custo de oportunidade pequeno demais pra valer o alerta
    result = diag.check_custo_dinheiro_parado(
        saldo_medio_conta_corrente=50.0, dias=15, taxa_anual_referencia=14.78, benchmark_nome="CDI",
    )
    assert result == []


def test_dinheiro_parado_dispara_com_saldo_relevante():
    result = diag.check_custo_dinheiro_parado(
        saldo_medio_conta_corrente=5000.0, dias=180, taxa_anual_referencia=14.78, benchmark_nome="CDI",
    )
    assert len(result) == 1
    assert result[0].codigo == "custo_dinheiro_parado"
    assert result[0].severidade == DiagnosticSeverity.BAIXA
    assert "CDI" in result[0].descricao
    # custo esperado: 5000 * 0.1478 * (180/365) ~= 364.66
    assert result[0].impacto_financeiro == pytest.approx(5000 * 0.1478 * 180 / 365, rel=1e-3)


def test_run_diagnostics_integra_dinheiro_parado():
    monthly = pd.DataFrame({"month": ["2026-06"], "Receitas": [5000], "Despesas": [2000], "Saldo": [3000]})
    summary = {"receitas": 5000, "despesas": 2000, "saldo": 3000, "taxa_poupanca": 60.0}
    by_cat = pd.DataFrame({"category": ["Mercado"], "value_abs": [2000.0], "pct": [100.0]})
    all_tx = pd.DataFrame({"category": ["Mercado"] * 10})
    assets = pd.DataFrame({
        "identificador": ["cnpj1"], "nome": ["Fundo X"],
        "rentabilidade_12m_pct": [14.87], "benchmark": ["CDI"], "benchmark_12m_pct": [14.78],
    })
    balance_stats = {"saldo_medio": 5000.0, "dias": 180}

    result = diag.run_diagnostics(
        monthly=monthly, latest_summary=summary, latest_period_label="Jun/2026",
        latest_by_cat=by_cat, all_tx=all_tx,
        latest_assets=assets, balance_stats=balance_stats,
    )
    codigos = {d.codigo for d in result}
    assert "custo_dinheiro_parado" in codigos
