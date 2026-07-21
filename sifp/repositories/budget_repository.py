"""
repositories/budget_repository.py
------------------------------------
Acesso a dados da tabela budgets (Módulo 13 — limite de gasto mensal por
categoria). Uma linha por categoria; definir de novo o limite de uma
categoria já existente substitui o valor (não acumula histórico — é uma
configuração atual, não um snapshot como assets/daily_balances).
"""

from pathlib import Path

import pandas as pd

from sifp.repositories.connection import DEFAULT_DB_PATH, get_connection


class BudgetRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    def set_limit(self, category: str, limite_mensal: float) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO budgets (category, limite_mensal) VALUES (?, ?)",
            (category, limite_mensal),
        )
        conn.commit()
        conn.close()

    def remove_limit(self, category: str) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM budgets WHERE category = ?", (category,))
        conn.commit()
        conn.close()

    def get_all(self) -> pd.DataFrame:
        conn = self._connect()
        df = pd.read_sql_query("SELECT * FROM budgets ORDER BY category", conn)
        conn.close()
        return df

    def get_limits_dict(self) -> dict:
        """{categoria: limite_mensal} — formato conveniente pra comparar
        contra indicator_service.category_breakdown()."""
        df = self.get_all()
        return dict(zip(df["category"], df["limite_mensal"]))
