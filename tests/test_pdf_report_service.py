"""
Testes de sifp/services/pdf_report_service.py -- cobre a paridade de
conteúdo com report_service.py (texto), achado real de auditoria (3ª
varredura): o PDF divergia do texto sem nenhum aviso.
"""

import io

import pandas as pd
import pdfplumber
import pytest

from sifp.services.pdf_report_service import generate_pdf_report


def _pdf_texto(monthly: pd.DataFrame, debt_transactions: pd.DataFrame, self_transfer_total: float = 0.0) -> str:
    summary = {"receitas": 5000.0, "despesas": 3000.0, "saldo": 2000.0, "taxa_poupanca": 40.0}
    by_cat = pd.DataFrame({"category": ["Mercado"], "value_abs": [300.0], "pct": [100.0]})
    by_merchant = pd.DataFrame({"merchant": ["Amigao"], "value_abs": [300.0], "n_transacoes": [1]})
    asset_positions = pd.DataFrame({"nome": ["CDB"], "tipo": ["Renda Fixa"], "saldo_liquido": [1000.0]})

    pdf_bytes = generate_pdf_report(
        "Jun/2026", summary, by_cat, by_merchant, monthly, [],
        asset_positions, debt_transactions, patrimonio_total=1000.0,
        self_transfer_total=self_transfer_total,
    )
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def test_dividas_table_inclui_total():
    """Achado real de auditoria: a seção Dívidas do PDF não mostrava o
    TOTAL que a versão em texto já mostra (report_service.py)."""
    monthly = pd.DataFrame({"month": ["2026-06"], "Receitas": [5000.0], "Despesas": [3000.0], "Saldo": [2000.0]})
    debt_transactions = pd.DataFrame({
        "date": ["2026-06-01", "2026-06-15"],
        "description": ["Emprestimo Pedro", "Ajuda familiar"],
        "value": [-100.0, -50.0],
    })
    texto = _pdf_texto(monthly, debt_transactions)
    idx = texto.find("Dívidas")
    trecho = texto[idx:idx + 200]
    assert "TOTAL" in trecho
    assert "150,00" in trecho  # 100 + 50


def test_evolucao_chart_avisa_quando_corta_meses():
    """Achado real de auditoria: o gráfico de evolução mensal corta pros
    últimos 12 meses sem aviso, enquanto o texto mostra o histórico
    inteiro -- alguém com mais de 12 meses de dados via números
    diferentes entre os dois formatos do mesmo relatório."""
    meses = [f"2025-{m:02d}" if m <= 12 else f"2026-{m - 12:02d}" for m in range(1, 15)]  # 14 meses
    monthly = pd.DataFrame({"month": meses, "Receitas": [5000.0] * 14, "Despesas": [3000.0] * 14, "Saldo": [2000.0] * 14})
    debt_transactions = pd.DataFrame(columns=["date", "description", "value"])

    texto = _pdf_texto(monthly, debt_transactions)
    assert "últimos 12 de 14 meses" in texto


def test_evolucao_chart_sem_aviso_quando_nao_corta():
    monthly = pd.DataFrame({"month": ["2026-05", "2026-06"], "Receitas": [5000.0] * 2, "Despesas": [3000.0] * 2, "Saldo": [2000.0] * 2})
    debt_transactions = pd.DataFrame(columns=["date", "description", "value"])

    texto = _pdf_texto(monthly, debt_transactions)
    assert "Exibindo os últimos" not in texto


def test_pdf_mostra_self_transfer_total_quando_maior_que_zero():
    """Melhoria viável da 3ª varredura: self_transfer_total (nota de
    transparência já mostrada no Dashboard) não aparecia no PDF."""
    monthly = pd.DataFrame({"month": ["2026-06"], "Receitas": [5000.0], "Despesas": [3000.0], "Saldo": [2000.0]})
    debt_transactions = pd.DataFrame(columns=["date", "description", "value"])

    texto = _pdf_texto(monthly, debt_transactions, self_transfer_total=1000.0)
    assert "movimentados entre contas próprias" in texto
    assert "1.000,00" in texto


def test_pdf_omite_self_transfer_total_quando_zero():
    monthly = pd.DataFrame({"month": ["2026-06"], "Receitas": [5000.0], "Despesas": [3000.0], "Saldo": [2000.0]})
    debt_transactions = pd.DataFrame(columns=["date", "description", "value"])

    texto = _pdf_texto(monthly, debt_transactions)
    assert "movimentados entre contas próprias" not in texto
