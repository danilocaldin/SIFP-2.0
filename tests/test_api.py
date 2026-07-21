"""Testes da API REST (sifp/api) — só a camada de tradução HTTP/JSON.
A lógica em si (SummaryService) já tem sua própria suíte; aqui validamos
que o contrato HTTP (rota, status, shape do JSON) está correto."""

import pytest
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


def test_patrimonio_returns_json_with_has_data_flag():
    resp = client.get("/api/patrimonio")
    assert resp.status_code == 200
    assert "has_data" in resp.json()


def test_patrimonio_import_rejects_non_pdf():
    resp = client.post(
        "/api/patrimonio/import",
        files={"file": ("extrato.txt", b"nao e um pdf", "text/plain")},
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


def test_patrimonio_import_rejects_unparseable_pdf():
    """Bytes que nao formam um PDF de verdade: precisa falhar limpo (400),
    sem nunca chegar perto de escrever no banco real."""
    resp = client.post(
        "/api/patrimonio/import",
        files={"file": ("extrato.pdf", b"isso nao e um pdf valido", "application/pdf")},
    )
    assert resp.status_code == 400


def test_projecoes_returns_json_with_has_data_flag():
    resp = client.get("/api/projecoes")
    assert resp.status_code == 200
    assert "has_data" in resp.json()


def test_projecoes_rejects_invalid_horizonte():
    resp = client.get("/api/projecoes?horizonte=7")
    assert resp.status_code == 400


def test_orcamento_returns_categorias_sugestoes_limites():
    resp = client.get("/api/orcamento")
    assert resp.status_code == 200
    body = resp.json()
    assert "categorias" in body and "sugestoes" in body and "limites" in body


def test_criar_e_remover_limite_de_orcamento():
    """Usa uma categoria real da lista padrão, mas restaura o estado
    original no final (mesmo se a asserção falhar) — a API roda contra o
    banco de dados real, e essa categoria pode já ter um limite de
    verdade definido pelo usuário; nunca deve ficar perdido."""
    categorias = client.get("/api/orcamento").json()["categorias"]
    categoria = categorias[0]
    limites_antes = {l["category"]: l["limite_mensal"] for l in client.get("/api/orcamento").json()["limites"]}
    valor_original = limites_antes.get(categoria)

    try:
        resp = client.post("/api/orcamento/limites", json={"category": categoria, "valor": 123.45})
        assert resp.status_code == 200

        limites = client.get("/api/orcamento").json()["limites"]
        assert any(l["category"] == categoria and l["limite_mensal"] == pytest.approx(123.45) for l in limites)
    finally:
        if valor_original is None:
            client.delete(f"/api/orcamento/limites/{categoria}")
        else:
            client.post("/api/orcamento/limites", json={"category": categoria, "valor": valor_original})


def test_criar_limite_com_valor_invalido_e_rejeitado():
    resp = client.post("/api/orcamento/limites", json={"category": "Mercado", "valor": 0})
    assert resp.status_code == 400


def test_ciclo_completo_de_meta():
    resp = client.post(
        "/api/metas",
        json={"nome": "[pytest] meta temporaria", "valor_necessario": 1000.0, "prazo": "2030-01-01"},
    )
    assert resp.status_code == 200
    goal_id = resp.json()["id"]

    try:
        metas = client.get("/api/metas").json()
        assert any(m["id"] == goal_id for m in metas)

        resp_patch = client.patch(f"/api/metas/{goal_id}", json={"valor_acumulado": 500.0})
        assert resp_patch.status_code == 200

        metas_atualizadas = client.get("/api/metas").json()
        meta = next(m for m in metas_atualizadas if m["id"] == goal_id)
        assert meta["valor_acumulado"] == pytest.approx(500.0)
    finally:
        resp_delete = client.delete(f"/api/metas/{goal_id}")
        assert resp_delete.status_code == 200
        metas_finais = client.get("/api/metas").json()
        assert not any(m["id"] == goal_id for m in metas_finais)


def test_criar_meta_com_dados_invalidos_e_rejeitada():
    resp = client.post("/api/metas", json={"nome": "", "valor_necessario": 100.0, "prazo": "2030-01-01"})
    assert resp.status_code == 400
