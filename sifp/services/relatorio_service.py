"""
relatorio_service.py
---------------------
Composição para a tela "Relatório": monta o payload de um mês específico
reutilizando report_service.generate_text_report (mesma fonte de dados das
outras telas, via SummaryService.diagnostics_for_month) — compartilhado
entre o app Streamlit e a API REST.
"""

from __future__ import annotations

import pandas as pd

from sifp.services import indicator_service as ind
from sifp.services.report_service import generate_text_report


class RelatorioService:
    def __init__(self, transaction_repo, asset_repo, summary_service):
        self.transaction_repo = transaction_repo
        self.asset_repo = asset_repo
        self.summary_service = summary_service

    def build_relatorio(self, month: str | None, month_label_fmt) -> dict:
        """Payload completo da tela Relatório. `month`=None ou inexistente
        cai pro mês mais recente disponível (mesmo padrão de fallback do
        Dashboard)."""
        all_tx = self.transaction_repo.get_all()
        if all_tx.empty:
            return {"has_data": False}

        all_tx["date"] = pd.to_datetime(all_tx["date"])
        all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)
        all_tx_real = ind.exclude_self_transfers(all_tx)

        months_sorted = sorted(all_tx["month"].unique())
        if month is None or month not in months_sorted:
            month = months_sorted[-1]

        period_label = month_label_fmt(month)
        period_df = all_tx[all_tx["month"] == month]
        period_df_real = all_tx_real[all_tx_real["month"] == month]

        summary = ind.period_summary(period_df_real)
        by_cat = ind.category_breakdown(period_df_real)
        by_merchant = ind.merchant_concentration(period_df_real)
        monthly = ind.monthly_evolution(all_tx_real)
        latest_assets = self.asset_repo.get_latest_positions()

        diagnostics = self.summary_service.diagnostics_for_month(all_tx, all_tx_real, month, period_label)

        debt_transactions = period_df[period_df["category"] == "Dívida"]

        report_text = generate_text_report(
            period_label=period_label,
            summary=summary,
            by_cat=by_cat,
            by_merchant=by_merchant,
            monthly=monthly,
            diagnostics=diagnostics,
            asset_positions=latest_assets,
            debt_transactions=debt_transactions,
        )

        return {
            "has_data": True,
            "months": months_sorted,
            "months_labels": {m: month_label_fmt(m) for m in months_sorted},
            "selected_month": month,
            "period_label": period_label,
            "report_text": report_text,
        }
