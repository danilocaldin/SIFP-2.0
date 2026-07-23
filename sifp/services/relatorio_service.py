"""
relatorio_service.py
---------------------
Composição para a tela "Relatório": monta o payload de um mês específico
reutilizando report_service.generate_text_report (mesma fonte de dados das
outras telas, via SummaryService.diagnostics_for_month) — compartilhado
entre o app Streamlit e a API REST. `_compor_periodo` é a base comum entre
o relatório em texto e o relatório em PDF (pdf_report_service): nenhum dos
dois recalcula nada, só formatam a mesma composição de dado de forma
diferente.
"""

from __future__ import annotations

import pandas as pd

from sifp.services import indicator_service as ind
from sifp.services.pdf_report_service import generate_pdf_report
from sifp.services.report_service import generate_text_report


class RelatorioService:
    def __init__(self, transaction_repo, asset_repo, summary_service):
        self.transaction_repo = transaction_repo
        self.asset_repo = asset_repo
        self.summary_service = summary_service

    def _compor_periodo(self, month: str | None, month_label_fmt) -> dict | None:
        """Monta os dados de um período (mês escolhido ou o mais recente).
        None se não há nenhuma transação importada ainda."""
        all_tx = self.transaction_repo.get_all()
        if all_tx.empty:
            return None

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

        return {
            "months_sorted": months_sorted,
            "month": month,
            "period_label": period_label,
            "summary": summary,
            "by_cat": by_cat,
            "by_merchant": by_merchant,
            "monthly": monthly,
            "latest_assets": latest_assets,
            "diagnostics": diagnostics,
            "debt_transactions": debt_transactions,
        }

    def build_relatorio(self, month: str | None, month_label_fmt) -> dict:
        """Payload completo da tela Relatório. `month`=None ou inexistente
        cai pro mês mais recente disponível (mesmo padrão de fallback do
        Dashboard)."""
        dados = self._compor_periodo(month, month_label_fmt)
        if dados is None:
            return {"has_data": False}

        report_text = generate_text_report(
            period_label=dados["period_label"],
            summary=dados["summary"],
            by_cat=dados["by_cat"],
            by_merchant=dados["by_merchant"],
            monthly=dados["monthly"],
            diagnostics=dados["diagnostics"],
            asset_positions=dados["latest_assets"],
            debt_transactions=dados["debt_transactions"],
        )

        return {
            "has_data": True,
            "months": dados["months_sorted"],
            "months_labels": {m: month_label_fmt(m) for m in dados["months_sorted"]},
            "selected_month": dados["month"],
            "period_label": dados["period_label"],
            "report_text": report_text,
        }

    def build_relatorio_pdf(self, month: str | None, month_label_fmt) -> bytes | None:
        """PDF do mesmo período/dados do relatório em texto. None se não há
        nenhuma transação importada ainda."""
        dados = self._compor_periodo(month, month_label_fmt)
        if dados is None:
            return None

        patrimonio_total = (
            float(dados["latest_assets"]["saldo_liquido"].sum()) if not dados["latest_assets"].empty else 0.0
        )

        return generate_pdf_report(
            period_label=dados["period_label"],
            summary=dados["summary"],
            by_cat=dados["by_cat"],
            monthly=dados["monthly"],
            diagnostics=dados["diagnostics"],
            patrimonio_total=patrimonio_total,
        )
