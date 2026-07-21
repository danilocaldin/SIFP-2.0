"""Testes do DashboardService — payload da tela Dashboard."""

import pandas as pd
import pytest

from sifp.domain.categories import SELF_TRANSFER_CATEGORY
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.connection import init_db
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.dashboard_service import DashboardService


def _mes(periodo: str) -> str:
    ano, mes = periodo.split("-")
    nomes = {"05": "Mai", "06": "Jun"}
    return f"{nomes[mes]}/{ano}"


@pytest.fixture
def service(tmp_db_path):
    init_db(tmp_db_path)
    transaction_repo = TransactionRepository(tmp_db_path)
    balance_repo = BalanceRepository(tmp_db_path)

    tx = pd.DataFrame([
        {"date": "2026-05-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-05-10", "description": "Mercado", "value": -1000.0, "category": "Mercado", "merchant": "Mercado Livre"},
        {"date": "2026-06-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-06-10", "description": "Mercado", "value": -300.0, "category": "Mercado", "merchant": "Mercado Livre"},
        {"date": "2026-06-11", "description": "Uber", "value": -50.0, "category": "Transporte", "merchant": "Uber"},
        {"date": "2026-06-12", "description": "Transferencia p/ investimento", "value": -1000.0, "category": SELF_TRANSFER_CATEGORY},
    ])
    transaction_repo.insert_new(tx)

    return DashboardService(transaction_repo, balance_repo)


def test_build_dashboard_no_data():
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "empty.db")
        init_db(path)
        svc = DashboardService(TransactionRepository(path), BalanceRepository(path))
        assert svc.build_dashboard(None, _mes) == {"has_data": False}


def test_build_dashboard_specific_month(service):
    result = service.build_dashboard("2026-06", _mes)
    assert result["has_data"] is True
    assert result["period_label"] == "Jun/2026"
    assert result["receitas"] == pytest.approx(5000.0)
    assert result["despesas"] == pytest.approx(350.0)  # self-transfer excluded
    assert result["self_transfer_total"] == pytest.approx(1000.0)
    assert result["months"] == ["2026-05", "2026-06"]


def test_build_dashboard_all_months(service):
    result = service.build_dashboard(None, _mes)
    assert result["period_label"] == "todo o período importado"
    assert result["receitas"] == pytest.approx(10000.0)
    assert result["despesas"] == pytest.approx(1350.0)


def test_build_dashboard_delta_vs_previous_month(service):
    result = service.build_dashboard("2026-06", _mes)
    # despesa caiu de 1000 pra 350
    assert result["delta"]["despesas"] == pytest.approx((350.0 - 1000.0) / 1000.0 * 100)


def test_build_dashboard_category_and_merchant_breakdown(service):
    result = service.build_dashboard("2026-06", _mes)
    categories = {c["category"]: c["value_abs"] for c in result["by_category"]}
    assert categories["Mercado"] == pytest.approx(300.0)
    assert categories["Transporte"] == pytest.approx(50.0)
    merchants = {m["merchant"]: m["value_abs"] for m in result["top_merchants"]}
    assert merchants["Uber"] == pytest.approx(50.0)


def test_build_dashboard_invalid_month_falls_back_to_all(service):
    result = service.build_dashboard("2099-01", _mes)
    assert result["selected_month"] is None
    assert result["period_label"] == "todo o período importado"


def test_build_dashboard_top_expenses_dates_are_strings(service):
    result = service.build_dashboard("2026-06", _mes)
    for row in result["top_expenses"]:
        assert isinstance(row["date"], str)
