"""Testes de sifp/services/supabase_admin_service.py.

`convidar_conta_nova` (recurso de assessor, Fase 4) é sempre best-effort
-- nenhum desses casos deve levantar exceção, já que o vínculo em
advisor_links (fonte de verdade do convite) já foi gravado antes desta
função ser chamada.

`excluir_conta_admin` (exclusão de conta, LGPD art. 18) é o oposto:
NUNCA best-effort -- qualquer falha tem que levantar `AdminApiIndisponivel`,
senão o usuário acredita que os dados foram apagados quando não foram.

httpx.post/delete são sempre mockados: um teste real contra a Admin API
do Supabase enviaria e-mail de verdade ou apagaria uma conta de verdade."""

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


def test_exclusao_bem_sucedida_nao_levanta_excecao(monkeypatch):
    monkeypatch.setattr(service.httpx, "delete", Mock(return_value=_fake_response(200, {})))
    service.excluir_conta_admin("algum-user-id")  # não deve levantar


def test_exclusao_de_conta_ja_inexistente_e_idempotente(monkeypatch):
    """404 (a conta já não existe) é tratado como sucesso -- cobre
    clique duplo ou uma tentativa anterior cuja resposta se perdeu."""
    monkeypatch.setattr(service.httpx, "delete", Mock(return_value=_fake_response(404, {})))
    service.excluir_conta_admin("algum-user-id")  # não deve levantar


def test_exclusao_sem_chave_configurada_levanta_excecao(monkeypatch):
    monkeypatch.setattr(service, "SUPABASE_SERVICE_ROLE_KEY", "")
    delete_mock = Mock()
    monkeypatch.setattr(service.httpx, "delete", delete_mock)
    with pytest.raises(service.AdminApiIndisponivel):
        service.excluir_conta_admin("algum-user-id")
    delete_mock.assert_not_called()


def test_exclusao_com_erro_de_rede_levanta_excecao(monkeypatch):
    import httpx

    monkeypatch.setattr(service.httpx, "delete", Mock(side_effect=httpx.ConnectError("falhou")))
    with pytest.raises(service.AdminApiIndisponivel):
        service.excluir_conta_admin("algum-user-id")


def test_exclusao_com_resposta_inesperada_levanta_excecao(monkeypatch):
    monkeypatch.setattr(service.httpx, "delete", Mock(return_value=_fake_response(500, text="erro interno")))
    with pytest.raises(service.AdminApiIndisponivel):
        service.excluir_conta_admin("algum-user-id")
