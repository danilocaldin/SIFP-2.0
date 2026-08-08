"""
sifp/api/main.py
-----------------
Camada de API REST (FastAPI) sobre os services/repositories do SIFP.
Existe só pra expor pela web o que já é validado e testado em sifp/services
e sifp/repositories — nenhuma regra de negócio nova mora aqui, só tradução
para HTTP/JSON. Consumida pelo frontend dedicado (frontend/); o app
Streamlit (app.py) continua funcionando em paralelo, chamando as MESMAS
services diretamente, sem passar pela API.

Rodar com:
    uvicorn sifp.api.main:app --reload --port 8000
"""

import logging
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from sifp.api.routes_saas import router as saas_router
from sifp.api.shared import (
    as_file_like,
    categorization_service,
    transactions_payload,
    validar_categoria,
    validar_data_iso,
    validar_mensagens_chat,
    validar_tamanho_upload,
)
from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO
from sifp.importers.btg_importer import BTGImporter
from sifp.importers.btg_investment_importer import BTGInvestmentImporter
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.despesa_fixa_repository import DespesaFixaRepository
from sifp.repositories.goal_repository import GoalRepository
from sifp.repositories.preferencia_repository import PreferenciaRepository
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.dashboard_service import DashboardService
from sifp.services.despesas_fixas_service import DespesasFixasService
from sifp.services.formatting import formatar_mes, unescape_currency
from sifp.services.chat_service import ChatIndisponivel, ChatService
from sifp.services.import_service import ImportService
from sifp.services.narrativa_service import NarrativaIndisponivel, NarrativaService
from sifp.services.orcamento_service import OrcamentoService
from sifp.services.patrimonio_service import PatrimonioService
from sifp.services.projecoes_service import ProjecoesService
from sifp.services.relatorio_service import RelatorioService
from sifp.services.revisao_service import RevisaoService
from sifp.services.summary_service import SummaryService

init_db()

transaction_repo = TransactionRepository()
balance_repo = BalanceRepository()
asset_repo = AssetRepository()
budget_repo = BudgetRepository()
goal_repo = GoalRepository()
despesa_fixa_repo = DespesaFixaRepository()
preferencia_repo = PreferenciaRepository()
investment_importer = BTGInvestmentImporter()
import_service = ImportService(
    importers=[BTGImporter()],
    categorization=categorization_service,
    transaction_repo=transaction_repo,
    balance_repo=balance_repo,
    preferencia_repo=preferencia_repo,
)
summary_service = SummaryService(
    transaction_repo, balance_repo, asset_repo, budget_repo, goal_repo, despesa_fixa_repo, preferencia_repo
)
dashboard_service = DashboardService(transaction_repo, balance_repo)
patrimonio_service = PatrimonioService(asset_repo, investment_importer)
projecoes_service = ProjecoesService(transaction_repo, asset_repo, goal_repo)
orcamento_service = OrcamentoService(transaction_repo, budget_repo)
despesas_fixas_service = DespesasFixasService(despesa_fixa_repo, preferencia_repo, transaction_repo)
relatorio_service = RelatorioService(transaction_repo, asset_repo, summary_service)
revisao_service = RevisaoService(transaction_repo)
narrativa_service = NarrativaService(summary_service, transaction_repo)
chat_service = ChatService(transaction_repo, asset_repo)


def _refresh_model() -> str:
    training_df = transaction_repo.get_training_data()
    return categorization_service.train(training_df)


# RAILWAY_ENVIRONMENT é injetada automaticamente pela Railway em toda
# implantação (não precisa configurar nada) -- ausente localmente, então
# /docs e /redoc continuam abertos em dev, mas desligados em produção
# (achado real de auditoria: expunham o schema completo da API, sem
# nenhum motivo pra estar acessível publicamente).
_em_producao = bool(os.environ.get("RAILWAY_ENVIRONMENT"))
app = FastAPI(
    title="SIFP API",
    docs_url=None if _em_producao else "/docs",
    redoc_url=None if _em_producao else "/redoc",
    openapi_url=None if _em_producao else "/openapi.json",
)
app.include_router(saas_router)

