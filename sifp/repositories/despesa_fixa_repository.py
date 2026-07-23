"""
repositories/despesa_fixa_repository.py
------------------------------------------
Acesso a dados da tabela despesas_fixas (Módulo 17 — despesas fixas
declaradas manualmente: assinatura, plano de saúde, compra parcelada).
"""

from pathlib import Path

import pandas as pd

from sifp.repositories.connection import DEFAULT_DB_PATH, get_connection


class DespesaFixaRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    def create(
        self,
        nome: str,
        categoria: str,
        valor_mensal: float,
        tipo: str,
        data_inicio: str,
        parcela_atual: int | None = None,
        parcelas_totais: int | None = None,
    ) -> int:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO despesas_fixas
                (nome, categoria, valor_mensal, tipo, data_inicio, parcela_atual, parcelas_totais)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (nome, categoria, valor_mensal, tipo, data_inicio, parcela_atual, parcelas_totais),
        )
        conn.commit()
        despesa_id = cur.lastrowid
        conn.close()
        return despesa_id

    def update_parcela_atual(self, despesa_id: int, parcela_atual: int) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("UPDATE despesas_fixas SET parcela_atual = ? WHERE id = ?", (parcela_atual, despesa_id))
        conn.commit()
        conn.close()

    def set_ativa(self, despesa_id: int, ativa: bool) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("UPDATE despesas_fixas SET ativa = ? WHERE id = ?", (1 if ativa else 0, despesa_id))
        conn.commit()
        conn.close()

    def delete(self, despesa_id: int) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM despesas_fixas WHERE id = ?", (despesa_id,))
        conn.commit()
        conn.close()

    def get_all(self, apenas_ativas: bool = True) -> pd.DataFrame:
        conn = self._connect()
        query = "SELECT * FROM despesas_fixas"
        if apenas_ativas:
            query += " WHERE ativa = 1"
        query += " ORDER BY criado_em ASC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
