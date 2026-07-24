"""
sifp/api/routes_saas.py
--------------------------
Rotas multiusuário do SaaS (Supabase Postgres + RLS), prefixo /api/v2,
lado a lado com as rotas single-tenant existentes em sifp/api/main.py
(SQLite, sem auth) — que continuam 100% intocadas. Ver memória
project_sifp_multiuser_scaling para o porquê da convivência das duas
durante a migração; a decisão de qual URL vira qual fica pra quando o
deploy for feito.

Cada rota monta os MESMOS services de sifp/services/*.py que a API
single-tenant já usa — só que com repositories Postgres escopados por
usuário (ConnBound em cima da conexão de get_db) em vez dos repositories
SQLite globais. Nenhuma lógica de negócio nova aqui, só composição.

O CategorizationService (modelo de ML) é a única peça deliberadamente
global (não por tenant, ver sifp/api/shared.py) — é sugestão de categoria,
não dado financeiro sensível.
"""

from __future__ import annotations

import os

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel

from sifp.api.auth import get_current_user_name, get_db
from sifp.api.shared import as_file_like, categorization_service, transactions_payload
from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO
from sifp.importers.btg_importer import BTGImporter
from sifp.importers.btg_investment_importer import BTGInvestmentImporter
from sifp.repositories.pg.asset_repository import AssetRepository
from sifp.repositories.pg.balance_repository import BalanceRepository
from sifp.repositories.pg.bound import ConnBound
from sifp.repositories.pg.budget_repository import BudgetRepository
from sifp.repositories.pg.despesa_fixa_repository import DespesaFixaRepository
from sifp.repositories.pg.goal_repository import GoalRepository
from sifp.repositories.pg.import_alias_repository import ImportAliasRepository
from sifp.repositories.pg.preferencia_repository import PreferenciaRepository
from sifp.repositories.pg.transaction_repository import TransactionRepository
from sifp.services.chat_service import ChatIndisponivel, ChatService
from sifp.services.dashboard_service import DashboardService
from sifp.services.despesas_fixas_service import DespesasFixasService
from sifp.services.formatting import formatar_mes, unescape_currency
from sifp.services.import_service import ImportService
from sifp.services.narrativa_service import NarrativaIndisponivel, NarrativaService
from sifp.services.orcamento_service import OrcamentoService
from sifp.services.patrimonio_service import PatrimonioService
from sifp.services.projecoes_service import ProjecoesService
from sifp.services.relatorio_service import RelatorioService
from sifp.services.revisao_service import RevisaoService
from sifp.services.summary_service import SummaryService

router = APIRouter(prefix="/api/v2")

_investment_importer = BTGInvestmentImporter()


def _repos(conn: psycopg.Connection) -> dict:
    return {
        "transaction_repo": ConnBound(TransactionRepository(), conn),
        "balance_repo": ConnBound(BalanceRepository(), conn),
        "asset_repo": ConnBound(AssetRepository(), conn),
        "budget_repo": ConnBound(BudgetRepository(), conn),
        "goal_repo": ConnBound(GoalRepository(), conn),
        "despesa_fixa_repo": ConnBound(DespesaFixaRepository(), conn),
        "preferencia_repo": ConnBound(PreferenciaRepository(), conn),
        "import_alias_repo": ConnBound(ImportAliasRepository(), conn),
    }


def _summary_service(r: dict) -> SummaryService:
    return SummaryService(
        r["transaction_repo"], r["balance_repo"], r["asset_repo"], r["budget_repo"], r["goal_repo"],
        r["despesa_fixa_repo"], r["preferencia_repo"],
    )


def _plain_resumo(resumo: dict) -> dict:
    """Mesmo motivo da versão single-tenant (ver main.py): desfaz o escape
    de 'R$' que SummaryService devolve pensado pro markdown do Streamlit."""
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


