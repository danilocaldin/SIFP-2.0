"""
repositories/balance_repository.py
-------------------------------------
Acesso a dados da tabela daily_balances (saldo da conta ao final de cada
dia, extraído do extrato — usado para o gráfico de evolução do saldo).
"""

from pathlib import Path

import pandas as pd

from sifp.repositories.connection import DEFAULT_DB_PATH, get_connection


class BalanceRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    def insert_many(self, df: pd.DataFrame, source_file: str = "") -> int:
        """Insere/atualiza saldos diários (chave = data, então reimportar um
        período sobreposto atualiza o valor em vez de duplicar)."""
        if df is None or df.empty:
            return 0
        conn = self._connect()
        cur = conn.cursor()
        cur.executemany(
            "INSERT OR REPLACE INTO daily_balances (date, balance, source_file) VALUES (?, ?, ?)",
            [(row["date"], float(row["balance"]), source_file) for _, row in df.iterrows()],
        )
        conn.commit()
        conn.close()
        return len(df)

    def get_all(self) -> pd.DataFrame:
        conn = self._connect()
        df = pd.read_sql_query(
            "SELECT * FROM daily_balances ORDER BY date ASC", conn, parse_dates=["date"]
        )
        conn.close()
        return df
