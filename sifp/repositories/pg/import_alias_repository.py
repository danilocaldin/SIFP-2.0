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
        # token_urlsafe(32) = 256 bits -- padrão recomendado pra token
        # opaco usado como credencial (o token FAZ PARTE do endereço de
        # e-mail de importação, então precisa ser difícil de adivinhar).
        token = secrets.token_urlsafe(32)
        # Achado real de auditoria: duas requisições concorrentes na
        # primeira visita à tela Perfil (duas abas, ou reentrância do
        # React) podiam ambas passar pelo SELECT acima vendo "sem token"
        # e ambas tentar o INSERT -- a segunda violava a constraint
        # UNIQUE em user_id e estourava 500 em vez de simplesmente
        # devolver o token que a primeira acabou de criar. ON CONFLICT
        # com um UPDATE de no-op torna isso atômico: se outra requisição
        # já ganhou a corrida, devolve o token dela (via RETURNING), não
        # o gerado aqui.
        cur.execute(
            """
            INSERT INTO import_aliases (token) VALUES (%s)
            ON CONFLICT (user_id) DO UPDATE SET token = import_aliases.token
            RETURNING token
            """,
            (token,),
        )
        return cur.fetchone()[0]

    def get_remetente_confiavel(self, conn: psycopg.Connection) -> str | None:
        cur = conn.cursor()
        cur.execute("SELECT remetente_confiavel FROM import_aliases WHERE user_id = auth.uid()")
        row = cur.fetchone()
        return row[0] if row and row[0] else None

    def resetar_remetente_confiavel(self, conn: psycopg.Connection) -> None:
        """Esquece o remetente aprendido (confiar-no-primeiro-uso) — usado
        quando o usuário muda a forma como encaminha o extrato (troca de
        e-mail, passa a usar regra automática em vez de encaminhar na mão
        etc.) e o próximo e-mail de um remetente novo passaria a ser
        bloqueado como suspeito sem essa opção."""
        conn.cursor().execute(
            "UPDATE import_aliases SET remetente_confiavel = NULL WHERE user_id = auth.uid()"
        )