@router.get("/resumo")
def resumo(conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    summary_service = _summary_service(r)
    return _plain_resumo(summary_service.build_resumo(formatar_mes))


@router.get("/dashboard")
def dashboard(month: str | None = None, conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    dashboard_service = DashboardService(r["transaction_repo"], r["balance_repo"])
    return dashboard_service.build_dashboard(month, formatar_mes)


@router.get("/patrimonio")
def patrimonio(conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    patrimonio_service = PatrimonioService(r["asset_repo"], _investment_importer)
    return patrimonio_service.build_patrimonio()


@router.post("/patrimonio/import")
def patrimonio_import(file: UploadFile, conn: psycopg.Connection = Depends(get_db)):
    if not _investment_importer.supports(file.filename or ""):
        raise HTTPException(status_code=400, detail="Envie um arquivo PDF do extrato de investimento.")
    r = _repos(conn)
    patrimonio_service = PatrimonioService(r["asset_repo"], _investment_importer)
    try:
        n = patrimonio_service.import_pdf(file.file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"inserted": n}


@router.get("/projecoes")
def projecoes(horizonte: int = 12, conn: psycopg.Connection = Depends(get_db)):
    if horizonte not in (6, 12, 24):
        raise HTTPException(status_code=400, detail="horizonte deve ser 6, 12 ou 24.")
    r = _repos(conn)
    projecoes_service = ProjecoesService(r["transaction_repo"], r["asset_repo"], r["goal_repo"])
    return projecoes_service.build_projecoes(horizonte)


class LimiteIn(BaseModel):
    category: str
    valor: float


@router.get("/orcamento")
def orcamento(conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    orcamento_service = OrcamentoService(r["transaction_repo"], r["budget_repo"])
    return orcamento_service.build_orcamento()


@router.post("/orcamento/limites")
def criar_limite(body: LimiteIn, conn: psycopg.Connection = Depends(get_db)):
    if body.valor <= 0:
        raise HTTPException(status_code=400, detail="Informe um valor maior que zero.")
    _repos(conn)["budget_repo"].set_limit(body.category, body.valor)
    return {"ok": True}


@router.delete("/orcamento/limites/{category}")
def remover_limite(category: str, conn: psycopg.Connection = Depends(get_db)):
    _repos(conn)["budget_repo"].remove_limit(category)
    return {"ok": True}


class GoalIn(BaseModel):
    nome: str
    valor_necessario: float
    prazo: str  # "YYYY-MM-DD"


class GoalProgressIn(BaseModel):
    valor_acumulado: float


@router.get("/metas")
def listar_metas(conn: psycopg.Connection = Depends(get_db)):
    df = _repos(conn)["goal_repo"].get_all().drop(columns=["user_id"])
    return df.to_dict("records")


@router.post("/metas")
def criar_meta(body: GoalIn, conn: psycopg.Connection = Depends(get_db)):
    if not body.nome or body.valor_necessario <= 0:
        raise HTTPException(status_code=400, detail="Preencha o nome e um valor maior que zero.")
    goal_id = _repos(conn)["goal_repo"].create(body.nome, body.valor_necessario, body.prazo)
    return {"id": goal_id}


@router.patch("/metas/{goal_id}")
def atualizar_progresso_meta(goal_id: int, body: GoalProgressIn, conn: psycopg.Connection = Depends(get_db)):
    _repos(conn)["goal_repo"].update_progress(goal_id, body.valor_acumulado)
    return {"ok": True}


@router.delete("/metas/{goal_id}")
def excluir_meta(goal_id: int, conn: psycopg.Connection = Depends(get_db)):
    _repos(conn)["goal_repo"].delete(goal_id)
    return {"ok": True}


class DespesaFixaIn(BaseModel):
    nome: str
    categoria: str
    valor_mensal: float
    tipo: str  # "recorrente" | "parcelada"
    data_inicio: str  # "YYYY-MM-DD"
    parcela_atual: int | None = None
    parcelas_totais: int | None = None


class DespesaFixaParcelaIn(BaseModel):
    parcela_atual: int


class LimiteAlertaIn(BaseModel):
    pct: float


@router.get("/despesas-fixas")
def despesas_fixas(conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    return DespesasFixasService(r["despesa_fixa_repo"], r["preferencia_repo"], r["transaction_repo"]).build_despesas_fixas()


@router.post("/despesas-fixas")
def criar_despesa_fixa(body: DespesaFixaIn, conn: psycopg.Connection = Depends(get_db)):
    if not body.nome or body.valor_mensal <= 0:
        raise HTTPException(status_code=400, detail="Preencha o nome e um valor maior que zero.")
    if body.tipo not in ("recorrente", "parcelada"):
        raise HTTPException(status_code=400, detail="Tipo deve ser 'recorrente' ou 'parcelada'.")
    despesa_id = _repos(conn)["despesa_fixa_repo"].create(
        body.nome, body.categoria, body.valor_mensal, body.tipo, body.data_inicio,
        body.parcela_atual, body.parcelas_totais,
    )
    return {"id": despesa_id}


@router.patch("/despesas-fixas/{despesa_id}/parcela")
def atualizar_parcela_despesa_fixa(
    despesa_id: int, body: DespesaFixaParcelaIn, conn: psycopg.Connection = Depends(get_db)
):
    _repos(conn)["despesa_fixa_repo"].update_parcela_atual(despesa_id, body.parcela_atual)
    return {"ok": True}


@router.post("/despesas-fixas/{despesa_id}/encerrar")
def encerrar_despesa_fixa(despesa_id: int, conn: psycopg.Connection = Depends(get_db)):
    _repos(conn)["despesa_fixa_repo"].set_ativa(despesa_id, False)
    return {"ok": True}


@router.delete("/despesas-fixas/{despesa_id}")
def excluir_despesa_fixa(despesa_id: int, conn: psycopg.Connection = Depends(get_db)):
    _repos(conn)["despesa_fixa_repo"].delete(despesa_id)
    return {"ok": True}


@router.put("/despesas-fixas/limite-alerta")
def definir_limite_alerta(body: LimiteAlertaIn, conn: psycopg.Connection = Depends(get_db)):
    if body.pct <= 0:
        raise HTTPException(status_code=400, detail="Informe um percentual maior que zero.")
    r = _repos(conn)
    DespesasFixasService(r["despesa_fixa_repo"], r["preferencia_repo"], r["transaction_repo"]).set_limite_alerta_pct(
        body.pct
    )
    return {"ok": True}


@router.get("/perfil/email-importacao")
def email_importacao(conn: psycopg.Connection = Depends(get_db)):
    """Endereço pessoal de encaminhamento (Módulo 18) — o usuário
    configura no próprio provedor de e-mail um encaminhamento automático
    do extrato do BTG pra esse endereço; o worker (sifp/workers/
    email_import_worker.py) identifica de quem é pelo "+token"."""
    base = os.environ.get("EMAIL_IMPORT_BASE")
    if not base:
        raise HTTPException(status_code=503, detail="Importação por e-mail ainda não configurada.")
    local, _, domain = base.partition("@")
    token = _repos(conn)["import_alias_repo"].get_or_create()
    return {"email": f"{local}+{token}@{domain}"}


@router.get("/relatorio")
def relatorio(month: str | None = None, conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    summary_service = _summary_service(r)
    relatorio_service = RelatorioService(r["transaction_repo"], r["asset_repo"], summary_service)
    return relatorio_service.build_relatorio(month, formatar_mes)


@router.get("/relatorio/pdf")
def relatorio_pdf(
    month: str | None = None,
    conn: psycopg.Connection = Depends(get_db),
    nome_titular: str | None = Depends(get_current_user_name),
):
    r = _repos(conn)
    summary_service = _summary_service(r)
    relatorio_service = RelatorioService(r["transaction_repo"], r["asset_repo"], summary_service)
    pdf_bytes = relatorio_service.build_relatorio_pdf(month, formatar_mes, nome_titular=nome_titular)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Nenhum dado importado ainda.")
    nome_arquivo = f"relatorio_sifra_{month or 'atual'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


def _import_service(r: dict) -> ImportService:
    return ImportService(
        importers=[BTGImporter()],
        categorization=categorization_service,
        transaction_repo=r["transaction_repo"],
        balance_repo=r["balance_repo"],
    )


def _refresh_model(r: dict) -> str:
    training_df = r["transaction_repo"].get_training_data()
    return categorization_service.train(training_df)


@router.post("/upload/preview")
def upload_preview(file: UploadFile, conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    try:
        df, balances = _import_service(r).parse(as_file_like(file))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "count": len(df),
        "balances_count": len(balances),
        "preview": transactions_payload(df.head(10)),
    }


@router.post("/upload/persist")
def upload_persist(file: UploadFile, conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    try:
        summary = _import_service(r).import_and_persist(as_file_like(file))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return summary


@router.get("/revisao")
def revisao(conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    return RevisaoService(r["transaction_repo"]).build_revisao()


class RevisaoLoteIn(BaseModel):
    description: str
    category: str


@router.post("/revisao/lote")
def revisao_lote(body: RevisaoLoteIn, conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    n = RevisaoService(r["transaction_repo"]).bulk_apply_by_description(body.description, body.category)
    if n == 0:
        raise HTTPException(status_code=404, detail="Nenhuma transação pendente encontrada com essa descrição.")
    msg = _refresh_model(r)
    return {"atualizadas": n, "mensagem_treino": msg}


class RevisaoUpdate(BaseModel):
    tx_hash: str
    category: str


class RevisaoConfirmarIn(BaseModel):
    updates: list[RevisaoUpdate]


@router.post("/revisao/confirmar")
def revisao_confirmar(body: RevisaoConfirmarIn, conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    updates = [(u.tx_hash, u.category) for u in body.updates]
    r["transaction_repo"].bulk_update_categories(updates)
    msg = _refresh_model(r)
    n_pending = sum(1 for _, c in updates if c == CATEGORIA_NAO_CATEGORIZADO)
    return {
        "confirmadas": len(updates) - n_pending,
        "ainda_pendentes": n_pending,
        "mensagem_treino": msg,
    }


@router.post("/revisao/retreinar")
def revisao_retreinar(conn: psycopg.Connection = Depends(get_db)):
    return {"mensagem": _refresh_model(_repos(conn))}


@router.post("/narrativa")
def narrativa(conn: psycopg.Connection = Depends(get_db)):
    r = _repos(conn)
    summary_service = _summary_service(r)
    narrativa_service = NarrativaService(summary_service, r["transaction_repo"])
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


@router.post("/chat")
def chat(body: ChatIn, conn: psycopg.Connection = Depends(get_db)):
    if not body.mensagens:
        raise HTTPException(status_code=400, detail="Envie ao menos uma mensagem.")
    r = _repos(conn)
    chat_service = ChatService(r["transaction_repo"], r["asset_repo"])
    try:
        resposta = chat_service.responder([m.model_dump() for m in body.mensagens])
    except ChatIndisponivel as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="Falha ao gerar a resposta. Tente novamente em instantes.")
    return {"resposta": resposta}
