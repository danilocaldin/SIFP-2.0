"""Testes do RelatorioService — payload da tela Relatório."""

import pandas as pd
import pytest

from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.goal_repository import GoalRepository
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.relatorio_service import RelatorioService
from sifp.services.summary_service import SummaryService


def _mes(periodo: str) -> str:
    ano, mes = periodo.split("-")
    nomes = {"05": "Mai", "06": "Jun"}
    return f"{nomes[mes]}/{ano}"


@pytest.fixture
def service(tmp_db_path):
    init_db(tmp_db_path)
    transaction_repo = TransactionRepository(tmp_db_path)
    balance_repo = BalanceRepository(tmp_db_path)
    asset_repo = AssetRepository(tmp_db_path)
    budget_repo = BudgetRepository(tmp_db_path)
    goal_repo = GoalRepository(tmp_db_path)

    tx = pd.DataFrame([
        {"date": "2026-05-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-05-10", "description": "Mercado", "value": -1000.0, "category": "Mercado", "merchant": "Mercado Livre"},
        {"date": "2026-06-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-06-10", "description": "Mercado", "value": -300.0, "category": "Mercado", "merchant": "Mercado Livre"},
        {"date": "2026-06-11", "description": "Financiamento carro", "value": -400.0, "category": "Dívida"},
    ])
    transaction_repo.insert_new(tx)

    summary_service = SummaryService(transaction_repo, balance_repo, asset_repo, budget_repo, goal_repo)
    return RelatorioService(transaction_repo, asset_repo, summary_service)


def test_build_relatorio_no_data():
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "empty.db")
        init_db(path)
        svc = RelatorioService(
            TransactionRepository(path),
            AssetRepository(path),
            SummaryService(
                TransactionRepository(path),
                BalanceRepository(path),
                AssetRepository(path),
                BudgetRepository(path),
                GoalRepository(path),
            ),
        )
        assert svc.build_relatorio(None, _mes) == {"has_data": False}


def test_build_relatorio_specific_month(service):
    result = service.build_relatorio("2026-06", _mes)
    assert result["has_data"] is True
    assert result["period_label"] == "Jun/2026"
    assert result["selected_month"] == "2026-06"
    assert result["months"] == ["2026-05", "2026-06"]
    assert result["months_labels"] == {"2026-05": "Mai/2026", "2026-06": "Jun/2026"}


def test_build_relatorio_invalid_month_falls_back_to_latest(service):
    result = service.build_relatorio("2099-01", _mes)
    assert result["selected_month"] == "2026-06"


def test_build_relatorio_none_month_falls_back_to_latest(service):
    result = service.build_relatorio(None, _mes)
    assert result["selected_month"] == "2026-06"


def test_build_relatorio_report_text_contains_expected_sections(service):
    result = service.build_relatorio("2026-06", _mes)
    text = result["report_text"]
    assert "RELATÓRIO FINANCEIRO — Jun/2026" in text
    assert "RESUMO FINANCEIRO" in text
    assert "GASTOS POR CATEGORIA" in text
    assert "DÍVIDAS" in text
    assert "Financiamento carro" in text
    # sem escape de markdown vazando pro texto plano
    assert "R\\$" not in text