# As rotas pessoais (/api/..., sem o /v2) nunca tiveram autenticação —
# aceitável enquanto só existia o app pessoal do Danilo (a "segurança"
# era só ninguém saber a URL). Deixou de ser aceitável quando essa MESMA
# API passou a servir o SaaS também: a URL fica embutida no bundle
# público do site, então qualquer um que a descubra podia ler/apagar os
# dados financeiros reais do Danilo sem login nenhum. As rotas /api/v2/...
# (SaaS) já têm autenticação de verdade via JWT do Supabase (ver
# routes_saas.py) e ficam de fora dessa checagem. Lida do ambiente A CADA
# request (não numa constante de módulo) de propósito — deixa testável
# via monkeypatch.setenv sem precisar reimportar o módulo, e o custo de
# um os.environ.get() por request é irrelevante.


if not os.environ.get("SIFP_PERSONAL_API_KEY"):
    logger.warning(
        "SIFP_PERSONAL_API_KEY não está configurada -- as rotas pessoais (/api/...) estão "
        "respondendo sem exigir autenticação nenhuma neste processo. Se isso for produção, "
        "qualquer pessoa que descubra a URL pode ler/apagar os dados financeiros do app "
        "pessoal e queimar a chave da Anthropic via /api/chat."
    )


@app.middleware("http")
async def require_personal_api_key(request: Request, call_next):
    path = request.url.path
    is_personal_route = path.startswith("/api/") and not path.startswith("/api/v2/")
    expected_key = os.environ.get("SIFP_PERSONAL_API_KEY")
    if is_personal_route and expected_key:
        # secrets.compare_digest (não !=) -- comparação de string comum
        # sai assim que acha o primeiro caractere diferente, vazando por
        # timing quantos caracteres do início a chave tentada acertou.
        if not secrets.compare_digest(request.headers.get("X-API-Key", ""), expected_key):
            return JSONResponse(status_code=401, content={"detail": "Chave de API inválida ou ausente."})
    return await call_next(request)


# CORSMiddleware precisa ser o ÚLTIMO registrado (não o primeiro): o
# Starlette usa app.add_middleware(...) como pilha -- o último a ser
# registrado fica mais externo e roda primeiro na requisição. Registrado
# antes da checagem de chave (como estava), o preflight OPTIONS do
# navegador (que nunca manda X-API-Key -- só a requisição real manda)
# caía na checagem de chave antes de chegar no CORSMiddleware e levava
# 401 em vez de ser respondido, quebrando upload/exclusão/chat do app
# pessoal feitos pelo navegador sempre que SIFP_PERSONAL_API_KEY está
# configurada (ver test_preflight_cors_nao_e_bloqueado_pela_chave_de_api).
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


def _plain_resumo(resumo: dict) -> dict:
    """SummaryService devolve texto com 'R\\$' escapado (pensado pro
    markdown do Streamlit — ver diagnostics._brl). A API não renderiza
    markdown, então desfaz o escape antes de virar JSON, senão a barra
    invertida aparece visível no frontend."""
    if not resumo.get("has_data"):
        return resumo
    resumo = dict(resumo)
    resumo["diagnostics"] = [
        {
            **d,
            "descricao": unescape_currency(d["descricao"]),
            "explicacao": unescape_currency(d["explicacao"]),
            "recomendacao": unescape_currency(d["recomendacao"]),
        }
        for d in resumo["diagnostics"]
    ]
    return resumo


@app.get("/api/resumo")
def resumo():
    return _plain_resumo(summary_service.build_resumo(formatar_mes))


@app.post("/api/narrativa")
def narrativa():
    """Explicação em linguagem natural do mês, gerada sob demanda (Fase 6/IA).
    503 quando o recurso está desligado (sem ANTHROPIC_API_KEY ou sem dados
    ainda) — não é um erro do usuário, é um estado esperado do sistema."""
    try:
        texto = narrativa_service.explicar_mes()
    except NarrativaIndisponivel as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Falha ao gerar narrativa do mês")
        raise HTTPException(status_code=502, detail="Falha ao gerar a explicação. Tente novamente em instantes.")
    return {"texto": texto}


