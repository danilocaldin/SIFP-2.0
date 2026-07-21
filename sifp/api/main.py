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

import io
import os

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sifp.importers.btg_importer import BTGImporter
from sifp.importers.btg_investment_importer import BTGInvestmentImporter
from sifp.intelligence.categorization import CategorizationService
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.goal_repository import GoalRepository
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.dashboard_service import DashboardService
from sifp.services.formatting import formatar_mes, unescape_currency
from sifp.services.import_service import ImportService
from sifp.services.orcamento_service import OrcamentoService
from sifp.services.patrimonio_service import PatrimonioService
from sifp.services.projecoes_service import ProjecoesService
from sifp.services.relatorio_service import RelatorioService
from sifp.services.summary_service import SummaryService

init_db()

transaction_repo = TransactionRepository()
balance_repo = BalanceRepository()
asset_repo = AssetRepository()
budget_repo = BudgetRepository()
goal_repo = GoalRepository()
investment_importer = BTGInvestmentImporter()
# Estado do modelo de ML vive nesta instância (mesmo padrão de
# st.session_state.categorization no Streamlit) — singleton do processo,
# recarrega do disco (categorizer_model.joblib) uma vez no boot da API.
categorization_service = CategorizationService.load()
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


def _refresh_model() -> str:
    training_df = transaction_repo.get_training_data()
    return categorization_service.train(training_df)


def _as_file_like(file: UploadFile) -> io.BytesIO:
    """Importers/ImportService esperam um arquivo com `.name` (mesma
    interface do UploadedFile do Streamlit) pra decidir o parser pela
    extensão — UploadFile.file (SpooledTemporaryFile) não garante isso."""
    file_like = io.BytesIO(file.file.read())
    file_like.name = file.filename or ""
    return file_like

app = FastAPI(title="SIFP API")

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


def _transactions_payload(df) -> list[dict]:
    """Sanitiza tipos numpy (bool_/float64) que o encoder JSON do FastAPI
    não serializa nativamente, antes de devolver linhas de transação."""
    records = df.to_dict("records")
    for r in records:
        r["value"] = float(r["value"])
        r["self_transfer"] = bool(r["self_transfer"])
    return records


@app.post("/api/upload/preview")
def upload_preview(file: UploadFile):
    try:
        df, balances = import_service.parse(_as_file_like(file))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "count": len(df),
        "balances_count": len(balances),
        "preview": _transactions_payload(df.head(10)),
    }


@app.post("/api/upload/persist")
def upload_persist(file: UploadFile):
    try:
        summary = import_service.import_and_persist(_as_file_like(file))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return summary
