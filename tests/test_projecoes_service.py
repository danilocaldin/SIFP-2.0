"""Testes do ProjecoesService — payload da tela Projeções."""

import pandas as pd
import pytest

from sifp.domain.models import AssetPosition
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.goal_repository import GoalRepository
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.projecoes_service import ProjecoesService


@pytest.fixture
def repos(tmp_db_path):
    init_db(tmp_db_path)
    return {
        "transaction_repo": TransactionRepository(tmp_db_path),
        "asset_repo": AssetRepository(tmp_db_path),
        "goal_repo": GoalRepository(tmp_db_path),
    }


def test_build_projecoes_no_data(repos):
    service = ProjecoesService(repos["transaction_repo"], repos["asset_repo"], repos["goal_repo"])
    assert service.build_projecoes() == {"has_data": False}


def _seed_positive_saldo(repos):
    tx = pd.DataFrame([
        {"date": "2026-04-01", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-04-05", "description": "Mercado", "value": -1000.0, "category": "Mercado"},
        {"date": "2026-05-01", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-05-05", "description": "Mercado", "value": -1000.0, "category": "Mercado"},
        {"date": "2026-06-01", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-06-05", "description": "Mercado", "value": -1000.0, "category": "Mercado"},
    ])
    repos["transaction_repo"].insert_new(tx)


def test_build_projecoes_positive_saldo_projects_growth(repos):
    _seed_positive_saldo(repos)
    repos["asset_repo"].insert_many([
        AssetPosition(
            nome="Fundo", identificador="1", tipo="Fundo de Investimento", instituicao="BTG",
            data_referencia="2026-06-30", saldo_bruto=1000.0, saldo_liquido=1000.0,
            rentabilidade_12m_pct=12.68,
        )
    ])
    service = ProjecoesService(repos["transaction_repo"], repos["asset_repo"], repos["goal_repo"])
    result = service.build_projecoes(horizonte=12)

    assert result["has_data"] is True
    assert result["saldo_medio_3m"] == pytest.approx(4000.0)
    assert result["patrimonio_atual"] == pytest.approx(1000.0)
    assert result["patrimonio_final"] is not None
    assert result["patrimonio_final"] > result["patrimonio_atual"]
    assert len(result["chart"]) > 0


def test_build_projecoes_negative_saldo_skips_chart(repos):
    tx = pd.DataFrame([
        {"date": "2026-06-01", "description": "Salario", "value": 1000.0, "category": "Salário/Receita"},
        {"date": "2026-06-05", "description": "Mercado", "value": -5000.0, "category": "Mercado"},
    ])
    repos["transaction_repo"].insert_new(tx)
    service = ProjecoesService(repos["transaction_repo"], repos["asset_repo"], repos["goal_repo"])
    result = service.build_projecoes()

    assert result["saldo_medio_3m"] < 0
    assert result["patrimonio_final"] is None
    assert result["chart"] == []


def test_build_projecoes_goal_eta(repos):
    _seed_positive_saldo(repos)
    repos["goal_repo"].create("Reserva", 20000.0, "2030-01-01")
    service = ProjecoesService(repos["transaction_repo"], repos["asset_repo"], repos["goal_repo"])
    result = service.build_projecoes()

    assert len(result["goals"]) == 1
    goal = result["goals"][0]
    assert goal["nome"] == "Reserva"
    assert goal["eta_meses"] == 5  # faltam 20000, saldo medio 4000/mes -> 5 meses
    assert goal["dentro_do_prazo"] is True


def test_build_projecoes_expoe_faixa_de_confianca(repos):
    _seed_positive_saldo(repos)
    repos["asset_repo"].insert_many([
        AssetPosition(
            nome="Fundo", identificador="1", tipo="Fundo de Investimento", instituicao="BTG",
            data_referencia="2026-06-30", saldo_bruto=1000.0, saldo_liquido=1000.0,
        )
    ])
    service = ProjecoesService(repos["transaction_repo"], repos["asset_repo"], repos["goal_repo"])
    result = service.build_projecoes(horizonte=12)

    assert result["saldo_range"] == {"pior": pytest.approx(4000.0), "media": pytest.approx(4000.0), "melhor": pytest.approx(4000.0)}
    assert result["patrimonio_final_melhor"] is not None
    assert result["patrimonio_final_pior"] is not None
    assert result["patrimonio_final_melhor"] == pytest.approx(result["patrimonio_final_pior"])  # 3 meses iguais -> faixa achatada

    ponto_projetado = next(p for p in result["chart"] if p["tipo"] == "projecao")
    assert "patrimonio_melhor" in ponto_projetado
    assert "patrimonio_pior" in ponto_projetado


def test_build_projecoes_mostra_grafico_quando_melhor_mes_e_positivo_mesmo_com_media_negativa(repos):
    # media dos ultimos 3 meses e negativa, mas um dos meses foi positivo --
    # o grafico deve aparecer mesmo assim (mais honesto que esconder tudo)
    tx = pd.DataFrame([
        {"date": "2026-04-01", "description": "Salario", "value": 1000.0, "category": "Salário/Receita"},
        {"date": "2026-04-05", "description": "Mercado", "value": -4000.0, "category": "Mercado"},  # -3000
        {"date": "2026-05-01", "description": "Salario", "value": 1000.0, "category": "Salário/Receita"},
        {"date": "2026-05-05", "description": "Mercado", "value": -4000.0, "category": "Mercado"},  # -3000
        {"date": "2026-06-01", "description": "Salario", "value": 3000.0, "category": "Salário/Receita"},
        {"date": "2026-06-05", "description": "Mercado", "value": -2000.0, "category": "Mercado"},  # +1000
    ])
    repos["transaction_repo"].insert_new(tx)
    repos["asset_repo"].insert_many([
        AssetPosition(
            nome="Fundo", identificador="1", tipo="Fundo de Investimento", instituicao="BTG",
            data_referencia="2026-06-30", saldo_bruto=1000.0, saldo_liquido=1000.0,
        )
    ])
    service = ProjecoesService(repos["transaction_repo"], repos["asset_repo"], repos["goal_repo"])
    result = service.build_projecoes()

    assert result["saldo_medio_3m"] < 0  # media dos 3 meses e negativa
    assert result["saldo_range"]["melhor"] == pytest.approx(1000.0)
    assert result["patrimonio_final"] is not None  # grafico aparece mesmo assim
    assert len(result["chart"]) > 0
    assert result["patrimonio_final_melhor"] > result["patrimonio_final_pior"]


def test_build_projecoes_goal_already_reached(repos):
    _seed_positive_saldo(repos)
    repos["goal_repo"].create("Meta feita", 100.0, "2030-01-01")
    repos["goal_repo"].update_progress(1, 200.0)
    service = ProjecoesService(repos["transaction_repo"], repos["asset_repo"], repos["goal_repo"])
    result = service.build_projecoes()

    assert result["goals"][0]["eta_meses"] == 0
    assert result["goals"][0]["data_prevista"] is None
