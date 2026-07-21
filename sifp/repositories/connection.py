"""
repositories/connection.py
----------------------------
Conexão SQLite e schema/migrações. Único lugar do sistema que sabe que o
banco hoje é SQLite — trocar por PostgreSQL no futuro (Módulo 5) significa
mexer só aqui e nos repositories, nunca em services/intelligence/UI.
"""

import os
import sqlite3
from pathlib import Path

_LOCAL_DB_PATH = Path(__file__).resolve().parents[2] / "financas.db"

# SIFP_DB_PATH permite apontar pro caminho de um volume persistente em
# produção (ex: Railway) sem mexer em nenhum call site — todo repository
# já usa DEFAULT_DB_PATH como valor padrão do parâmetro db_path.
DEFAULT_DB_PATH = Path(os.environ["SIFP_DB_PATH"]) if os.environ.get("SIFP_DB_PATH") else _LOCAL_DB_PATH

# Migrações leves: cada entrada é (coluna, DDL). Aplicadas apenas se a
# coluna ainda não existir, então bancos antigos ganham as colunas novas
# sem perder dados já gravados.
_TRANSACTIONS_MIGRATIONS = {
    "bank_category": "ALTER TABLE transactions ADD COLUMN bank_category TEXT DEFAULT ''",
    "human_confirmed": "ALTER TABLE transactions ADD COLUMN human_confirmed INTEGER NOT NULL DEFAULT 0",
    "self_transfer": "ALTER TABLE transactions ADD COLUMN self_transfer INTEGER NOT NULL DEFAULT 0",
    "merchant": "ALTER TABLE transactions ADD COLUMN merchant TEXT DEFAULT ''",
    "category_source": "ALTER TABLE transactions ADD COLUMN category_source TEXT DEFAULT ''",
}

_ASSETS_MIGRATIONS = {
    "benchmark_mes_pct": "ALTER TABLE assets ADD COLUMN benchmark_mes_pct REAL",
    "benchmark_ano_pct": "ALTER TABLE assets ADD COLUMN benchmark_ano_pct REAL",
    "benchmark_12m_pct": "ALTER TABLE assets ADD COLUMN benchmark_12m_pct REAL",
}


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path, check_same_thread=False)


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Cria as tabelas caso ainda não existam e aplica migrações leves."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            tx_hash TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            value REAL NOT NULL,
            category TEXT DEFAULT 'Não categorizado',
            confidence REAL DEFAULT 0.0,
            source_file TEXT,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute("PRAGMA table_info(transactions)")
    existing_cols = {row[1] for row in cur.fetchall()}
    for col, ddl in _TRANSACTIONS_MIGRATIONS.items():
        if col not in existing_cols:
            cur.execute(ddl)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_balances (
            date TEXT PRIMARY KEY,
            balance REAL NOT NULL,
            source_file TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            position_key TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            identificador TEXT NOT NULL,
            tipo TEXT,
            instituicao TEXT,
            data_referencia TEXT NOT NULL,
            quantidade REAL,
            cotacao REAL,
            saldo_bruto REAL DEFAULT 0.0,
            saldo_liquido REAL DEFAULT 0.0,
            rentabilidade_mes_pct REAL,
            rentabilidade_ano_pct REAL,
            rentabilidade_12m_pct REAL,
            benchmark TEXT,
            source_file TEXT,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute("PRAGMA table_info(assets)")
    existing_asset_cols = {row[1] for row in cur.fetchall()}
    for col, ddl in _ASSETS_MIGRATIONS.items():
        if col not in existing_asset_cols:
            cur.execute(ddl)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS budgets (
            category TEXT PRIMARY KEY,
            limite_mensal REAL NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            valor_necessario REAL NOT NULL,
            valor_acumulado REAL NOT NULL DEFAULT 0.0,
            prazo TEXT NOT NULL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()
