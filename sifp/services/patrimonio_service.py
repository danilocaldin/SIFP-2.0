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


class PatrimonioService:
    def __init__(self, asset_repo, investment_importer):
        self.asset_repo = asset_repo
        self.investment_importer = investment_importer

    def build_patrimonio(self) -> dict:
        latest = self.asset_repo.get_latest_positions()
        if latest.empty:
            return {"has_data": False}

        latest = latest.copy()
        latest["data_referencia"] = latest["data_referencia"].dt.strftime("%Y-%m-%d")
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
            "assets": latest[
                ["nome", "tipo", "instituicao", "data_referencia", "saldo_liquido",
                 "rentabilidade_12m_pct", "benchmark", "benchmark_12m_pct"]
            ].to_dict("records"),
            "net_worth_history": net_worth_records,
        }

    def import_pdf(self, file_obj) -> int:
        """Lê e persiste um extrato de investimento em PDF. Propaga
        ValueError (PDF ilegível/corrompido) pro chamador tratar."""
        positions = self.investment_importer.read(file_obj)
        return self.asset_repo.insert_many(positions)
