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


def test_build_dashboard_nao_expoe_mais_all_transactions(service):
    # Achado real de auditoria: esse campo já passou de 1MB numa conta
    # com anos de uso e era carregado em toda troca de mês mesmo que o
    # expander nunca abrisse -- agora só existe via list_transactions().
    result = service.build_dashboard("2026-06", _mes)
    assert "all_transactions" not in result


def test_list_transactions_periodo_sorted_desc(service):
    result = service.list_transactions("2026-06")
    dates = [row["date"] for row in result["transactions"]]
    assert dates == sorted(dates, reverse=True)
    descriptions = {row["description"] for row in result["transactions"]}
    assert descriptions == {"Salario", "Mercado", "Uber", "Transferencia p/ investimento"}
    assert result["total"] == 4
    assert result["has_more"] is False


def test_list_transactions_dates_are_strings(service):
    result = service.list_transactions(None)
    for row in result["transactions"]:
        assert isinstance(row["date"], str)


def test_list_transactions_pagina_com_limit_e_offset(service):
    pagina1 = service.list_transactions(None, limit=2, offset=0)
    assert len(pagina1["transactions"]) == 2
    assert pagina1["total"] == 6  # 6 transações no fixture, sem filtro de mês
    assert pagina1["has_more"] is True

    pagina2 = service.list_transactions(None, limit=2, offset=2)
    assert len(pagina2["transactions"]) == 2
    # páginas não se sobrepõem
    assert {r["date"] + r["description"] for r in pagina1["transactions"]}.isdisjoint(
        {r["date"] + r["description"] for r in pagina2["transactions"]}
    )


def test_list_transactions_sem_dados():
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "empty.db")
        init_db(path)
        svc = DashboardService(TransactionRepository(path), BalanceRepository(path))
        assert svc.list_transactions(None) == {"transactions": [], "total": 0, "has_more": False}


def test_build_dashboard_daily_balance_empty_without_balance_data(service):
    result = service.build_dashboard("2026-06", _mes)
    assert result["daily_balance"] == []


def test_build_dashboard_daily_balance_filtered_by_month(tmp_db_path):
    init_db(tmp_db_path)
    transaction_repo = TransactionRepository(tmp_db_path)
    balance_repo = BalanceRepository(tmp_db_path)

    tx = pd.DataFrame([
        {"date": "2026-06-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
    ])
    transaction_repo.insert_new(tx)
    balances = pd.DataFrame([
        {"date": "2026-05-30", "balance": 100.0},
        {"date": "2026-06-01", "balance": 200.0},
        {"date": "2026-06-02", "balance": 250.0},
    ])
    balance_repo.insert_many(balances)

    svc = DashboardService(transaction_repo, balance_repo)
    result = svc.build_dashboard("2026-06", _mes)
    assert result["daily_balance"] == [
        {"date": "2026-06-01", "balance": 200.0},
        {"date": "2026-06-02", "balance": 250.0},
    ]
