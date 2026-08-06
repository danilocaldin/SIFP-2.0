"""
Testes de sifp/repositories/asset_repository.py, focados em
get_latest_positions() -- achado de uma varredura de segurança: um
ativo resgatado (que some dos extratos seguintes, sem nenhum sinal
explícito de "encerrado") continuava contando no patrimônio pra
sempre, porque a lógica antiga pegava a última linha de CADA ativo em
vez de só quem aparece no extrato mais recente.
"""

import pytest

from sifp.domain.models import AssetPosition
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.connection import init_db


@pytest.fixture
def asset_repo(tmp_db_path):
    init_db(tmp_db_path)
    return AssetRepository(tmp_db_path)


def _posicao(identificador, data_referencia, saldo_liquido, instituicao="BTG Pactual", nome=None):
    return AssetPosition(
        nome=nome or identificador,
        identificador=identificador,
        tipo="Fundo de Investimento",
        instituicao=instituicao,
        data_referencia=data_referencia,
        saldo_liquido=saldo_liquido,
    )


def test_ativo_resgatado_nao_conta_mais_apos_sumir_do_extrato_mais_recente(asset_repo):
    # Janeiro: dois fundos. Fevereiro: só um (o outro foi resgatado).
    asset_repo.insert_many([
        _posicao("FUNDO-A", "2026-01-31", 10_000.0),
        _posicao("FUNDO-B", "2026-01-31", 5_000.0),
    ])
    asset_repo.insert_many([
        _posicao("FUNDO-A", "2026-02-28", 10_200.0),
    ])

    latest = asset_repo.get_latest_positions()

    identificadores = set(latest["identificador"])
    assert identificadores == {"FUNDO-A"}
    assert "FUNDO-B" not in identificadores
    assert latest["saldo_liquido"].sum() == pytest.approx(10_200.0)


def test_get_all_mantem_historico_completo_mesmo_apos_resgate(asset_repo):
    """get_all() (usado pro gráfico de evolução) não deve ser afetado
    pela mudança -- o histórico completo continua existindo."""
    asset_repo.insert_many([
        _posicao("FUNDO-A", "2026-01-31", 10_000.0),
        _posicao("FUNDO-B", "2026-01-31", 5_000.0),
    ])
    asset_repo.insert_many([
        _posicao("FUNDO-A", "2026-02-28", 10_200.0),
    ])

    all_snapshots = asset_repo.get_all()
    assert len(all_snapshots) == 3


def test_get_latest_positions_por_instituicao_independente(asset_repo):
    """Instituições diferentes podem ter sido importadas em datas
    diferentes -- o corte de "mais recente" é por instituição, não uma
    data global única (senão um ativo de uma instituição importada há
    mais tempo desapareceria só por a outra ter um extrato mais novo)."""
    asset_repo.insert_many([
        _posicao("FUNDO-BTG", "2026-02-28", 10_000.0, instituicao="BTG Pactual"),
        _posicao("FUNDO-XP", "2026-01-15", 7_000.0, instituicao="XP Investimentos"),
    ])

    latest = asset_repo.get_latest_positions()

    identificadores = set(latest["identificador"])
    assert identificadores == {"FUNDO-BTG", "FUNDO-XP"}
    assert latest["saldo_liquido"].sum() == pytest.approx(17_000.0)


def test_get_latest_positions_vazio_sem_dados(asset_repo):
    assert asset_repo.get_latest_positions().empty
