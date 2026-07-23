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

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sifp.api.routes_saas import router as saas_router
from sifp.api.shared import as_file_like, categorization_service, transactions_payload
from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO
from sifp.importers.btg_importer import BTGImporter
from sifp.importers.btg_investment_importer import BTGInvestmentImporter
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.goal_repository import GoalRepository
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.dashboard_service import DashboardService
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
investment_importer = BTGInvestmentImporter()
import_service = ImportService(
    importers=[BTGImporter()],
    categorization=categorization_service,
    transaction_repo=transaction_repo,
    balance_repo=balance_repo,
)
summary_service = SummaryService(transaction_repo, balance_repo, asset_repo, budget_repo, goal_repo)
dashboard_service = DashboardService(transaction_repo, balance_repo)
patrimonio_service = PatrimonioService(asset_repo, investment_importer)
projecoes_service = ProjecoesService(transaction_repo, asset_repo, goal_repo)
orcamento_service = OrcamentoService(transaction_repo, budget_repo)
relatorio_service = RelatorioService(transaction_repo, asset_repo, summary_service)
revisao_service = RevisaoService(transaction_repo)
narrativa_service = NarrativaService(summary_service, transaction_repo)
chat_service = ChatService(transaction_repo, asset_repo)


def _refresh_model() -> str:
    training_df = transaction_repo.get_training_data()
    return categorization_service.train(training_df)


app = FastAPI(title="SIFP API")
app.include_router(saas_router)

# Origem(s) do frontend, via env var — sem isso, hospedar em outra máquina
# (ou domínio de produção) exigiria editar código-fonte. CORS_ORIGINS
# aceita uma lista separada por vírgula; default cobre o dev local.
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
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
        raise HTTPException(status_code=502, detail="Falha ao gerar a explicação. Tente novamente em instantes.")
    return {"texto": texto}


class ChatMensagem(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    mensagens: list[ChatMensagem]


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
        raise HTTPException(status_code=502, detail="Falha ao gerar a resposta. Tente novamente em instantes.")
    return {"resposta": resposta}


@app.get("/api/dashboard")
def dashboard(month: str | None = None):
    return dashboard_service.build_dashboard(month, formatar_mes)


@app.get("/api/patrimonio")
def patrimonio():
    return patrimonio_service.build_patrimonio()


@app.post("/api/patrimonio/import")
def patrimonio_import(file: UploadFile):
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
    category: str
    valor: float


@app.get("/api/orcamento")
def orcamento():
    return orcamento_service.build_orcamento()


@app.post("/api/orcamento/limites")
def criar_limite(body: LimiteIn):
    if body.valor <= 0:
        raise HTTPException(status_code=400, detail="Informe um valor maior que zero.")
    budget_repo.set_limit(body.category, body.valor)
    return {"ok": True}


@app.delete("/api/orcamento/limites/{category}")
def remover_limite(category: str):
    budget_repo.remove_limit(category)
    return {"ok": True}


class GoalIn(BaseModel):
    nome: str
    valor_necessario: float
    prazo: str  # "YYYY-MM-DD"


class GoalProgressIn(BaseModel):
    valor_acumulado: float


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
    goal_repo.delete(goal_id)
    return {"ok": True}


@app.get("/api/relatorio")
def relatorio(month: str | None = None):
    return relatorio_service.build_relatorio(month, formatar_mes)


@app.get("/api/relatorio/pdf")
def relatorio_pdf(month: str | None = None):
    pdf_bytes = relatorio_service.build_relatorio_pdf(month, formatar_mes)
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
