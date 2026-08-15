"""Teste dedicado do ponto mais crítico de segurança do recurso de
assessor (ver plano em `sifp/api/auth.py::get_db`): o header
`X-Sifra-Visualizar-Cliente` troca a identidade da conexão Postgres pra
do cliente, reaproveitando as ~20 rotas existentes sem duplicá-las. Um
bug aqui vira vazamento (ou escrita indevida) de dado financeiro entre
clientes -- por isso este teste chama `get_db` diretamente (sem HTTP,
sem Postgres real) e prova, por unidade lógica, cada trava:

1. sem o header -> comportamento de sempre, ignorando tudo abaixo.
2. método não-GET + header presente -> 403 ANTES de abrir qualquer
   conexão (nem a do assessor).
3. client_id malformado -> 403 antes de qualquer conexão.
4. GET + header, mas sem vínculo aceito -> 403; só a conexão do
   assessor foi aberta (pra checar o vínculo), a do cliente nunca.
5. GET + header + vínculo aceito -> abre a conexão do CLIENTE (não a
   do assessor) pro resto da rota usar.
"""

from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

from sifp.api import auth as auth_module

ADVISOR_ID = "11111111-1111-1111-1111-111111111111"
CLIENT_ID = "22222222-2222-2222-2222-222222222222"


def _fake_scoped_transaction(chamadas):
    @contextmanager
    def _fake(user_id):
        chamadas.append(user_id)
        yield f"conn-para-{user_id}"

    return _fake


def _request(method: str) -> Mock:
    return Mock(method=method)


def test_sem_header_abre_conexao_do_proprio_usuario(monkeypatch):
    chamadas = []
    monkeypatch.setattr(auth_module, "scoped_transaction", _fake_scoped_transaction(chamadas))

    gen = auth_module.get_db(request=_request("GET"), user_id=ADVISOR_ID, visualizar_cliente=None)
    conn = next(gen)

    assert conn == f"conn-para-{ADVISOR_ID}"
    assert chamadas == [ADVISOR_ID]


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE", "PUT"])
def test_escrita_com_header_bloqueia_antes_de_abrir_qualquer_conexao(monkeypatch, method):
    chamadas = []
    monkeypatch.setattr(auth_module, "scoped_transaction", _fake_scoped_transaction(chamadas))
    monkeypatch.setattr(
        auth_module,
        "AdvisorLinkRepository",
        lambda: Mock(vinculo_aceito=Mock(return_value=True)),  # nem deveria ser chamado
    )

    gen = auth_module.get_db(request=_request(method), user_id=ADVISOR_ID, visualizar_cliente=CLIENT_ID)
    with pytest.raises(HTTPException) as exc:
        next(gen)

    assert exc.value.status_code == 403
    assert chamadas == []  # nenhuma conexão (nem a do assessor) foi aberta


def test_client_id_malformado_bloqueia_antes_de_abrir_qualquer_conexao(monkeypatch):
    chamadas = []
    monkeypatch.setattr(auth_module, "scoped_transaction", _fake_scoped_transaction(chamadas))

    gen = auth_module.get_db(request=_request("GET"), user_id=ADVISOR_ID, visualizar_cliente="nao-e-um-uuid")
    with pytest.raises(HTTPException) as exc:
        next(gen)

    assert exc.value.status_code == 403
    assert chamadas == []


def test_get_sem_vinculo_aceito_bloqueia_e_nunca_abre_conexao_do_cliente(monkeypatch):
    chamadas = []
    monkeypatch.setattr(auth_module, "scoped_transaction", _fake_scoped_transaction(chamadas))
    checagem = Mock(vinculo_aceito=Mock(return_value=False))
    monkeypatch.setattr(auth_module, "AdvisorLinkRepository", lambda: checagem)

    gen = auth_module.get_db(request=_request("GET"), user_id=ADVISOR_ID, visualizar_cliente=CLIENT_ID)
    with pytest.raises(HTTPException) as exc:
        next(gen)

    assert exc.value.status_code == 403
    # só a conexão do assessor foi aberta (pra checar o vínculo) -- a do cliente, nunca
    assert chamadas == [ADVISOR_ID]
    checagem.vinculo_aceito.assert_called_once_with(f"conn-para-{ADVISOR_ID}", ADVISOR_ID, CLIENT_ID)


def test_get_com_vinculo_aceito_abre_conexao_do_cliente_nao_do_assessor(monkeypatch):
    chamadas = []
    monkeypatch.setattr(auth_module, "scoped_transaction", _fake_scoped_transaction(chamadas))
    checagem = Mock(vinculo_aceito=Mock(return_value=True))
    monkeypatch.setattr(auth_module, "AdvisorLinkRepository", lambda: checagem)

    gen = auth_module.get_db(request=_request("GET"), user_id=ADVISOR_ID, visualizar_cliente=CLIENT_ID)
    conn = next(gen)

    assert conn == f"conn-para-{CLIENT_ID}"
    assert chamadas == [ADVISOR_ID, CLIENT_ID]


def test_assessor_nao_consegue_chutar_client_id_sem_vinculo(monkeypatch):
    """Mesmo com um client_id sintaticamente válido mas sem vínculo
    aceito de verdade, o assessor nunca consegue montar a conexão do
    cliente -- a política de RLS de advisor_links já garante que
    vinculo_aceito só enxerga vínculos onde o próprio user_id é uma das
    partes, então este teste prova o lado da aplicação: mesmo que a
    checagem retorne False (equivalente a "não achei"), a conexão do
    cliente nunca é aberta."""
    chamadas = []
    monkeypatch.setattr(auth_module, "scoped_transaction", _fake_scoped_transaction(chamadas))
    checagem = Mock(vinculo_aceito=Mock(return_value=False))
    monkeypatch.setattr(auth_module, "AdvisorLinkRepository", lambda: checagem)

    client_chutado = "99999999-9999-9999-9999-999999999999"
    gen = auth_module.get_db(request=_request("GET"), user_id=ADVISOR_ID, visualizar_cliente=client_chutado)
    with pytest.raises(HTTPException):
        next(gen)

    assert client_chutado not in chamadas
