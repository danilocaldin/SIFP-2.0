"""Testes do OrcamentoService — payload da tela Orçamento."""

import pandas as pd
import pytest

from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.orcamento_service import OrcamentoService


@pytest.fixture
def service(tmp_db_path):
    init_db(tmp_db_path)
    transaction_repo = TransactionRepository(tmp_db_path)
    budget_repo = BudgetRepository(tmp_db_path)

    tx = pd.DataFrame([
        {"date": "2026-05-01", "description": "Mercado", "value": -400.0, "category": "Mercado"},
        {"date": "2026-06-01", "description": "Mercado", "value": -600.0, "category": "Mercado"},
    ])
    transaction_repo.insert_new(tx)

    return OrcamentoService(transaction_repo, budget_repo), budget_repo


def test_build_orcamento_includes_all_categories(service):
    svc, _ = service
    result = svc.build_orcamento()
    assert "Mercado" in result["categorias"]
    assert "Não categorizado" not in result["categorias"]


def test_build_orcamento_suggestion_is_average_spend(service):
    svc, _ = service
    result = svc.build_orcamento()
    assert result["sugestoes"]["Mercado"] == pytest.approx(500.0)


def test_build_orcamento_shows_current_spend_against_limit(service):
    svc, budget_repo = service
    budget_repo.set_limit("Mercado", 800.0)
    result = svc.build_orcamento()
    assert len(result["limites"]) == 1
    limite = result["limites"][0]
    assert limite["category"] == "Mercado"
    assert limite["limite_mensal"] == pytest.approx(800.0)
    assert limite["gasto_atual"] == pytest.approx(600.0)  # mes mais recente (junho)


def test_build_orcamento_no_data():
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "empty.db")
        init_db(path)
        svc = OrcamentoService(TransactionRepository(path), BudgetRepository(path))
        result = svc.build_orcamento()
        assert result["sugestoes"] == {}
        assert result["limites"] == []
        assert len(result["categorias"]) > 0
