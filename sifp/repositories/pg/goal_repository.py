"""
sifp/repositories/pg/goal_repository.py
------------------------------------------
Versão Postgres (Supabase, multiusuário) de
sifp/repositories/goal_repository.py — mesmo padrão dos outros
repositories em pg/. `id` continua uma identidade global (não composta com
user_id) porque a RLS já garante que um usuário nunca acha/edita a linha
de outro mesmo sabendo o id — simplifica update_progress/delete, que
continuam recebendo só o id.
"""

from __future__ import annotations

import psycopg
import pandas as pd

__all__ = ["GoalRepository"]


class GoalRepository:
    def create(
        self, conn: psycopg.Connection, nome: str, valor_necessario: float, prazo: str, valor_acumulado: float = 0.0
    ) -> int:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO goals (nome, valor_necessario, valor_acumulado, prazo) VALUES (%s, %s, %s, %s) RETURNING id",
            (nome, valor_necessario, valor_acumulado, prazo),
        )
        return cur.fetchone()[0]

    def update_progress(self, conn: psycopg.Connection, goal_id: int, valor_acumulado: float) -> None:
        cur = conn.cursor()
        cur.execute("UPDATE goals SET valor_acumulado = %s WHERE id = %s", (valor_acumulado, goal_id))

    def delete(self, conn: psycopg.Connection, goal_id: int) -> None:
        cur = conn.cursor()
        cur.execute("DELETE FROM goals WHERE id = %s", (goal_id,))

    def get_all(self, conn: psycopg.Connection) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM goals ORDER BY prazo ASC", conn)
