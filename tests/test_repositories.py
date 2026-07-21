"""
Testes dos repositories — dedup por hash, migração de schema, e a
memória de categorização por descrição (estável vs. variável).
"""

import sqlite3

import pandas as pd
import pytest

from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.connection import init_db
from sifp.repositories.transaction_repository import TransactionRepository


@pytest.fixture
def repo(tmp_db_path):
    init_db(tmp_db_path)
    return TransactionRepository(tmp_db_path)


@pytest.fixture
def balance_repo(tmp_db_path):
    init_db(tmp_db_path)
    return BalanceRepository(tmp_db_path)


def _sample_transactions():
    return pd.DataFrame(
        {
            "date": ["2026-06-01", "2026-06-02"],
            "description": ["Uber", "Mercado"],
            "value": [-10.0, -50.0],
            "category": ["Transporte", "Mercado"],
            "confidence": [0.99, 0.99],
            "bank_category": ["Transporte", "Supermercado"],
            "self_transfer": [False, False],
            "merchant": ["Uber", "Mercado XYZ"],
            "category_source": ["keyword_rule", "keyword_rule"],
        }
    )


def test_init_db_is_idempotent(tmp_db_path):
    init_db(tmp_db_path)
    init_db(tmp_db_path)  # não pode falhar na segunda chamada


