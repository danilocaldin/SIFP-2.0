"""
repositories/goal_repository.py
-----------------------------------
Acesso a dados da tabela goals (Módulo 14 — metas financeiras).
"""

from pathlib import Path

import pandas as pd

from sifp.repositories.connection import DEFAULT_DB_PATH, get_connection


class GoalRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    def create(self, nome: str, valor_necessario: float, prazo: str, valor_acumulado: float = 0.0) -> int:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO goals (nome, valor_necessario, valor_acumulado, prazo) VALUES (?, ?, ?, ?)",
            (nome, valor_necessario, valor_acumulado, prazo),
        )
        conn.commit()
        goal_id = cur.lastrowid
        conn.close()
        return goal_id

    def update_progress(self, goal_id: int, valor_acumulado: float) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("UPDATE goals SET valor_acumulado = ? WHERE id = ?", (valor_acumulado, goal_id))
        conn.commit()
        conn.close()

    def delete(self, goal_id: int) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        conn.commit()
        conn.close()

    def get_all(self) -> pd.DataFrame:
        conn = self._connect()
        df = pd.read_sql_query("SELECT * FROM goals ORDER BY prazo ASC", conn)
        conn.close()
        return df
