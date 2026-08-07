"""
patrimonio_service.py
----------------------
Composição para a tela "Patrimônio": posições atuais dos ativos e
evolução histórica, mais a importação de um novo extrato em PDF. Mesmo
padrão de summary_service.py / dashboard_service.py — compartilhado
entre o app Streamlit e a API REST.
"""

from __future__ import annotations

import pandas as pd

from sifp.services import indicator_service as ind


_SNAPSHOT_COLUMNS = [
    "position_key", "nome", "tipo", "instituicao", "data_referencia", "saldo_liquido",
    "rentabilidade_12m_pct", "benchmark", "benchmark_12m_pct",
]


def _sanitize_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    """Seleciona as colunas expostas na API, formata a data e troca NaN
    por None -- snapshots mais antigos podem não ter rentabilidade/
    benchmark preenchidos, e NaN não é JSON válido (Starlette serializa
    com allow_nan=False, o que quebrava a rota com 500 assim que um
    extrato sem essas colunas aparecia)."""
    out = df[_SNAPSHOT_COLUMNS].copy()
    out["data_referencia"] = pd.to_datetime(out["data_referencia"]).dt.strftime("%Y-%m-%d")
    return out.astype(object).where(pd.notna(out), None)


class PatrimonioService:
    def __init__(self, asset_repo, investment_importer):
        self.asset_repo = asset_repo
        self.investment_importer = investment_importer

    def build_patrimonio(self) -> dict:
        latest = self.asset_repo.get_latest_positions()
        if latest.empty:
            return {"has_data": False}

        patrimonio_total = float(latest["saldo_liquido"].sum())

        all_snapshots = self.asset_repo.get_all()
        net_worth = ind.net_worth_history(all_snapshots)
        if not net_worth.empty:
            net_worth = net_worth.copy()
            net_worth["data_referencia"] = pd.to_datetime(net_worth["data_referencia"]).dt.strftime("%Y-%m-%d")
        net_worth_records = net_worth.to_dict("records") if not net_worth.empty else []

        return {
            "has_data": True,
            "patrimonio_total": patrimonio_total,
            "assets": _sanitize_snapshots(latest).to_dict("records"),
            "net_worth_history": net_worth_records,
        }

    def list_snapshots(self, limit: int = 200, offset: int = 0) -> dict:
        """Página do histórico completo de snapshots de ativos (todas as
        importações, não só a posição mais recente) — usado pelo expander
        "Ver histórico completo" da tela Patrimônio. Rota própria pelo
        mesmo motivo de DashboardService.list_transactions: o histórico
        inteiro sem limite era carregado em toda visita à tela mesmo que
        o expander nunca abrisse."""
        all_snapshots = self.asset_repo.get_all()
        if all_snapshots.empty:
            return {"snapshots": [], "total": 0, "has_more": False}

        total = len(all_snapshots)
        page = all_snapshots.iloc[offset:offset + limit]
        return {
            "snapshots": _sanitize_snapshots(page).to_dict("records"),
            "total": total,
            "has_more": offset + limit < total,
        }

    def import_pdf(self, file_obj) -> int:
        """Lê e persiste um extrato de investimento em PDF. Propaga
        ValueError (PDF ilegível/corrompido) pro chamador tratar."""
        positions = self.investment_importer.read(file_obj)
        return self.asset_repo.insert_many(positions)
