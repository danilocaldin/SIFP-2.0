"""
Testes do report_service (Módulo 11). Como é geração de texto, os
testes checam que os números certos aparecem no lugar certo — não
comparam string inteira (frágil demais a mudanças de formatação).
"""

import pandas as pd
import pytest

from sifp.domain.models import Diagnostic, DiagnosticSeverity
from sifp.services.report_service import generate_text_report


@pytest.fixture
def summary():
    return {"receitas": 7573.64, "despesas": 6863.72, "saldo": 709.92, "taxa_poupanca": 9.37}


@pytest.fixture
def by_cat():
    return pd.DataFrame({
        "category": ["Alimentação", "Transporte"],
        "value_abs": [2535.45, 972.82],
        "pct": [37.0, 14.0],
    })


@pytest.fixture
def by_merchant():
    return pd.DataFrame({
        "merchant": ["Uber", "iFood"],
        "value_abs": [300.0, 150.0],
        "n_transacoes": [16, 4],
    })


@pytest.fixture
def monthly():
    return pd.DataFrame({
        "month": ["2026-05", "2026-06"],
        "Receitas": [6251.39, 7573.64],
        "Despesas": [7050.79, 6863.72],
        "Saldo": [-799.40, 709.92],
    })


@pytest.fixture
def diagnostics():
    return [
        Diagnostic(
            codigo="taxa_poupanca_baixa",
            titulo="Taxa de poupança baixa",
            severidade=DiagnosticSeverity.ALTA,
            # "\$" escapado de propósito -- é assim que diagnostics._brl()
            # formata de verdade (pensado para o markdown do Streamlit).
            descricao="Em Jun/2026, você guardou 9% da renda (receita R\\$ 7.573,64).",
            explicacao="Pouca margem para imprevistos.",
            recomendacao="Corte despesas variáveis.",
            impacto_financeiro=709.92,
        )
    ]


@pytest.fixture
def asset_positions():
    return pd.DataFrame({
        "nome": ["BTG CDB Plus FIRF CrPr"],
        "tipo": ["Fundo de Investimento"],
        "saldo_liquido": [3006.49],
    })


@pytest.fixture
def debt_transactions():
    return pd.DataFrame({
        "date": ["2026-06-15"],
        "description": ["Pix enviado - Max Nelson Caldin"],
        "value": [-200.0],
    })


def test_report_contains_summary_values(summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions):
    report = generate_text_report(
        "Jun/2026", summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions
    )
    assert "RELATÓRIO FINANCEIRO — Jun/2026" in report
    assert "7,573.64" in report
    assert "6,863.72" in report
    assert "709.92" in report
    assert "9.4%" in report or "9.37" in report or "9.4" in report


def test_report_contains_categories(summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions):
    report = generate_text_report(
        "Jun/2026", summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions
    )
    assert "Alimentação" in report
    assert "2,535.45" in report
    assert "Transporte" in report


def test_report_contains_merchants(summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions):
    report = generate_text_report(
        "Jun/2026", summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions
    )
    assert "Uber" in report
    assert "16x" in report


def test_report_contains_diagnostics_with_severity(summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions):
    report = generate_text_report(
        "Jun/2026", summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions
    )
    assert "[ALTA] Taxa de poupança baixa" in report
    assert "Corte despesas variáveis." in report


def test_report_unescapes_dollar_sign_from_diagnostics(summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions):
    """Regressão: Diagnostic.descricao vem com '\\$' escapado (pra renderizar
    certo como markdown no Streamlit) — o relatório é texto puro, sem parser
    de markdown, então a barra invertida não pode vazar pro arquivo."""
    report = generate_text_report(
        "Jun/2026", summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions
    )
    assert "\\$" not in report
    assert "R$ 7.573,64" in report


def test_report_contains_patrimonio_total(summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions):
    report = generate_text_report(
        "Jun/2026", summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions
    )
    assert "BTG CDB Plus FIRF CrPr" in report
    assert "3,006.49" in report


def test_report_contains_debts(summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions):
    report = generate_text_report(
        "Jun/2026", summary, by_cat, by_merchant, monthly, diagnostics, asset_positions, debt_transactions
    )
    assert "Max Nelson Caldin" in report
    assert "200.00" in report


def test_report_handles_empty_sections_gracefully(summary, monthly):
    empty_df = pd.DataFrame(columns=["category", "value_abs", "pct"])
    empty_merchant = pd.DataFrame(columns=["merchant", "value_abs", "n_transacoes"])
    empty_assets = pd.DataFrame(columns=["nome", "tipo", "saldo_liquido"])
    empty_debts = pd.DataFrame(columns=["date", "description", "value"])

    report = generate_text_report(
        "Jun/2026", summary, empty_df, empty_merchant, monthly, [], empty_assets, empty_debts
    )
    assert "sem despesas no período" in report
    assert "nenhum ativo importado" in report
    assert "Nenhum diagnóstico no momento." in report
    assert "nenhuma transação categorizada como Dívida" in report
