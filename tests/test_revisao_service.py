"""Testes do RevisaoService — payload da tela Revisão de Categorias."""

import pandas as pd
import pytest

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO
from sifp.repositories.connection import init_db
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.revisao_service import RevisaoService


def _sample_transactions():
    return pd.DataFrame(
        {
            "date": ["2026-06-01 10:00", "2026-06-02 11:00", "2026-06-03 12:00", "2026-06-04 13:00"],
            "description": ["Uber", "Padaria Sao Jose", "Padaria Sao Jose", "Pix Joao"],
            "value": [-10.0, -20.0, -15.0, -100.0],
            "category": ["Transporte", CATEGORIA_NAO_CATEGORIZADO, CATEGORIA_NAO_CATEGORIZADO, CATEGORIA_NAO_CATEGORIZADO],
            "confidence": [0.99, 0.0, 0.0, 0.0],
            "bank_category": ["Transporte", "", "", ""],
            "self_transfer": [False, False, False, False],
            "merchant": ["Uber", "Padaria Sao Jose", "Padaria Sao Jose", "Pix Joao"],
            "category_source": ["keyword_rule", "", "", ""],
        }
    )


@pytest.fixture
def repo(tmp_db_path):
    init_db(tmp_db_path)
    return TransactionRepository(tmp_db_path)


@pytest.fixture
def service(repo):
    repo.insert_new(_sample_transactions())
    return RevisaoService(repo)


def test_build_revisao_no_data():
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "empty.db")
        init_db(path)
        svc = RevisaoService(TransactionRepository(path))
        assert svc.build_revisao() == {"has_data": False}


def test_build_revisao_returns_all_transactions_with_situacao(service):
    result = service.build_revisao()
    assert result["has_data"] is True
    assert result["total"] == 4
    situacoes = {t["description"]: t["situacao"] for t in result["transactions"]}
    assert situacoes["Uber"] == "Alta confiança"
    assert situacoes["Padaria Sao Jose"] == "Novo / revisar"


def test_build_revisao_groups_pending_establishments_excluding_pix(service):
    result = service.build_revisao()
    lote = {p["descricao"]: p["quantidade"] for p in result["lote_pendentes"]}
    assert lote == {"Padaria Sao Jose": 2}  # Pix Joao fica de fora (revisão individual)


def test_build_revisao_exposes_categorias_and_marker(service):
    result = service.build_revisao()
    assert "Mercado" in result["categorias"]
    assert result["categoria_nao_categorizada"] == CATEGORIA_NAO_CATEGORIZADO


def test_bulk_apply_by_description_updates_only_pending_matches(service, repo):
    n = service.bulk_apply_by_description("Padaria Sao Jose", "Mercado")
    assert n == 2

    all_tx = repo.get_all()
    padaria = all_tx[all_tx["description"] == "Padaria Sao Jose"]
    assert (padaria["category"] == "Mercado").all()
    assert (padaria["human_confirmed"] == 1).all()

    # não mexe em outras descrições
    uber = all_tx[all_tx["description"] == "Uber"]
    assert (uber["category"] == "Transporte").all()


def test_bulk_apply_by_description_unknown_description_is_noop(service):
    n = service.bulk_apply_by_description("Nao Existe", "Mercado")
    assert n == 0


def test_situacao_reflects_learned_variable_memory(repo):
    df = pd.DataFrame(
        {
            "date": ["2026-06-01 10:00", "2026-06-02 10:00", "2026-06-03 10:00"],
            "description": ["Pix Maria", "Pix Maria", "Pix Maria"],
            "value": [-50.0, -60.0, -70.0],
            "category": ["Lazer", "Moradia", CATEGORIA_NAO_CATEGORIZADO],
            "confidence": [0.99, 0.99, 0.0],
            "bank_category": ["", "", ""],
            "self_transfer": [False, False, False],
            "merchant": ["Pix Maria", "Pix Maria", "Pix Maria"],
            "category_source": ["", "", ""],
        }
    )
    repo.insert_new(df)
    all_tx = repo.get_all()
    hashes = all_tx[all_tx["category"].isin(["Lazer", "Moradia"])]["tx_hash"].tolist()
    repo.bulk_update_categories([(h, all_tx.set_index("tx_hash").loc[h, "category"]) for h in hashes])

    result = RevisaoService(repo).build_revisao()
    variavel = next(t for t in result["transactions"] if t["category"] == CATEGORIA_NAO_CATEGORIZADO)
    assert "Variável" in variavel["situacao"]