class ChatMensagem(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    mensagens: list[ChatMensagem]

    _validar_mensagens = field_validator("mensagens")(validar_mensagens_chat)


@app.post("/api/chat")
def chat(body: ChatIn):
    """Perguntas livres sobre as finanças (Fase 6/IA) — a conversa inteira
    é reenviada a cada chamada (API sem estado, sem sessão/login)."""
    if not body.mensagens:
        raise HTTPException(status_code=400, detail="Envie ao menos uma mensagem.")
    try:
        resposta = chat_service.responder([m.model_dump() for m in body.mensagens])
    except ChatIndisponivel as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Falha ao gerar resposta do chat")
        raise HTTPException(status_code=502, detail="Falha ao gerar a resposta. Tente novamente em instantes.")
    return {"resposta": resposta}


@app.get("/api/dashboard")
def dashboard(month: str | None = None):
    return dashboard_service.build_dashboard(month, formatar_mes)


@app.get("/api/dashboard/categoria")
def dashboard_categoria(categoria: str, month: str | None = None):
    return {"transacoes": dashboard_service.list_category_transactions(month, categoria)}


@app.get("/api/dashboard/transacoes")
def dashboard_transacoes(month: str | None = None, limit: int = 200, offset: int = 0):
    return dashboard_service.list_transactions(month, limit=limit, offset=offset)


@app.get("/api/patrimonio")
def patrimonio():
    return patrimonio_service.build_patrimonio()


@app.get("/api/patrimonio/snapshots")
def patrimonio_snapshots(limit: int = 200, offset: int = 0):
    return patrimonio_service.list_snapshots(limit=limit, offset=offset)


@app.post("/api/patrimonio/import")
def patrimonio_import(file: UploadFile):
    validar_tamanho_upload(file)
    if not investment_importer.supports(file.filename or ""):
        raise HTTPException(status_code=400, detail="Envie um arquivo PDF do extrato de investimento.")
    try:
        n = patrimonio_service.import_pdf(file.file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"inserted": n}


@app.get("/api/projecoes")
def projecoes(horizonte: int = 12):
    if horizonte not in (6, 12, 24):
        raise HTTPException(status_code=400, detail="horizonte deve ser 6, 12 ou 24.")
    return projecoes_service.build_projecoes(horizonte)


class LimiteIn(BaseModel):
    categoria: str
    valor: float

    _validar_categoria = field_validator("categoria")(validar_categoria)


@app.get("/api/orcamento")
def orcamento():
    return orcamento_service.build_orcamento()


@app.post("/api/orcamento/limites")
def criar_limite(body: LimiteIn):
    if body.valor <= 0:
        raise HTTPException(status_code=400, detail="Informe um valor maior que zero.")
    budget_repo.set_limit(body.categoria, body.valor)
    return {"ok": True}


@app.delete("/api/orcamento/limites/{categoria}")
def remover_limite(categoria: str):
    budget_repo.remove_limit(categoria)
    return {"ok": True}


class GoalIn(BaseModel):
    nome: str
    valor_necessario: float
    prazo: str  # "YYYY-MM-DD"

    _validar_prazo = field_validator("prazo")(validar_data_iso)


class GoalProgressIn(BaseModel):
    valor_acumulado: float = Field(ge=0)


@app.get("/api/metas")
def listar_metas():
    return goal_repo.get_all().to_dict("records")


@app.post("/api/metas")
def criar_meta(body: GoalIn):
    if not body.nome or body.valor_necessario <= 0:
        raise HTTPException(status_code=400, detail="Preencha o nome e um valor maior que zero.")
    goal_id = goal_repo.create(body.nome, body.valor_necessario, body.prazo)
    return {"id": goal_id}


@app.patch("/api/metas/{goal_id}")
def atualizar_progresso_meta(goal_id: int, body: GoalProgressIn):
    goal_repo.update_progress(goal_id, body.valor_acumulado)
    return {"ok": True}


@app.delete("/api/metas/{goal_id}")
def excluir_meta(goal_id: int):
    if not goal_repo.delete(goal_id):
        raise HTTPException(status_code=404, detail="Meta não encontrada.")
    return {"ok": True}


class DespesaFixaIn(BaseModel):
    nome: str
    categoria: str
    valor_mensal: float
    tipo: str  # "recorrente" | "parcelada"
    data_inicio: str  # "YYYY-MM-DD"
    parcela_atual: int | None = None
    parcelas_totais: int | None = None

    _validar_categoria = field_validator("categoria")(validar_categoria)


class DespesaFixaParcelaIn(BaseModel):
    parcela_atual: int = Field(ge=0)


class LimiteAlertaIn(BaseModel):
    pct: float = Field(ge=0, le=100)


@app.get("/api/despesas-fixas")
def despesas_fixas():
    return despesas_fixas_service.build_despesas_fixas()


@app.post("/api/despesas-fixas")
def criar_despesa_fixa(body: DespesaFixaIn):
    if not body.nome or body.valor_mensal <= 0:
        raise HTTPException(status_code=400, detail="Preencha o nome e um valor maior que zero.")
    if body.tipo not in ("recorrente", "parcelada"):
        raise HTTPException(status_code=400, detail="Tipo deve ser 'recorrente' ou 'parcelada'.")
    despesa_id = despesa_fixa_repo.create(
        body.nome, body.categoria, body.valor_mensal, body.tipo, body.data_inicio,
        body.parcela_atual, body.parcelas_totais,
    )
    return {"id": despesa_id}


@app.patch("/api/despesas-fixas/{despesa_id}/parcela")
def atualizar_parcela_despesa_fixa(despesa_id: int, body: DespesaFixaParcelaIn):
    despesa_fixa_repo.update_parcela_atual(despesa_id, body.parcela_atual)
    return {"ok": True}


@app.post("/api/despesas-fixas/{despesa_id}/encerrar")
def encerrar_despesa_fixa(despesa_id: int):
    despesa_fixa_repo.set_ativa(despesa_id, False)
    return {"ok": True}


@app.delete("/api/despesas-fixas/{despesa_id}")
def excluir_despesa_fixa(despesa_id: int):
    if not despesa_fixa_repo.delete(despesa_id):
        raise HTTPException(status_code=404, detail="Despesa fixa não encontrada.")
    return {"ok": True}


@app.put("/api/despesas-fixas/limite-alerta")
def definir_limite_alerta(body: LimiteAlertaIn):
    if body.pct <= 0:
        raise HTTPException(status_code=400, detail="Informe um percentual maior que zero.")
    despesas_fixas_service.set_limite_alerta_pct(body.pct)
    return {"ok": True}


@app.get("/api/relatorio")
def relatorio(month: str | None = None):
    return relatorio_service.build_relatorio(month, formatar_mes)


@app.get("/api/relatorio/pdf")
def relatorio_pdf(month: str | None = None):
    # Sem login nesse caminho (uso pessoal) — nome do titular, se quiser
    # que apareça na capa, vem de uma variável de ambiente em vez de
    # cadastro/perfil (não faz sentido construir isso pra uma pessoa só).
    nome_titular = os.environ.get("SIFP_TITULAR_NOME") or None
    pdf_bytes = relatorio_service.build_relatorio_pdf(month, formatar_mes, nome_titular=nome_titular)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Nenhum dado importado ainda.")
    nome_arquivo = f"relatorio_sifra_{month or 'atual'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@app.post("/api/upload/preview")
def upload_preview(file: UploadFile):
    validar_tamanho_upload(file)
    try:
        df, balances = import_service.parse(as_file_like(file))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "count": len(df),
        "balances_count": len(balances),
        "preview": transactions_payload(df.head(10)),
    }


