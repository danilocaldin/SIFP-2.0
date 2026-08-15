"""
sifp/repositories/pg/advisor_link_repository.py
--------------------------------------------------
Vínculo assessor<->cliente (Módulo de assessores, SaaS only — não existe
versão SQLite, é um conceito específico do multiusuário). Mesmo padrão
dos outros repositories em pg/: recebe a conexão já escopada, nunca abre
a própria.

Ciclo de vida: pendente -> aceito -> revogado, sempre na MESMA linha
(nunca deletada — histórico de consentimento é evidência, LGPD art. 8º
§5º, ônus da prova é do controlador). Ver schema.sql para a política de
RLS e o porquê de client_id ser nullable (convite grava só o e-mail;
client_id só é preenchido quando o dono desse e-mail loga e "reivindica"
o vínculo — evita precisar da Admin API do Supabase só pra descobrir se
um e-mail já é usuário).
"""

from __future__ import annotations

import psycopg
import pandas as pd

from sifp.repositories.pg.connection import read_sql_query

__all__ = ["AdvisorLinkRepository"]


class AdvisorLinkRepository:
    def convidar(self, conn: psycopg.Connection, advisor_id: str, client_email: str) -> int:
        """Cria o convite ou, se já existir um pendente/revogado pro mesmo
        par (assessor, e-mail), reaproveita a linha em vez de duplicar --
        volta pra 'pendente', limpa aceito_em/revogado_em/revogado_por."""
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM advisor_links WHERE advisor_id = %s AND lower(client_email) = lower(%s) AND client_id IS NULL",
            (advisor_id, client_email),
        )
        existing = cur.fetchone()
        if existing:
            link_id = existing[0]
            cur.execute(
                "UPDATE advisor_links SET status = 'pendente', convidado_em = now(), "
                "aceito_em = NULL, revogado_em = NULL, revogado_por = NULL WHERE id = %s",
                (link_id,),
            )
            return link_id
        cur.execute(
            "INSERT INTO advisor_links (advisor_id, client_email) VALUES (%s, %s) RETURNING id",
            (advisor_id, client_email),
        )
        return cur.fetchone()[0]

    def claim_pending(self, conn: psycopg.Connection, client_id: str, client_email: str) -> None:
        """Roda toda vez que o cliente acessa a própria lista de vínculos:
        qualquer convite pendente pro e-mail dele (client_id ainda NULL)
        passa a apontar pra essa conta. Idempotente -- não faz nada se não
        houver convite pendente pra esse e-mail."""
        cur = conn.cursor()
        cur.execute(
            "UPDATE advisor_links SET client_id = %s WHERE lower(client_email) = lower(%s) AND client_id IS NULL",
            (client_id, client_email),
        )

    def list_as_advisor(self, conn: psycopg.Connection, advisor_id: str) -> pd.DataFrame:
        return read_sql_query(
            conn,
            "SELECT * FROM advisor_links WHERE advisor_id = %s ORDER BY convidado_em DESC",
            (advisor_id,),
        )

    def list_as_client(self, conn: psycopg.Connection, client_id: str) -> pd.DataFrame:
        return read_sql_query(
            conn,
            "SELECT * FROM advisor_links WHERE client_id = %s ORDER BY convidado_em DESC",
            (client_id,),
        )

    def get_by_id(self, conn: psycopg.Connection, link_id: int) -> dict | None:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, advisor_id, client_id, client_email, status FROM advisor_links WHERE id = %s",
            (link_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = ["id", "advisor_id", "client_id", "client_email", "status"]
        return dict(zip(cols, row))

    def aceitar(self, conn: psycopg.Connection, link_id: int, client_id: str) -> bool:
        cur = conn.cursor()
        cur.execute(
            "UPDATE advisor_links SET status = 'aceito', aceito_em = now() "
            "WHERE id = %s AND client_id = %s AND status = 'pendente'",
            (link_id, client_id),
        )
        return cur.rowcount > 0

    def revogar_pelo_assessor(self, conn: psycopg.Connection, link_id: int, advisor_id: str) -> bool:
        cur = conn.cursor()
        cur.execute(
            "UPDATE advisor_links SET status = 'revogado', revogado_em = now(), revogado_por = %s "
            "WHERE id = %s AND advisor_id = %s AND status IN ('pendente', 'aceito')",
            (advisor_id, link_id, advisor_id),
        )
        return cur.rowcount > 0

    def revogar_pelo_cliente(self, conn: psycopg.Connection, link_id: int, client_id: str) -> bool:
        cur = conn.cursor()
        cur.execute(
            "UPDATE advisor_links SET status = 'revogado', revogado_em = now(), revogado_por = %s "
            "WHERE id = %s AND client_id = %s AND status IN ('pendente', 'aceito')",
            (client_id, link_id, client_id),
        )
        return cur.rowcount > 0

    def vinculo_aceito(self, conn: psycopg.Connection, advisor_id: str, client_id: str) -> bool:
        """Usado pelo gate de autorização de 'visualizar como cliente'
        (sifp/api/auth.py::get_db) -- confirma que existe um vínculo
        aceito entre esse par antes de trocar a identidade da conexão."""
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM advisor_links WHERE advisor_id = %s AND client_id = %s AND status = 'aceito'",
            (advisor_id, client_id),
        )
        return cur.fetchone() is not None
