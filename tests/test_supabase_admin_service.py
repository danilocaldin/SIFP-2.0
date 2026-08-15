"""Testes de sifp/services/supabase_admin_service.py (recurso de
assessor, Fase 4). `convidar_conta_nova` é sempre best-effort -- nenhum
destes casos deve levantar exceção, já que o vínculo em advisor_links
(fonte de verdade do convite) já foi gravado antes desta função ser
chamada. httpx.post é sempre mockado: um teste real contra a Admin API
do Supabase enviaria e-mail de verdade pra qualquer endereço novo."""

from unittest.mock import Mock

import pytest

from sifp.services import supabase_admin_service as service


@pytest.fixture(autouse=True)
def _configurado(monkeypatch):
    monkeypatch.setattr(service, "SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setattr(service, "SUPABASE_SERVICE_ROLE_KEY", "chave-de-teste")


def _fake_response(status_code: int, json_body: dict | None = None, text: str = ""):
    resp = Mock()
    resp.status_code = status_code
    resp.text = text
    if json_body is None:
        resp.json.side_effect = ValueError("não é JSON")
    else:
        resp.json.return_value = json_body
    return resp


def test_email_ja_existente_nao_levanta_excecao(monkeypatch):
    monkeypatch.setattr(
        service.httpx, "post", Mock(return_value=_fake_response(422, {"error_code": "email_exists"}))
    )
    service.convidar_conta_nova("ja-existe@sifra.dev")  # não deve levantar


def test_convite_bem_sucedido_nao_levanta_excecao(monkeypatch):
    monkeypatch.setattr(service.httpx, "post", Mock(return_value=_fake_response(200, {})))
    service.convidar_conta_nova("novo@sifra.dev")  # não deve levantar


def test_sem_chave_configurada_nao_chama_a_api(monkeypatch):
    monkeypatch.setattr(service, "SUPABASE_SERVICE_ROLE_KEY", "")
    post_mock = Mock()
    monkeypatch.setattr(service.httpx, "post", post_mock)
    service.convidar_conta_nova("qualquer@sifra.dev")
    post_mock.assert_not_called()


def test_erro_de_rede_nao_levanta_excecao(monkeypatch):
    import httpx

    monkeypatch.setattr(service.httpx, "post", Mock(side_effect=httpx.ConnectError("falhou")))
    service.convidar_conta_nova("qualquer@sifra.dev")  # não deve levantar


def test_resposta_inesperada_nao_levanta_excecao(monkeypatch):
    monkeypatch.setattr(service.httpx, "post", Mock(return_value=_fake_response(500, text="erro interno")))
    service.convidar_conta_nova("qualquer@sifra.dev")  # não deve levantar


def test_erro_422_com_outro_error_code_nao_levanta_excecao(monkeypatch):
    """422 por um motivo diferente de email_exists (ex: e-mail
    malformado) ainda não deve derrubar a rota -- só fica logado."""
    monkeypatch.setattr(
        service.httpx, "post", Mock(return_value=_fake_response(422, {"error_code": "validation_failed"}))
    )
    service.convidar_conta_nova("qualquer@sifra.dev")  # não deve levantar
