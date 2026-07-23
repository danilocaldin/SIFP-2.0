"""
sifp/repositories/pg/transaction_repository.py
------------------------------------------------
Versão Postgres (Supabase, multiusuário) de
sifp/repositories/transaction_repository.py. Mesma interface pública, duas
diferenças de fundo:
  1) todo método recebe a `conn` já escopada (ver pg/connection.py) em vez
     de abrir a própria — nunca chama commit()/close(), quem administra o
     ciclo de vida da transação é o dependency de auth do FastAPI.
  2) nenhuma query filtra por usuário explicitamente — a Row Level Security
     do Postgres já faz isso (ver pg/schema.sql), e user_id nem é
     declarado nos INSERTs (default auth.uid() na própria coluna).

make_tx_hash/normalize_tx_date são funções puras (sem I/O) — reaproveitadas
da versão SQLite em vez de duplicadas.
"""

from __future__ import annotations

import psycopg
import pandas as pd

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO
from sifp.repositories.transaction_repository import make_tx_hash, normalize_tx_date

__all__ = ["TransactionRepository", "make_tx_hash", "normalize_tx_date"]


class TransactionRepository:
    def insert_new(self, conn: psycopg.Connection, df: pd.DataFrame, source_file: str = "") -> list[str]:
        """Insere transações novas; ignora as que já existem (dedup por
        hash, agora escopado por usuário via a chave primária composta
        (user_id, tx_hash)). Retorna os tx_hash efetivamente inseridos."""
        cur = conn.cursor()
        inserted_hashes: list[str] = []
        for _, row in df.iterrows():
            date_normalized = normalize_tx_date(row["date"])
            tx_hash = make_tx_hash(date_normalized, row["description"], row["value"])
            cur.execute(
                """
                INSERT INTO transactions
                    (tx_hash, date, description, value, category, confidence,
                     source_file, bank_category, self_transfer, merchant, category_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, tx_hash) DO NOTHING
                """,
                (
                    tx_hash,
                    date_normalized,
                    row["description"],
                    float(row["value"]),
                    row.get("category", CATEGORIA_NAO_CATEGORIZADO),
                    float(row.get("confidence", 0.0)),
                    source_file,
                    row.get("bank_category", "") or "",
                    bool(row.get("self_transfer", False)),
                    row.get("merchant", "") or "",
                    row.get("category_source", "") or "",
                ),
            )
            if cur.rowcount:
                inserted_hashes.append(tx_hash)
        return inserted_hashes

    def get_all(self, conn: psycopg.Connection) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM transactions ORDER BY date DESC", conn, parse_dates=["date"]
        )

    def get_training_data(self, conn: psycopg.Connection) -> pd.DataFrame:
        """Transações já classificadas manualmente, usadas para treinar o modelo de ML."""
        return pd.read_sql_query(
            """
            SELECT description, category FROM transactions
            WHERE category IS NOT NULL AND category != %s
            """,
            conn,
            params=(CATEGORIA_NAO_CATEGORIZADO,),
        )

    def update_category(self, conn: psycopg.Connection, tx_hash: str, new_category: str) -> None:
        self.bulk_update_categories(conn, [(tx_hash, new_category)])

    def bulk_update_categories(self, conn: psycopg.Connection, updates: list[tuple[str, str]]) -> None:
        """Mesma regra da versão SQLite: se a categoria final ainda é
        'Não categorizado', NÃO marca como confirmada (ver docstring
        original em sifp/repositories/transaction_repository.py)."""
        cur = conn.cursor()
        confirmed = [(cat, h) for h, cat in updates if cat != CATEGORIA_NAO_CATEGORIZADO]
        unresolved = [(cat, h) for h, cat in updates if cat == CATEGORIA_NAO_CATEGORIZADO]

        if confirmed:
            cur.executemany(
                "UPDATE transactions SET category = %s, confidence = 1.0, human_confirmed = true, "
                "category_source = 'human' WHERE tx_hash = %s",
                confirmed,
            )
        if unresolved:
            cur.executemany(
                "UPDATE transactions SET category = %s, confidence = 0.0, human_confirmed = false, "
                "category_source = 'none' WHERE tx_hash = %s",
                unresolved,
            )

    def get_learned_categories(self, conn: psycopg.Connection) -> dict:
        """Ver docstring completa na versão SQLite — mesma lógica, só a
        fonte da conexão muda."""
        df = pd.read_sql_query(
            """
            SELECT description, category, COUNT(*) as n
            FROM transactions
            WHERE human_confirmed = true
            GROUP BY description, category
            """,
            conn,
        )

        learned = {}
        for desc, group in df.groupby("description"):
            history = sorted(zip(group["category"], group["n"]), key=lambda x: x[1], reverse=True)
            if len(history) == 1:
                learned[desc] = {"category": history[0][0], "variable": False, "history": history}
            else:
                learned[desc] = {"category": None, "variable": True, "history": history}
        return learned
