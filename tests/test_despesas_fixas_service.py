"""Testes de DespesaFixaRepository, PreferenciaRepository e DespesasFixasService."""

import pandas as pd
import pytest

from sifp.repositories.connection import init_db
from sifp.repositories.despesa_fixa_repository import DespesaFixaRepository
from sifp.repositories.preferencia_repository import PreferenciaRepository
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.despesas_fixas_service import DespesasFixasService


@pytest.fixture
def repos(tmp_db_path):
    init_db(tmp_db_path)
    return (
        DespesaFixaRepository(tmp_db_path),
        PreferenciaRepository(tmp_db_path),
        TransactionRepository(tmp_db_path),
    )


# ---------------------------------------------------------------------
# DespesaFixaRepository
# ---------------------------------------------------------------------
def test_create_and_get_all(repos):
    despesa_fixa_repo, _, _ = repos
    despesa_fixa_repo.create("Plano de saúde", "Saúde", 450.0, "recorrente", "2026-01-01")
    df = despesa_fixa_repo.get_all()
    assert len(df) == 1
    assert df.iloc[0]["nome"] == "Plano de saúde"
    assert df.iloc[0]["ativa"] == 1


def test_create_parcelada_stores_parcelas(repos):
    despesa_fixa_repo, _, _ = repos
    despesa_fixa_repo.create(
        "Notebook", "Compras", 300.0, "parcelada", "2026-01-01", parcela_atual=2, parcelas_totais=10
    )
    df = despesa_fixa_repo.get_all()
    assert df.iloc[0]["parcela_atual"] == 2
    assert df.iloc[0]["parcelas_totais"] == 10


def test_update_parcela_atual(repos):
    despesa_fixa_repo, _, _ = repos
    despesa_id = despesa_fixa_repo.create(
        "Notebook", "Compras", 300.0, "parcelada", "2026-01-01", parcela_atual=1, parcelas_totais=10
    )
    despesa_fixa_repo.update_parcela_atual(despesa_id, 2)
    df = despesa_fixa_repo.get_all()
    assert df.iloc[0]["parcela_atual"] == 2


def test_set_ativa_false_removes_from_default_listing(repos):
    despesa_fixa_repo, _, _ = repos
    despesa_id = despesa_fixa_repo.create("Assinatura", "Assinaturas", 50.0, "recorrente", "2026-01-01")
    despesa_fixa_repo.set_ativa(despesa_id, False)
    assert despesa_fixa_repo.get_all(apenas_ativas=True).empty
    assert len(despesa_fixa_repo.get_all(apenas_ativas=False)) == 1


def test_delete(repos):
    despesa_fixa_repo, _, _ = repos
    despesa_id = despesa_fixa_repo.create("Assinatura", "Assinaturas", 50.0, "recorrente", "2026-01-01")
    despesa_fixa_repo.delete(despesa_id)
    assert despesa_fixa_repo.get_all().empty


# ---------------------------------------------------------------------
# PreferenciaRepository
# ---------------------------------------------------------------------
def test_preferencia_get_sem_valor_retorna_none(repos):
    _, preferencia_repo, _ = repos
    assert preferencia_repo.get("limite_despesas_fixas_pct") is None


def test_preferencia_set_e_get(repos):
    _, preferencia_repo, _ = repos
    preferencia_repo.set("limite_despesas_fixas_pct", "35.0")
    assert preferencia_repo.get("limite_despesas_fixas_pct") == "35.0"


def test_preferencia_set_substitui_valor_anterior(repos):
    _, preferencia_repo, _ = repos
    preferencia_repo.set("limite_despesas_fixas_pct", "30.0")
    preferencia_repo.set("limite_despesas_fixas_pct", "40.0")
    assert preferencia_repo.get("limite_despesas_fixas_pct") == "40.0"


