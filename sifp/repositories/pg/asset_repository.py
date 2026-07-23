"""
sifp/repositories/pg/asset_repository.py
-------------------------------------------
Versão Postgres (Supabase, multiusuário) de
sifp/repositories/asset_repository.py — mesmo padrão do
pg/transaction_repository.py (conn recebida, sem user_id explícito nas
queries, RLS cuida do isolamento). `INSERT OR REPLACE` do SQLite vira
`ON CONFLICT ... DO UPDATE` no Postgres (upsert real, não delete+insert).
"""

from __future__ import annotations

import psycopg
import pandas as pd

from sifp.domain.models import AssetPosition
from sifp.repositories.asset_repository import _position_key

__all__ = ["AssetRepository"]


class AssetRepository:
    def insert_many(self, conn: psycopg.Connection, positions: list[AssetPosition]) -> int:
        if not positions:
            return 0
        cur = conn.cursor()
        for p in positions:
            key = _position_key(p.identificador, p.data_referencia)
            cur.execute(
                """
                INSERT INTO assets
                    (position_key, nome, identificador, tipo, instituicao, data_referencia,
                     quantidade, cotacao, saldo_bruto, saldo_liquido,
                     rentabilidade_mes_pct, rentabilidade_ano_pct, rentabilidade_12m_pct,
                     benchmark, benchmark_mes_pct, benchmark_ano_pct, benchmark_12m_pct,
                     source_file)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, position_key) DO UPDATE SET
                    nome = excluded.nome,
                    identificador = excluded.identificador,
                    tipo = excluded.tipo,
                    instituicao = excluded.instituicao,
                    data_referencia = excluded.data_referencia,
                    quantidade = excluded.quantidade,
                    cotacao = excluded.cotacao,
                    saldo_bruto = excluded.saldo_bruto,
                    saldo_liquido = excluded.saldo_liquido,
                    rentabilidade_mes_pct = excluded.rentabilidade_mes_pct,
                    rentabilidade_ano_pct = excluded.rentabilidade_ano_pct,
                    rentabilidade_12m_pct = excluded.rentabilidade_12m_pct,
                    benchmark = excluded.benchmark,
                    benchmark_mes_pct = excluded.benchmark_mes_pct,
                    benchmark_ano_pct = excluded.benchmark_ano_pct,
                    benchmark_12m_pct = excluded.benchmark_12m_pct,
                    source_file = excluded.source_file
                """,
                (
                    key, p.nome, p.identificador, p.tipo, p.instituicao, p.data_referencia,
                    p.quantidade, p.cotacao, p.saldo_bruto, p.saldo_liquido,
                    p.rentabilidade_mes_pct, p.rentabilidade_ano_pct, p.rentabilidade_12m_pct,
                    p.benchmark, p.benchmark_mes_pct, p.benchmark_ano_pct, p.benchmark_12m_pct,
                    p.source_file,
                ),
            )
        return len(positions)

    def get_all(self, conn: psycopg.Connection) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM assets ORDER BY data_referencia DESC", conn, parse_dates=["data_referencia"]
        )

    def get_latest_positions(self, conn: psycopg.Connection) -> pd.DataFrame:
        """Última posição conhecida de cada ativo (por identificador) —
        usado para o patrimônio atual, em vez de somar todo o histórico."""
        all_positions = self.get_all(conn)
        if all_positions.empty:
            return all_positions
        return (
            all_positions.sort_values("data_referencia")
            .groupby("identificador", as_index=False)
            .tail(1)
            .reset_index(drop=True)
        )
