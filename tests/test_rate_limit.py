"""Testes de sifp/api/rate_limit.py -- rate limiting simples por usuário
usado em /chat, /narrativa, upload e PDF (melhoria viável da 3ª
varredura). _checar_limite é testada direto (lógica pura de janela
deslizante); um teste de integração leve confirma que rate_limiter()
funciona como dependency real do FastAPI, sem precisar do app inteiro
(sem Postgres/get_db)."""

import time

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from sifp.api import rate_limit as rl
from sifp.api.auth import get_current_user_id
from sifp.api.rate_limit import _checar_limite, rate_limiter


@pytest.fixture(autouse=True)
def _limpa_contadores():
    """_hits é um dict de módulo compartilhado -- sem limpar entre
    testes, um teste "vazaria" contagem pro seguinte que usar a mesma chave."""
    rl._hits.clear()
    yield
    rl._hits.clear()


def test_checar_limite_permite_ate_o_maximo():
    for _ in range(5):
        _checar_limite("teste:usuario-1", max_chamadas=5, janela_segundos=60)


def test_checar_limite_estoura_acima_do_maximo():
    for _ in range(5):
        _checar_limite("teste:usuario-1", max_chamadas=5, janela_segundos=60)
    with pytest.raises(HTTPException) as exc_info:
        _checar_limite("teste:usuario-1", max_chamadas=5, janela_segundos=60)
    assert exc_info.value.status_code == 429


def test_checar_limite_e_por_chave_um_usuario_nao_afeta_outro():
    for _ in range(5):
        _checar_limite("teste:usuario-1", max_chamadas=5, janela_segundos=60)
    # usuário 2 tem seu próprio contador -- não deve estourar
    _checar_limite("teste:usuario-2", max_chamadas=5, janela_segundos=60)


def test_checar_limite_libera_apos_a_janela_expirar():
    for _ in range(3):
        _checar_limite("teste:janela-curta", max_chamadas=3, janela_segundos=0.05)
    with pytest.raises(HTTPException):
        _checar_limite("teste:janela-curta", max_chamadas=3, janela_segundos=0.05)

    time.sleep(0.1)  # espera a janela de 50ms expirar

    _checar_limite("teste:janela-curta", max_chamadas=3, janela_segundos=0.05)  # não deve estourar


def test_rate_limiter_como_dependency_do_fastapi():
    """Integração leve: app FastAPI mínimo (sem Postgres/get_db), só pra
    provar que rate_limiter() funciona de verdade como Depends() -- não
    só a lógica pura de _checar_limite."""
    app = FastAPI()

    @app.post("/testado", dependencies=[Depends(rate_limiter("rota_teste", max_chamadas=2, janela_segundos=60))])
    def rota_teste():
        return {"ok": True}

    app.dependency_overrides[get_current_user_id] = lambda: "user-fixo"
    client = TestClient(app)

    assert client.post("/testado").status_code == 200
    assert client.post("/testado").status_code == 200
    resp_estourado = client.post("/testado")
    assert resp_estourado.status_code == 429
    assert "Muitas requisições" in resp_estourado.json()["detail"]
