"""
repositories/preferencia_repository.py
------------------------------------------
Acesso a dados da tabela preferencias — configurações de valor único do
usuário (chave-valor genérica), ex: limiar de alerta de despesas fixas.
"""

from pathlib import Path

from sifp.repositories.connection import DEFAULT_DB_PATH, get_connection


class PreferenciaRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    def get(self, chave: str) -> str | None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM preferencias WHERE chave = ?", (chave,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

    def set(self, chave: str, valor: str) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)",
            (chave, valor),
        )
        conn.commit()
        conn.close()