@app.post("/api/upload/persist")
def upload_persist(file: UploadFile):
    validar_tamanho_upload(file)
    try:
        summary = import_service.import_and_persist(as_file_like(file))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return summary


@app.get("/api/revisao")
def revisao():
    return revisao_service.build_revisao()


class RevisaoLoteIn(BaseModel):
    description: str
    category: str

    _validar_categoria = field_validator("category")(validar_categoria)


@app.post("/api/revisao/lote")
def revisao_lote(body: RevisaoLoteIn):
    n = revisao_service.bulk_apply_by_description(body.description, body.category)
    if n == 0:
        raise HTTPException(status_code=404, detail="Nenhuma transação pendente encontrada com essa descrição.")
    msg = _refresh_model()
    return {"atualizadas": n, "mensagem_treino": msg}


class RevisaoUpdate(BaseModel):
    tx_hash: str
    category: str

    _validar_categoria = field_validator("category")(validar_categoria)


class RevisaoConfirmarIn(BaseModel):
    updates: list[RevisaoUpdate]


@app.post("/api/revisao/confirmar")
def revisao_confirmar(body: RevisaoConfirmarIn):
    updates = [(u.tx_hash, u.category) for u in body.updates]
    transaction_repo.bulk_update_categories(updates)
    msg = _refresh_model()
    n_pending = sum(1 for _, c in updates if c == CATEGORIA_NAO_CATEGORIZADO)
    return {
        "confirmadas": len(updates) - n_pending,
        "ainda_pendentes": n_pending,
        "mensagem_treino": msg,
    }


@app.post("/api/revisao/retreinar")
def revisao_retreinar():
    return {"mensagem": _refresh_model()}


@app.delete("/api/transacoes/{tx_hash}")
def excluir_transacao(tx_hash: str):
    if not transaction_repo.delete(tx_hash):
        raise HTTPException(status_code=404, detail="Transação não encontrada.")
    return {"ok": True}


@app.delete("/api/patrimonio/{position_key}")
def excluir_ativo(position_key: str):
    if not asset_repo.delete(position_key):
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    return {"ok": True}
