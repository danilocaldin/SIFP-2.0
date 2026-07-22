"""Testes da API REST (sifp/api) — só a camada de tradução HTTP/JSON.
A lógica em si (SummaryService) já tem sua própria suíte; aqui validamos
que o contrato HTTP (rota, status, shape do JSON) está correto."""

import io

import pytest
from fastapi.testclient import TestClient

from sifp.api.main import app, narrativa_service
from sifp.repositories.connection import DEFAULT_DB_PATH, get_connection
from sifp.repositories.transaction_repository import TransactionRepository, make_tx_hash
from sifp.services.narrativa_service import NarrativaIndisponivel

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


def test_relatorio_returns_json_with_has_data_flag():
    resp = client.get("/api/relatorio")
    assert resp.status_code == 200
    assert "has_data" in resp.json()


def test_relatorio_accepts_month_query_param():
    resp = client.get("/api/relatorio?month=2026-06")
    assert resp.status_code == 200
    body = resp.json()
    if body["has_data"]:
        assert "report_text" in body and isinstance(body["report_text"], str)


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


def test_upload_preview_returns_parsed_transactions_without_persisting():
    csv_content = (
        "Data;Descrição;Valor\n"
        "01/06/2026;PIX RECEBIDO JOAO SILVA;2500,00\n"
        "02/06/2026;SUPERMERCADO PAO DE ACUCAR;-345,67\n"
    ).encode("utf-8-sig")

    resp = client.post(
        "/api/upload/preview",
        files={"file": ("extrato.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["preview"]) == 2
    assert body["preview"][0]["description"] == "PIX RECEBIDO JOAO SILVA"
    assert body["preview"][0]["value"] == pytest.approx(2500.0)

    # preview não persiste nada — não deve aparecer no banco real
    all_tx = TransactionRepository().get_all()
    assert "PIX RECEBIDO JOAO SILVA" not in all_tx["description"].values


def test_upload_preview_rejects_unsupported_file():
    resp = client.post(
        "/api/upload/preview",
        files={"file": ("extrato.pdf", io.BytesIO(b"nao e um csv nem excel"), "application/pdf")},
    )
    assert resp.status_code == 400


def test_upload_persist_inserts_and_dedupes_without_corrupting_real_data():
    fake_desc = "[PYTEST] TRANSACAO TEMPORARIA DE TESTE UPLOAD"
    csv_content = f"Data;Descrição;Valor\n01/01/2000;{fake_desc};-1,23\n".encode("utf-8-sig")
    # Importador de CSV grava "%Y-%m-%d %H:%M" (mesmo formato do Excel,
    # sem hora vira 00:00) — ver comentário em btg_importer.py.
    tx_hash = make_tx_hash("2000-01-01 00:00", fake_desc, -1.23)

    try:
        resp1 = client.post(
            "/api/upload/persist",
            files={"file": ("extrato.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp1.status_code == 200
        assert resp1.json()["inseridas"] == 1

        # reimportar o mesmo extrato não duplica (dedup por tx_hash)
        resp2 = client.post(
            "/api/upload/persist",
            files={"file": ("extrato.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp2.json()["inseridas"] == 0
        assert resp2.json()["ignoradas_duplicadas"] == 1
    finally:
        conn = get_connection(DEFAULT_DB_PATH)
        conn.execute("DELETE FROM transactions WHERE tx_hash = ?", (tx_hash,))
        conn.commit()
        conn.close()

    all_tx = TransactionRepository().get_all()
    assert fake_desc not in all_tx["description"].values


def test_upload_persist_returns_revisao_pendente_for_transfer():
    # Nota: não testamos aqui o caso de "estabelecimento novo sem
    # confiança" porque este endpoint roda contra o modelo de ML REAL já
    # treinado (não um modelo vazio) -- ele pode prever alguma categoria
    # com confiança pra qualquer texto, mesmo sintético (não tem opção
    # "não sei"). Esse caso já é coberto de forma determinística em
    # test_import_service.py com um CategorizationService(model=None).
    fake_pix_desc = "Pix enviado - [PYTEST] Fulano De Tal Teste"
    csv_content = f"Data;Descrição;Valor\n01/01/2000;{fake_pix_desc};-50,00\n".encode("utf-8-sig")
    tx_hash_pix = make_tx_hash("2000-01-01 00:00", fake_pix_desc, -50.00)

    try:
        resp = client.post(
            "/api/upload/persist",
            files={"file": ("extrato.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inseridas"] == 1

        revisao = {r["description"]: r for r in body["revisao_pendente"]}
        assert fake_pix_desc in revisao
        assert revisao[fake_pix_desc]["is_transfer"] is True
        assert isinstance(revisao[fake_pix_desc]["value"], float)
    finally:
        conn = get_connection(DEFAULT_DB_PATH)
        conn.execute("DELETE FROM transactions WHERE tx_hash = ?", (tx_hash_pix,))
        conn.commit()
        conn.close()

    all_tx = TransactionRepository().get_all()
    assert not all_tx["description"].str.contains("PYTEST", na=False).any()


def test_revisao_returns_json_with_has_data_flag():
    resp = client.get("/api/revisao")
    assert resp.status_code == 200
    assert "has_data" in resp.json()


def test_revisao_lote_marks_pending_establishment_as_confirmed():
    fake_desc = "[PYTEST] ESTABELECIMENTO TEMPORARIO REVISAO LOTE"
    csv_content = f"Data;Descrição;Valor\n01/01/2000;{fake_desc};-9,99\n".encode("utf-8-sig")
    tx_hash = make_tx_hash("2000-01-01 00:00", fake_desc, -9.99)

    try:
        resp_upload = client.post(
            "/api/upload/persist",
            files={"file": ("extrato.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp_upload.json()["inseridas"] == 1

        # o modelo de ML real (já treinado) prevê ALGUMA categoria pra
        # qualquer texto, mesmo sem sentido (não tem opção "não sei") —
        # força "Não categorizado" direto no banco pra testar o endpoint
        # de lote isoladamente do que o classificador decidiu prever.
        conn_setup = get_connection(DEFAULT_DB_PATH)
        conn_setup.execute(
            "UPDATE transactions SET category = 'Não categorizado' WHERE tx_hash = ?", (tx_hash,)
        )
        conn_setup.commit()
        conn_setup.close()

        resp_lote = client.post("/api/revisao/lote", json={"description": fake_desc, "category": "Mercado"})
        assert resp_lote.status_code == 200
        assert resp_lote.json()["atualizadas"] == 1

        all_tx = TransactionRepository().get_all()
        row = all_tx[all_tx["tx_hash"] == tx_hash].iloc[0]
        assert row["category"] == "Mercado"
        assert row["human_confirmed"] == 1
    finally:
        conn = get_connection(DEFAULT_DB_PATH)
        conn.execute("DELETE FROM transactions WHERE tx_hash = ?", (tx_hash,))
        conn.commit()
        conn.close()
        # re-treina sem a linha de teste, pra não deixar o modelo salvo em
        # disco (categorizer_model.joblib) contaminado com um exemplo falso
        client.post("/api/revisao/retreinar")

    all_tx_final = TransactionRepository().get_all()
    assert fake_desc not in all_tx_final["description"].values


def test_revisao_lote_sem_pendencia_retorna_404():
    resp = client.post("/api/revisao/lote", json={"description": "Descricao Que Nao Existe Nunca", "category": "Mercado"})
    assert resp.status_code == 404


def test_revisao_confirmar_atualiza_categoria_por_tx_hash():
    fake_desc = "[PYTEST] TRANSACAO TEMPORARIA REVISAO CONFIRMAR"
    csv_content = f"Data;Descrição;Valor\n01/01/2000;{fake_desc};-4,56\n".encode("utf-8-sig")
    tx_hash = make_tx_hash("2000-01-01 00:00", fake_desc, -4.56)

    try:
        resp_upload = client.post(
            "/api/upload/persist",
            files={"file": ("extrato.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp_upload.json()["inseridas"] == 1

        resp_confirmar = client.post(
            "/api/revisao/confirmar", json={"updates": [{"tx_hash": tx_hash, "category": "Lazer"}]}
        )
        assert resp_confirmar.status_code == 200
        body = resp_confirmar.json()
        assert body["confirmadas"] == 1
        assert body["ainda_pendentes"] == 0

        all_tx = TransactionRepository().get_all()
        row = all_tx[all_tx["tx_hash"] == tx_hash].iloc[0]
        assert row["category"] == "Lazer"
    finally:
        conn = get_connection(DEFAULT_DB_PATH)
        conn.execute("DELETE FROM transactions WHERE tx_hash = ?", (tx_hash,))
        conn.commit()
        conn.close()
        client.post("/api/revisao/retreinar")

    all_tx_final = TransactionRepository().get_all()
    assert fake_desc not in all_tx_final["description"].values


def test_narrativa_returns_texto_from_mocked_service(monkeypatch):
    """Nunca chama a API real da Anthropic num teste — mocka a camada de
    serviço, testa só o contrato HTTP (rota/status/shape do JSON)."""
    monkeypatch.setattr(narrativa_service, "explicar_mes", lambda: "Explicação mockada.")
    resp = client.post("/api/narrativa")
    assert resp.status_code == 200
    assert resp.json() == {"texto": "Explicação mockada."}


def test_narrativa_returns_503_when_indisponivel(monkeypatch):
    def _raise():
        raise NarrativaIndisponivel("sem dados")

    monkeypatch.setattr(narrativa_service, "explicar_mes", _raise)
    resp = client.post("/api/narrativa")
    assert resp.status_code == 503


def test_narrativa_returns_502_on_unexpected_error(monkeypatch):
    def _raise():
        raise RuntimeError("falha de rede")

    monkeypatch.setattr(narrativa_service, "explicar_mes", _raise)
    resp = client.post("/api/narrativa")
    assert resp.status_code == 502
