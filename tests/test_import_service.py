"""
Teste de integração do ImportService: arquivo sintético -> importer ->
motor de relacionamento -> categorização -> repositories. Cobre o fluxo
completo que a UI (app.py) dispara ao clicar em "Processar e Categorizar".
"""

import pytest

from sifp.domain.categories import SELF_TRANSFER_CATEGORY
from sifp.importers.btg_importer import BTGImporter
from sifp.intelligence.categorization import CategorizationService
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.connection import init_db
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.import_service import ImportService
from tests.conftest import FakeUploadedFile


@pytest.fixture
def import_service(tmp_db_path):
    init_db(tmp_db_path)
    return ImportService(
        importers=[BTGImporter()],
        categorization=CategorizationService(model=None),
        transaction_repo=TransactionRepository(tmp_db_path),
        balance_repo=BalanceRepository(tmp_db_path),
    )


def test_full_import_flow_persists_transactions_and_balances(import_service, sample_btg_xlsx_bytes):
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    summary = import_service.import_and_persist(upload)

    assert summary["inseridas"] == 6
    assert summary["saldos_gravados"] == 3

    all_tx = import_service.transaction_repo.get_all()
    assert len(all_tx) == 6
    # merchant foi preenchido pelo motor de relacionamento
    assert (all_tx["merchant"] != "").all()


def test_self_transfer_transactions_get_correct_category(import_service, sample_btg_xlsx_bytes):
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    import_service.import_and_persist(upload)

    all_tx = import_service.transaction_repo.get_all()
    self_transfers = all_tx[all_tx["self_transfer"] == 1]
    assert len(self_transfers) == 2
    assert (self_transfers["category"] == SELF_TRANSFER_CATEGORY).all()


def test_reimport_same_file_does_not_duplicate(import_service, sample_btg_xlsx_bytes):
    upload1 = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    import_service.import_and_persist(upload1)

    upload2 = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    summary2 = import_service.import_and_persist(upload2)

    assert summary2["inseridas"] == 0
    assert summary2["ignoradas_duplicadas"] == 6


def test_unknown_importer_raises_value_error(import_service):
    upload = FakeUploadedFile(b"dados", "extrato.ofx")
    with pytest.raises(ValueError):
        import_service.parse(upload)


def test_revisao_pendente_inclui_transferencia_para_terceiro_mas_nao_self_transfer(
    import_service, sample_btg_xlsx_bytes
):
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    summary = import_service.import_and_persist(upload)

    revisao = {r["description"]: r for r in summary["revisao_pendente"]}
    # Pix pra "Maria Jose Vieira" (terceiro) -> precisa perguntar
    pix_terceiro = next(r for d, r in revisao.items() if "Maria Jose Vieira" in d)
    assert pix_terceiro["is_transfer"] is True

    # as duas linhas de transferência entre contas do próprio titular
    # (self_transfer) não devem aparecer na fila -- já resolvidas com certeza
    assert not any("Transferência" in d and "Maria" not in d for d in revisao)


def test_revisao_pendente_inclui_estabelecimento_sem_confianca(import_service, sample_btg_xlsx_bytes):
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    summary = import_service.import_and_persist(upload)

    all_tx = import_service.transaction_repo.get_all()
    pendentes_reais = all_tx[all_tx["category"] == "Não categorizado"]

    revisao_descricoes = {r["description"] for r in summary["revisao_pendente"]}
    for desc in pendentes_reais["description"]:
        assert desc in revisao_descricoes


def test_revisao_pendente_inclui_estabelecimento_novo_mesmo_com_regra_confiante(
    import_service, sample_btg_xlsx_bytes
):
    """Uma regra de palavra-chave (ex: "UBER" -> Transporte) é confiante,
    mas isso não significa que o usuário já confirmou essa categoria pra
    esse estabelecimento específico -- a primeira ocorrência sempre entra
    na fila de revisão, pra dar chance de corrigir antes de virar hábito
    silencioso (ver categorization.py sobre "bar" -> Alimentação vs Lazer)."""
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    summary = import_service.import_and_persist(upload)

    revisao_descricoes = {r["description"] for r in summary["revisao_pendente"]}
    assert any("Uber" in d for d in revisao_descricoes), revisao_descricoes


def test_revisao_pendente_nao_inclui_estabelecimento_ja_aprendido(
    import_service, sample_btg_xlsx_bytes
):
    """Depois que o usuário confirma manualmente a categoria de uma
    descrição (vira LEARNED_STABLE), uma nova transação com a mesma
    descrição não deve pedir revisão de novo -- só a primeira vez."""
    upload1 = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    import_service.import_and_persist(upload1)

    all_tx = import_service.transaction_repo.get_all()
    uber_hash = all_tx.loc[all_tx["description"].str.contains("Uber"), "tx_hash"].iloc[0]
    uber_desc = all_tx.loc[all_tx["description"].str.contains("Uber"), "description"].iloc[0]
    import_service.transaction_repo.bulk_update_categories([(uber_hash, "Transporte")])

    import pandas as pd

    nova_df = pd.DataFrame(
        [{"date": "2026-07-01 10:00", "description": uber_desc, "value": -9.99, "self_transfer": False}]
    )
    balances_vazio = pd.DataFrame(columns=["date", "balance"])
    summary2 = import_service.persist(nova_df, balances_vazio, source_file="extrato2.xlsx")

    revisao_descricoes = {r["description"] for r in summary2["revisao_pendente"]}
    assert uber_desc not in revisao_descricoes


def test_revisao_pendente_vazia_quando_tudo_ja_existia(import_service, sample_btg_xlsx_bytes):
    upload1 = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    import_service.import_and_persist(upload1)

    upload2 = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    summary2 = import_service.import_and_persist(upload2)

    assert summary2["revisao_pendente"] == []
