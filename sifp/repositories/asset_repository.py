"""
repositories/asset_repository.py
-----------------------------------
Acesso a dados da tabela assets (posições patrimoniais — Módulo 6).
Cada linha é um snapshot: mesmo ativo, datas de referência diferentes,
viram o histórico mensal (Módulo 8). A chave de dedup é
(identificador, data_referencia) — reimportar o mesmo extrato atualiza
o snapshot em vez de duplicar.
"""

import hashlib
from pathlib import Path

import pandas as pd

from sifp.domain.models import AssetPosition
from sifp.repositories.connection import DEFAULT_DB_PATH, get_connection


def _position_key(identificador: str, data_referencia: str) -> str:
    return hashlib.md5(f"{identificador}|{data_referencia}".encode("utf-8")).hexdigest()


class AssetRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    def insert_many(self, positions: list[AssetPosition]) -> int:
        if not positions:
            return 0
        conn = self._connect()
        cur = conn.cursor()
        for p in positions:
            key = _position_key(p.identificador, p.data_referencia)
            cur.execute(
                """
                INSERT OR REPLACE INTO assets
                    (position_key, nome, identificador, tipo, instituicao, data_referencia,
                     quantidade, cotacao, saldo_bruto, saldo_liquido,
                     rentabilidade_mes_pct, rentabilidade_ano_pct, rentabilidade_12m_pct,
                     benchmark, benchmark_mes_pct, benchmark_ano_pct, benchmark_12m_pct,
                     source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key, p.nome, p.identificador, p.tipo, p.instituicao, p.data_referencia,
                    p.quantidade, p.cotacao, p.saldo_bruto, p.saldo_liquido,
                    p.rentabilidade_mes_pct, p.rentabilidade_ano_pct, p.rentabilidade_12m_pct,
                    p.benchmark, p.benchmark_mes_pct, p.benchmark_ano_pct, p.benchmark_12m_pct,
                    p.source_file,
                ),
            )
        conn.commit()
        conn.close()
        return len(positions)

    def get_all(self) -> pd.DataFrame:
        conn = self._connect()
        df = pd.read_sql_query(
            "SELECT * FROM assets ORDER BY data_referencia DESC", conn, parse_dates=["data_referencia"]
        )
        conn.close()
        return df

    def get_latest_positions(self) -> pd.DataFrame:
        """Última posição conhecida de cada ativo (por identificador) —
        usado para o patrimônio atual, em vez de somar todo o histórico."""
        all_positions = self.get_all()
        if all_positions.empty:
            return all_positions
        return (
            all_positions.sort_values("data_referencia")
            .groupby("identificador", as_index=False)
            .tail(1)
            .reset_index(drop=True)
        )
