"""
sifp/repositories/pg/despesa_fixa_repository.py
---------------------------------------------------
Versão Postgres (Supabase, multiusuário) de
sifp/repositories/despesa_fixa_repository.py — mesmo padrão dos outros
repositories em pg/.
"""

from __future__ import annotations

import psycopg
import pandas as pd

__all__ = ["DespesaFixaRepository"]


class DespesaFixaRepository:
    def create(
        self,
        conn: psycopg.Connection,
        nome: str,
        categoria: str,
        valor_mensal: float,
        tipo: str,
        data_inicio: str,
        parcela_atual: int | None = None,
        parcelas_totais: int | None = None,
    ) -> int:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO despesas_fixas
                (nome, categoria, valor_mensal, tipo, data_inicio, parcela_atual, parcelas_totais)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (nome, categoria, valor_mensal, tipo, data_inicio, parcela_atual, parcelas_totais),
        )
        return cur.fetchone()[0]

    def update_parcela_atual(self, conn: psycopg.Connection, despesa_id: int, parcela_atual: int) -> None:
        cur = conn.cursor()
        cur.execute("UPDATE despesas_fixas SET parcela_atual = %s WHERE id = %s", (parcela_atual, despesa_id))

    def set_ativa(self, conn: psycopg.Connection, despesa_id: int, ativa: bool) -> None:
        cur = conn.cursor()
        cur.execute("UPDATE despesas_fixas SET ativa = %s WHERE id = %s", (ativa, despesa_id))

    def delete(self, conn: psycopg.Connection, despesa_id: int) -> None:
        cur = conn.cursor()
        cur.execute("DELETE FROM despesas_fixas WHERE id = %s", (despesa_id,))

    def get_all(self, conn: psycopg.Connection, apenas_ativas: bool = True) -> pd.DataFrame:
        query = "SELECT * FROM despesas_fixas"
        if apenas_ativas:
            query += " WHERE ativa = true"
        query += " ORDER BY criado_em ASC"
        return pd.read_sql_query(query, conn)
