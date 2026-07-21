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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.goal_repository import GoalRepository
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.formatting import formatar_mes, unescape_currency
from sifp.services.summary_service import SummaryService

init_db()

transaction_repo = TransactionRepository()
balance_repo = BalanceRepository()
asset_repo = AssetRepository()
budget_repo = BudgetRepository()
goal_repo = GoalRepository()
summary_service = SummaryService(transaction_repo, balance_repo, asset_repo, budget_repo, goal_repo)

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
