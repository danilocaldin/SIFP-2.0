"""Testes de sifp/api/auth.py — validação do JWT do Supabase Auth.

Não precisam de Postgres nem de rede: `_jwk_client` e `jwt.decode` são
substituídos por dublês, então cobrem só a lógica de sifp/api/auth.py
em si (parsing do header, decisão de status HTTP, extração de
user_id/nome) — não a verificação criptográfica real, que é
responsabilidade da biblioteca PyJWT."""

from dotenv import load_dotenv

# precisa rodar antes de importar sifp.api.auth: SUPABASE_URL (usado pra
# montar o _jwk_client no import do módulo) só é carregado do .env aqui
# -- sifp/api/main.py também chama load_dotenv(), mas se este arquivo for
# coletado/importado pelo pytest antes de main.py, sifp.api.auth entraria
# em cache no sys.modules com _jwk_client=None (SUPABASE_URL ainda não
# lido), e como o módulo já importado não é reexecutado depois, os testes
# ficariam dependentes da ordem de coleta dos arquivos de teste.
load_dotenv()

import pytest
from fastapi import HTTPException

from sifp.api import auth


def test_get_token_payload_sem_header_retorna_401():
    with pytest.raises(HTTPException) as exc:
        auth.get_token_payload(authorization=None)
    assert exc.value.status_code == 401


def test_get_token_payload_header_sem_prefixo_bearer_retorna_401():
    with pytest.raises(HTTPException) as exc:
        auth.get_token_payload(authorization="Token abc123")
    assert exc.value.status_code == 401


def test_get_token_payload_sem_jwk_client_configurado_retorna_503(monkeypatch):
    monkeypatch.setattr(auth, "_jwk_client", None)
    with pytest.raises(HTTPException) as exc:
        auth.get_token_payload(authorization="Bearer algum.token.aqui")
    assert exc.value.status_code == 503


def test_get_token_payload_token_valido_retorna_payload_decodificado(monkeypatch):
    class FakeSigningKey:
        key = "chave-publica-fake"

    class FakeJwkClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey()

    monkeypatch.setattr(auth, "_jwk_client", FakeJwkClient())
    monkeypatch.setattr(
        auth.jwt, "decode", lambda token, key, algorithms, audience: {"sub": "user-123"}
    )

    payload = auth.get_token_payload(authorization="Bearer token-valido")
    assert payload == {"sub": "user-123"}


def test_get_token_payload_assinatura_invalida_retorna_401(monkeypatch):
    class FakeJwkClient:
        def get_signing_key_from_jwt(self, token):
            raise auth.jwt.PyJWTError("assinatura inválida")

    monkeypatch.setattr(auth, "_jwk_client", FakeJwkClient())

    with pytest.raises(HTTPException) as exc:
        auth.get_token_payload(authorization="Bearer token-invalido")
    assert exc.value.status_code == 401


def test_get_token_payload_token_expirado_retorna_401(monkeypatch):
    class FakeSigningKey:
        key = "chave-publica-fake"

    class FakeJwkClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey()

    def fake_decode(token, key, algorithms, audience):
        raise auth.jwt.ExpiredSignatureError("expirado")

    monkeypatch.setattr(auth, "_jwk_client", FakeJwkClient())
    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    with pytest.raises(HTTPException) as exc:
        auth.get_token_payload(authorization="Bearer token-expirado")
    assert exc.value.status_code == 401


def test_get_current_user_id_extrai_sub_do_payload():
    assert auth.get_current_user_id(payload={"sub": "user-abc"}) == "user-abc"


def test_get_current_user_id_sem_sub_retorna_401():
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user_id(payload={})
    assert exc.value.status_code == 401


def test_get_current_user_name_extrai_full_name_e_remove_espacos():
    payload = {"user_metadata": {"full_name": "  Danilo Caldin  "}}
    assert auth.get_current_user_name(payload=payload) == "Danilo Caldin"


def test_get_current_user_name_ausente_retorna_none():
    assert auth.get_current_user_name(payload={}) is None
    assert auth.get_current_user_name(payload={"user_metadata": {}}) is None


def test_get_current_user_name_em_branco_retorna_none():
    payload = {"user_metadata": {"full_name": "   "}}
    assert auth.get_current_user_name(payload=payload) is None
