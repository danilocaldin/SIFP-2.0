"""Testes de sifp/api/routes_saas.py — cobertura básica que não depende
de Postgres: as 33 rotas do SaaS (prefixo /api/v2) vivem atrás da mesma
dependency `get_db` (auth.py), que sempre roda ANTES de qualquer conexão
ou validação de corpo/query — então dá pra provar que cada rota exige
login sem precisar de um Postgres real (a suíte inteira roda hoje só
contra SQLite, ver test_api.py). Testes de RLS/isolamento entre usuários
exigem um Postgres real e ficam fora do escopo desta suíte."""

import pytest
from fastapi.testclient import TestClient

from sifp.api.main import app

client = TestClient(app)


def _iter_all_routes(routes):
    """Achata a árvore de rotas do FastAPI/Starlette recursivamente --
    rotas incluídas via app.include_router() não aparecem como APIRoute
    direto em app.routes nesta versão do Starlette, e sim envelopadas
    num objeto que guarda o APIRouter original em `.original_router`."""
    for route in routes:
        sub_router = getattr(route, "original_router", None)
        if sub_router is not None:
            yield from _iter_all_routes(sub_router.routes)
        else:
            yield route


def _saas_routes():
    routes = []
    for route in _iter_all_routes(app.routes):
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        if not path.startswith("/api/v2") or not methods:
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            routes.append((method, path))
    return sorted(routes)


SAAS_ROUTES = _saas_routes()


def test_ha_rotas_v2_suficientes_pra_cobertura_valer_a_pena():
    # trava de sanidade: se a extração de rotas quebrar silenciosamente
    # (ex: prefixo mudou), o parametrize abaixo rodaria vazio e passaria
    # sem testar nada -- essa asserção garante que isso não acontece.
    assert len(SAAS_ROUTES) >= 30


@pytest.mark.parametrize("method,path", SAAS_ROUTES)
def test_rota_saas_sem_token_retorna_401(method, path):
    url = path
    for segment in path.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            url = url.replace(segment, "valor-qualquer", 1)
    resp = client.request(method, url)
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", SAAS_ROUTES)
def test_rota_saas_com_header_sem_bearer_retorna_401(method, path):
    url = path
    for segment in path.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            url = url.replace(segment, "valor-qualquer", 1)
    resp = client.request(method, url, headers={"Authorization": "token-sem-prefixo-bearer"})
    assert resp.status_code == 401


def test_rota_saas_com_token_invalido_retorna_401():
    resp = client.get("/api/v2/resumo", headers={"Authorization": "Bearer token.completamente.invalido"})
    assert resp.status_code == 401