# ---------------------------------------------------------------------
# DespesasFixasService
# ---------------------------------------------------------------------
def _com_receita(transaction_repo):
    tx = pd.DataFrame([
        {"date": "2026-04-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-05-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-06-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
    ])
    transaction_repo.insert_new(tx)


def test_build_despesas_fixas_sem_dados(repos):
    despesa_fixa_repo, preferencia_repo, transaction_repo = repos
    svc = DespesasFixasService(despesa_fixa_repo, preferencia_repo, transaction_repo)
    result = svc.build_despesas_fixas()
    assert result["despesas"] == []
    assert result["total_mensal"] == 0.0
    assert result["pct_comprometido"] is None
    assert result["margem_mensal"] is None
    assert result["limite_alerta_pct"] is None


def test_build_despesas_fixas_calcula_total_pct_e_margem(repos):
    despesa_fixa_repo, preferencia_repo, transaction_repo = repos
    _com_receita(transaction_repo)
    despesa_fixa_repo.create("Plano de saúde", "Saúde", 450.0, "recorrente", "2026-01-01")
    despesa_fixa_repo.create(
        "Notebook", "Compras", 300.0, "parcelada", "2026-01-01", parcela_atual=3, parcelas_totais=10
    )

    svc = DespesasFixasService(despesa_fixa_repo, preferencia_repo, transaction_repo)
    result = svc.build_despesas_fixas()

    assert result["total_mensal"] == pytest.approx(750.0)
    assert result["receita_media_mensal"] == pytest.approx(5000.0)
    assert result["pct_comprometido"] == pytest.approx(15.0)
    assert result["margem_mensal"] == pytest.approx(4250.0)

    parcelada = next(d for d in result["despesas"] if d["nome"] == "Notebook")
    assert parcelada["parcelas_restantes"] == 7


def test_receita_media_mensal_ignora_mes_corrente_incompleto(repos):
    """Um salário que ainda não caiu (mês em andamento) não pode puxar
    a receita média pra baixo -- inflaria pct_comprometido artificialmente."""
    despesa_fixa_repo, preferencia_repo, transaction_repo = repos
    _com_receita(transaction_repo)  # abr/mai/jun 2026, R$5000 cada -> media 5000

    hoje = pd.Timestamp.now()
    tx_mes_atual = pd.DataFrame([{
        "date": hoje.strftime("%Y-%m-01"),
        "description": "Salario parcial",
        "value": 200.0,  # bem menor que 5000 -- só entrou uma parte até agora
        "category": "Salário/Receita",
    }])
    transaction_repo.insert_new(tx_mes_atual)

    svc = DespesasFixasService(despesa_fixa_repo, preferencia_repo, transaction_repo)
    result = svc.build_despesas_fixas()

    # se o mes corrente (com só 200) entrasse na janela de 3, a media cairia
    # bem abaixo de 5000 -- continua 5000 porque só os 3 meses fechados contam.
    assert result["receita_media_mensal"] == pytest.approx(5000.0)


def test_build_despesas_fixas_despesa_inativa_nao_conta(repos):
    despesa_fixa_repo, preferencia_repo, transaction_repo = repos
    _com_receita(transaction_repo)
    despesa_id = despesa_fixa_repo.create("Assinatura", "Assinaturas", 50.0, "recorrente", "2026-01-01")
    despesa_fixa_repo.set_ativa(despesa_id, False)

    svc = DespesasFixasService(despesa_fixa_repo, preferencia_repo, transaction_repo)
    result = svc.build_despesas_fixas()
    assert result["total_mensal"] == 0.0
    assert result["despesas"] == []


def test_build_despesas_fixas_parcelada_concluida_nao_conta_no_total(repos):
    """Achado real de auditoria: parcela_atual == parcelas_totais (todas
    as parcelas já pagas) continuava somando no total mensal comprometido
    até o usuário clicar em "Encerrar" manualmente -- a despesa some do
    orçamento de verdade, mas o sistema continuava contando ela."""
    despesa_fixa_repo, preferencia_repo, transaction_repo = repos
    _com_receita(transaction_repo)
    despesa_fixa_repo.create("Plano de saúde", "Saúde", 450.0, "recorrente", "2026-01-01")
    despesa_fixa_repo.create(
        "Notebook", "Compras", 300.0, "parcelada", "2026-01-01", parcela_atual=10, parcelas_totais=10
    )

    svc = DespesasFixasService(despesa_fixa_repo, preferencia_repo, transaction_repo)
    result = svc.build_despesas_fixas()

    assert result["total_mensal"] == pytest.approx(450.0)  # só o plano de saúde
    # continua visível na lista (pra usuário notar e encerrar), só não conta
    notebook = next(d for d in result["despesas"] if d["nome"] == "Notebook")
    assert notebook["parcelas_restantes"] == 0


def test_build_despesas_fixas_data_inicio_futura_nao_conta_no_total(repos):
    """Achado real de auditoria: uma despesa fixa com data_inicio no
    futuro (cadastrada com antecedência) já comprometia a renda do mês
    atual, antes mesmo de começar a valer."""
    despesa_fixa_repo, preferencia_repo, transaction_repo = repos
    _com_receita(transaction_repo)
    despesa_fixa_repo.create("Plano de saúde", "Saúde", 450.0, "recorrente", "2026-01-01")
    futuro = (pd.Timestamp.now() + pd.DateOffset(months=2)).strftime("%Y-%m-%d")
    despesa_fixa_repo.create("Academia nova", "Saúde", 150.0, "recorrente", futuro)

    svc = DespesasFixasService(despesa_fixa_repo, preferencia_repo, transaction_repo)
    result = svc.build_despesas_fixas()

    assert result["total_mensal"] == pytest.approx(450.0)  # só o plano de saúde
    academia = next(d for d in result["despesas"] if d["nome"] == "Academia nova")
    assert academia is not None  # continua visível na lista


def test_set_e_get_limite_alerta_pct(repos):
    despesa_fixa_repo, preferencia_repo, transaction_repo = repos
    svc = DespesasFixasService(despesa_fixa_repo, preferencia_repo, transaction_repo)
    assert svc.get_limite_alerta_pct() is None
    svc.set_limite_alerta_pct(35.0)
    assert svc.get_limite_alerta_pct() == pytest.approx(35.0)
    result = svc.build_despesas_fixas()
    assert result["limite_alerta_pct"] == pytest.approx(35.0)
