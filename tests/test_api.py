"""Testes da API REST (sifp/api) — só a camada de tradução HTTP/JSON.
A lógica em si (SummaryService) já tem sua própria suíte; aqui validamos
que o contrato HTTP (rota, status, shape do JSON) está correto."""

from fastapi.testclient import TestClient

from sifp.api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_resumo_returns_json_with_has_data_flag():
    resp = client.get("/api/resumo")
    assert resp.status_code == 200
    body = resp.json()
    assert "has_data" in body


def test_resumo_diagnostics_have_no_leftover_markdown_escaping():
    """SummaryService devolve 'R\\$' escapado (pro Streamlit) — a API
    precisa desfazer isso, senão o frontend mostra a barra invertida."""
    resp = client.get("/api/resumo")
    body = resp.json()
    if not body.get("has_data"):
        return
    for d in body["diagnostics"]:
        assert "\\$" not in d["descricao"]
        assert "\\$" not in d["explicacao"]
        assert "\\$" not in d["recomendacao"]


def test_dashboard_returns_json_with_has_data_flag():
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    assert "has_data" in resp.json()


def test_dashboard_accepts_month_query_param():
    resp = client.get("/api/dashboard?month=2026-06")
    assert resp.status_code == 200
    body = resp.json()
    if body.get("has_data"):
        assert body["selected_month"] == "2026-06"
