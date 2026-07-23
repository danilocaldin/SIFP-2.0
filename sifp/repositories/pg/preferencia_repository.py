"""
sifp/repositories/pg/preferencia_repository.py
---------------------------------------------------
Versão Postgres (Supabase, multiusuário) de
sifp/repositories/preferencia_repository.py — mesmo padrão dos outros
repositories em pg/.
"""

from __future__ import annotations

import psycopg

__all__ = ["PreferenciaRepository"]


class PreferenciaRepository:
    def get(self, conn: psycopg.Connection, chave: str) -> str | None:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM preferencias WHERE chave = %s", (chave,))
        row = cur.fetchone()
        return row[0] if row else None

    def set(self, conn: psycopg.Connection, chave: str, valor: str) -> None:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO preferencias (chave, valor)
            VALUES (%s, %s)
            ON CONFLICT (user_id, chave) DO UPDATE SET valor = excluded.valor
            """,
            (chave, valor),
        )
