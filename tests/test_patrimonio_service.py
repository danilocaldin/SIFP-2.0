"""Testes do PatrimonioService — payload da tela Patrimônio + import de PDF."""

import pytest

from sifp.domain.models import AssetPosition
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.connection import init_db
from sifp.services.patrimonio_service import PatrimonioService


class FakeImporter:
    def __init__(self, positions):
        self._positions = positions
        self.received_file = None

    def read(self, file_obj):
        self.received_file = file_obj
        return self._positions


@pytest.fixture
def asset_repo(tmp_db_path):
    init_db(tmp_db_path)
    return AssetRepository(tmp_db_path)


def test_build_patrimonio_no_data(asset_repo):
    service = PatrimonioService(asset_repo, FakeImporter([]))
    assert service.build_patrimonio() == {"has_data": False}


def test_build_patrimonio_with_assets(asset_repo):
    asset_repo.insert_many([
        AssetPosition(
            nome="Fundo Teste", identificador="00.000.000/0001-00", tipo="Fundo de Investimento",
            instituicao="BTG Pactual", data_referencia="2026-06-30",
            saldo_bruto=3100.0, saldo_liquido=3000.0,
            rentabilidade_12m_pct=14.0, benchmark="CDI", benchmark_12m_pct=13.0,
        ),
        AssetPosition(
            nome="Fundo Teste", identificador="00.000.000/0001-00", tipo="Fundo de Investimento",
            instituicao="BTG Pactual", data_referencia="2026-05-31",
            saldo_bruto=2600.0, saldo_liquido=2500.0,
        ),
    ])
    service = PatrimonioService(asset_repo, FakeImporter([]))
    result = service.build_patrimonio()

    assert result["has_data"] is True
    assert result["patrimonio_total"] == pytest.approx(3000.0)
    assert len(result["assets"]) == 1  # só a posição mais recente
    assert result["assets"][0]["data_referencia"] == "2026-06-30"
    assert len(result["net_worth_history"]) == 2  # historico com os 2 snapshots
    for row in result["net_worth_history"]:
        assert row["data_referencia"] in ("2026-05-31", "2026-06-30")  # "YYYY-MM-DD", nao timestamp ISO completo


def test_import_pdf_persists_positions(asset_repo):
    positions = [
        AssetPosition(
            nome="Fundo Novo", identificador="11.111.111/0001-11", tipo="Fundo de Investimento",
            instituicao="BTG Pactual", data_referencia="2026-06-30",
            saldo_bruto=100.0, saldo_liquido=99.0,
        )
    ]
    fake_importer = FakeImporter(positions)
    service = PatrimonioService(asset_repo, fake_importer)

    n = service.import_pdf("um-arquivo-fake")

    assert n == 1
    assert fake_importer.received_file == "um-arquivo-fake"
    assert asset_repo.get_all()["nome"].tolist() == ["Fundo Novo"]


def test_import_pdf_propagates_importer_errors(asset_repo):
    class BrokenImporter:
        def read(self, file_obj):
            raise ValueError("PDF ilegível")

    service = PatrimonioService(asset_repo, BrokenImporter())
    with pytest.raises(ValueError, match="PDF ilegível"):
        service.import_pdf("qualquer-coisa")