def test_migration_adds_new_columns_to_old_schema(tmp_db_path):
    """Simula um banco criado antes das colunas novas existirem — a
    migração precisa adicioná-las sem apagar o que já tinha."""
    conn = sqlite3.connect(tmp_db_path)
    conn.execute(
        """
        CREATE TABLE transactions (
            tx_hash TEXT PRIMARY KEY, date TEXT, description TEXT,
            value REAL, category TEXT, confidence REAL,
            source_file TEXT, imported_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO transactions (tx_hash, date, description, value, category, confidence) "
        "VALUES ('abc', '2026-06-01', 'teste', -10.0, 'Mercado', 0.9)"
    )
    conn.commit()
    conn.close()

    init_db(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(transactions)")
    cols = {row[1] for row in cur.fetchall()}
    assert {"bank_category", "human_confirmed", "self_transfer", "merchant", "category_source"} <= cols

    cur.execute("SELECT description FROM transactions WHERE tx_hash = 'abc'")
    assert cur.fetchone()[0] == "teste"  # dado antigo preservado
    conn.close()


def test_insert_new_dedups_by_hash(repo):
    df = _sample_transactions()
    inserted_first = repo.insert_new(df, source_file="extrato1.csv")
    inserted_second = repo.insert_new(df, source_file="extrato2.csv")  # mesmo conteúdo, "outro arquivo"

    assert inserted_first == 2
    assert inserted_second == 0
    assert len(repo.get_all()) == 2


def test_bulk_update_marks_human_confirmed_and_source(repo):
    df = _sample_transactions()
    repo.insert_new(df)
    all_tx = repo.get_all()
    tx_hash = all_tx.iloc[0]["tx_hash"]

    repo.bulk_update_categories([(tx_hash, "Lazer")])

    updated = repo.get_all()
    row = updated[updated["tx_hash"] == tx_hash].iloc[0]
    assert row["category"] == "Lazer"
    assert row["human_confirmed"] == 1
    assert row["category_source"] == "human"
    assert row["confidence"] == 1.0


def test_bulk_update_to_nao_categorizado_does_not_confirm(repo):
    """
    Regressão: salvar a tela de Revisão com uma linha ainda em
    'Não categorizado' NÃO pode marcá-la como confirmada — isso é uma
    contradição (não há decisão nenhuma pra "confirmar") e faria a
    memória por descrição parar de pedir revisão pra ela para sempre,
    mesmo sem o usuário ter escolhido categoria nenhuma. Bug real: o botão
    Salvar confirmava TODAS as linhas visíveis, inclusive as que
    continuavam 'Não categorizado' só por estarem na tela.
    """
    df = _sample_transactions()
    repo.insert_new(df)
    all_tx = repo.get_all()
    tx_hash = all_tx.iloc[0]["tx_hash"]

    # simula clicar Salvar sem escolher categoria pra essa linha
    repo.bulk_update_categories([(tx_hash, "Não categorizado")])

    updated = repo.get_all()
    row = updated[updated["tx_hash"] == tx_hash].iloc[0]
    assert row["category"] == "Não categorizado"
    assert row["human_confirmed"] == 0
    assert row["category_source"] == "none"
    assert row["confidence"] == 0.0


def test_bulk_update_mixed_batch_only_confirms_real_categories(repo):
    """Um Salvar com várias linhas: só as que ganharam categoria real
    ficam confirmadas; a que ficou 'Não categorizado' não."""
    df = _sample_transactions()
    repo.insert_new(df)
    all_tx = repo.get_all()
    hash_uber = all_tx.loc[all_tx["description"] == "Uber", "tx_hash"].iloc[0]
    hash_mercado = all_tx.loc[all_tx["description"] == "Mercado", "tx_hash"].iloc[0]

    repo.bulk_update_categories([(hash_uber, "Transporte"), (hash_mercado, "Não categorizado")])

    updated = repo.get_all()
    row_uber = updated[updated["tx_hash"] == hash_uber].iloc[0]
    row_mercado = updated[updated["tx_hash"] == hash_mercado].iloc[0]
    assert row_uber["human_confirmed"] == 1
    assert row_mercado["human_confirmed"] == 0

    # e a memoria por descricao nao deve nem saber que "Mercado" existiu
    learned = repo.get_learned_categories()
    assert "Uber" in learned
    assert "Mercado" not in learned


def test_learned_categories_stable_vs_variable(repo):
    df = pd.DataFrame(
        {
            "date": ["2026-06-01", "2026-06-02", "2026-06-03"],
            "description": ["Uber", "Pix Fulano", "Pix Fulano"],
            "value": [-10.0, -200.0, -50.0],
            "category": ["Transporte", "Moradia", "Lazer"],
            "confidence": [0.99, 0.99, 0.99],
            "bank_category": ["", "", ""],
            "self_transfer": [False, False, False],
            "merchant": ["Uber", "Pix Fulano", "Pix Fulano"],
            "category_source": ["keyword_rule", "human", "human"],
        }
    )
    repo.insert_new(df)
    all_tx = repo.get_all()
    # confirma manualmente todas (como o botão Salvar faz)
    repo.bulk_update_categories(list(zip(all_tx["tx_hash"], all_tx["category"])))

    learned = repo.get_learned_categories()

    assert learned["Uber"]["variable"] is False
    assert learned["Uber"]["category"] == "Transporte"

    assert learned["Pix Fulano"]["variable"] is True
    assert learned["Pix Fulano"]["category"] is None
    assert dict(learned["Pix Fulano"]["history"]) == {"Moradia": 1, "Lazer": 1}


def test_get_training_data_excludes_nao_categorizado(repo):
    df = _sample_transactions()
    df.loc[len(df)] = {
        "date": "2026-06-03", "description": "Desconhecido", "value": -5.0,
        "category": "Não categorizado", "confidence": 0.0, "bank_category": "",
        "self_transfer": False, "merchant": "", "category_source": "none",
    }
    repo.insert_new(df)

    training = repo.get_training_data()
    assert "Não categorizado" not in training["category"].values
    assert len(training) == 2


def test_balance_repository_upsert_by_date(balance_repo):
    df1 = pd.DataFrame({"date": ["2026-06-01 23:59"], "balance": [100.0]})
    balance_repo.insert_many(df1, source_file="a.xls")
    df2 = pd.DataFrame({"date": ["2026-06-01 23:59"], "balance": [999.0]})  # mesma data, valor novo
    balance_repo.insert_many(df2, source_file="b.xls")

    result = balance_repo.get_all()
    assert len(result) == 1
    assert result.iloc[0]["balance"] == pytest.approx(999.0)
