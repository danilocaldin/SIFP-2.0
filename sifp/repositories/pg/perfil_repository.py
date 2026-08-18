"""
sifp/repositories/pg/perfil_repository.py
--------------------------------------------
Dados adicionais de cadastro (CPF/nascimento/país/estado/cidade/termos),
coletados no wizard de onboarding pós-convite (Módulo de cadastro, SaaS
only — não existe versão SQLite, é conceito específico do multiusuário).
Nome e telefone ficam em user_metadata do Supabase Auth (mesmo padrão já
usado pro nome em `/perfil`); só o que precisa de garantia real de
unicidade (CPF) ou é dado estruturado de verdade vem pra cá. Mesmo padrão
dos outros repositories em pg/: recebe a conexão já escopada, nunca abre
a própria.
"""

from __future__ import annotations

import psycopg

__all__ = ["PerfilRepository"]


class PerfilRepository:
    def criar(
        self,
        conn: psycopg.Connection,
        user_id: str,
        cpf: str,
        data_nascimento: str,
        pais: str,
        estado: str,
        cidade: str,
        marketing_consent: bool,
    ) -> None:
        """Levanta `psycopg.errors.UniqueViolation` se o CPF já estiver
        cadastrado em outra conta -- quem chama (routes_saas.py) captura
        e devolve um 409 amigável, em vez de deixar vazar um 500."""
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO perfis (user_id, cpf, data_nascimento, pais, estado, cidade, marketing_consent) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, cpf, data_nascimento, pais, estado, cidade, marketing_consent),
        )

    def existe(self, conn: psycopg.Connection, user_id: str) -> bool:
        """Usado pra evitar tentar gravar duas vezes se o wizard for
        reaberto por engano depois de já concluído (idempotência)."""
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM perfis WHERE user_id = %s", (user_id,))
        return cur.fetchone() is not None
