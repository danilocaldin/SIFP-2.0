"""
sifp/api/auth.py
-----------------
Autenticação do SaaS multiusuário: valida o JWT que o Supabase Auth emite
pro usuário logado (enviado pelo frontend em `Authorization: Bearer <jwt>`)
e expõe a dependency que toda rota de dado do usuário deve usar:

    @app.get("/api/algo")
    def algo(conn = Depends(get_db)):
        ...

`get_db` devolve uma conexão Postgres já escopada pra esse usuário via Row
Level Security (ver sifp/repositories/pg/connection.py). Nunca abra uma
conexão própria numa rota de dado do usuário — é assim que a RLS deixaria
de ser aplicada por engano.

O projeto Supabase deste app assina os tokens com uma chave assimétrica
(ES256), não um segredo compartilhado — por isso validamos contra a chave
pública do JWKS do próprio projeto (`PyJWKClient`, que já cacheia e
re-busca sozinho se o `kid` mudar), sem guardar nenhum segredo aqui.
"""

from __future__ import annotations

import os
from typing import Iterator

import jwt
import psycopg
from fastapi import Depends, Header, HTTPException

from sifp.repositories.pg.connection import scoped_transaction

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
_jwk_client = jwt.PyJWKClient(_JWKS_URL) if SUPABASE_URL else None


def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    token = authorization.removeprefix("Bearer ").strip()

    if _jwk_client is None:
        raise HTTPException(status_code=503, detail="Autenticação não configurada.")

    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Faça login novamente.")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Sessão inválida.")
    return user_id


def get_db(user_id: str = Depends(get_current_user_id)) -> Iterator[psycopg.Connection]:
    with scoped_transaction(user_id) as conn:
        yield conn
