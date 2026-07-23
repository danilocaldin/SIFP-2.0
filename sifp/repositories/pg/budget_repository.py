"""
sifp/repositories/pg/budget_repository.py
--------------------------------------------
Versão Postgres (Supabase, multiusuário) de
sifp/repositories/budget_repository.py — mesmo padrão dos outros
repositories em pg/.
"""

from __future__ import annotations

import psycopg
import pandas as pd

__all__ = ["BudgetRepository"]


class BudgetRepository:
    def set_limit(self, conn: psycopg.Connection, category: str, limite_mensal: float) -> None:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO budgets (category, limite_mensal)
            VALUES (%s, %s)
            ON CONFLICT (user_id, category) DO UPDATE SET limite_mensal = excluded.limite_mensal
            """,
            (category, limite_mensal),
        )

    def remove_limit(self, conn: psycopg.Connection, category: str) -> None:
        cur = conn.cursor()
        cur.execute("DELETE FROM budgets WHERE category = %s", (category,))

    def get_all(self, conn: psycopg.Connection) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM budgets ORDER BY category", conn)

    def get_limits_dict(self, conn: psycopg.Connection) -> dict:
        """{categoria: limite_mensal} — formato conveniente pra comparar
        contra indicator_service.category_breakdown()."""
        df = self.get_all(conn)
        return dict(zip(df["category"], df["limite_mensal"]))
