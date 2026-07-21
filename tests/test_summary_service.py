"""Testes do SummaryService (Módulo 16) — payload da tela Resumo."""

import pandas as pd
import pytest

from sifp.domain.categories import SELF_TRANSFER_CATEGORY
from sifp.domain.models import AssetPosition
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.goal_repository import GoalRepository
from sifp.repositories.transaction_repository import TransactionRepository
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
        {"date": "2026-05-10", "description": "Mercado", "value": -1000.0, "category": "Mercado"},
        {"date": "2026-06-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-06-10", "description": "Mercado", "value": -500.0, "category": "Mercado"},
    ])
    transaction_repo.insert_new(tx)

    asset_repo.insert_many([
        AssetPosition(
            nome="Fundo Teste", identificador="00.000.000/0001-00", tipo="Fundo de Investimento",
            instituicao="BTG Pactual", data_referencia="2026-06-30",
            saldo_bruto=3100.0, saldo_liquido=3000.0,
            rentabilidade_mes_pct=1.5, rentabilidade_ano_pct=6.0, rentabilidade_12m_pct=14.0,
            benchmark="CDI", benchmark_mes_pct=1.1, benchmark_ano_pct=5.5, benchmark_12m_pct=13.0,
        )
    ])

    return SummaryService(transaction_repo, balance_repo, asset_repo, budget_repo, goal_repo)


def test_build_resumo_no_data():
    from sifp.repositories.connection import init_db as init
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "empty.db")
        init(path)
        svc = SummaryService(
            TransactionRepository(path), BalanceRepository(path), AssetRepository(path),
            BudgetRepository(path), GoalRepository(path),
        )
        assert svc.build_resumo(_mes) == {"has_data": False}


def test_build_resumo_uses_latest_month(service):
    resumo = service.build_resumo(_mes)
    assert resumo["has_data"] is True
    assert resumo["mes"] == "2026-06"
    assert resumo["mes_label"] == "Jun/2026"
    assert resumo["saldo"] == pytest.approx(4500.0)
    assert resumo["taxa_poupanca_pct"] == pytest.approx(90.0)


def test_build_resumo_patrimonio_and_rentabilidade_real_nao_variacao_bruta(service):
    resumo = service.build_resumo(_mes)
    assert resumo["patrimonio_total"] == pytest.approx(3000.0)
    # rentabilidade do MES (nao a variacao bruta entre snapshots, que nem existe aqui - 1 so snapshot)
    assert resumo["taxa_mes_pct"] == pytest.approx(1.5)
    assert resumo["benchmark_mes_pct"] == pytest.approx(1.1)
    assert resumo["benchmark_nome"] == "CDI"


def test_build_resumo_delta_vs_previous_month(service):
    resumo = service.build_resumo(_mes)
    # despesa caiu de 1000 pra 500, saldo subiu de 4000 pra 4500 -> delta positivo
    assert resumo["delta_saldo_pct"] == pytest.approx((4500.0 - 4000.0) / 4000.0 * 100)


def test_build_resumo_includes_diagnostics_sorted_by_priority(service):
    resumo = service.build_resumo(_mes)
    assert isinstance(resumo["diagnostics"], list)
    if len(resumo["diagnostics"]) >= 2:
        prioridades = [d["prioridade"] for d in resumo["diagnostics"]]
        assert prioridades == sorted(prioridades)


def test_build_resumo_excludes_self_transfer_from_saldo(tmp_db_path):
    init_db(tmp_db_path)
    transaction_repo = TransactionRepository(tmp_db_path)
    tx = pd.DataFrame([
        {"date": "2026-06-01", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-06-02", "description": "Transferencia p/ investimento", "value": -1000.0, "category": SELF_TRANSFER_CATEGORY},
    ])
    transaction_repo.insert_new(tx)
    svc = SummaryService(
        transaction_repo, BalanceRepository(tmp_db_path), AssetRepository(tmp_db_path),
        BudgetRepository(tmp_db_path), GoalRepository(tmp_db_path),
    )
    resumo = svc.build_resumo(_mes)
    assert resumo["saldo"] == pytest.approx(5000.0)  # nao 4000 - self-transfer nao conta como despesa
