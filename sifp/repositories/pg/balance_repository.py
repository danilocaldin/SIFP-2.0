"""
sifp/repositories/pg/balance_repository.py
---------------------------------------------
Versão Postgres (Supabase, multiusuário) de
sifp/repositories/balance_repository.py — mesmo padrão dos outros
repositories em pg/.
"""

from __future__ import annotations

import psycopg
import pandas as pd

__all__ = ["BalanceRepository"]


class BalanceRepository:
    def insert_many(self, conn: psycopg.Connection, df: pd.DataFrame, source_file: str = "") -> int:
        """Insere/atualiza saldos diários (chave = (user_id, date), então
        reimportar um período sobreposto atualiza o valor em vez de duplicar)."""
        if df is None or df.empty:
            return 0
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT INTO daily_balances (date, balance, source_file)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, date) DO UPDATE SET
                balance = excluded.balance,
                source_file = excluded.source_file
            """,
            [(row["date"], float(row["balance"]), source_file) for _, row in df.iterrows()],
        )
        return len(df)

    def get_all(self, conn: psycopg.Connection) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM daily_balances ORDER BY date ASC", conn, parse_dates=["date"]
        )
