"""
sifp/repositories/pg/import_alias_repository.py
----------------------------------------------------
Token de encaminhamento de e-mail (Módulo 18) — SaaS only, sem
equivalente em SQLite (o app pessoal do Danilo já usa upload manual
direto, não precisa desse fluxo). Um token por usuário, gerado na
primeira vez que ele acessa a tela Perfil.
"""

from __future__ import annotations

import secrets

import psycopg

__all__ = ["ImportAliasRepository"]


class ImportAliasRepository:
    def get_or_create(self, conn: psycopg.Connection) -> str:
        cur = conn.cursor()
        cur.execute("SELECT token FROM import_aliases")
        row = cur.fetchone()
        if row:
            return row[0]
        token = secrets.token_urlsafe(6)
        cur.execute("INSERT INTO import_aliases (token) VALUES (%s) RETURNING token", (token,))
        return cur.fetchone()[0]
