"""
dashboard_service.py
---------------------
Composição para a tela "Dashboard" (visão geral de um mês ou de todo o
período). Extraído do padrão já usado em summary_service.py: agrega
indicator_service num único payload, compartilhado entre o app Streamlit
e a API REST, pra nunca haver duas implementações que podem divergir.
"""

from __future__ import annotations

import pandas as pd

from sifp.services import indicator_service as ind


class DashboardService:
    def __init__(self, transaction_repo, balance_repo):
        self.transaction_repo = transaction_repo
        self.balance_repo = balance_repo

    def build_dashboard(self, month: str | None, month_label_fmt) -> dict:
        """Payload completo da tela Dashboard. `month`=None significa "todo o
        período importado" (mesmo comportamento da opção "Todos" no Streamlit).
        `month_label_fmt` formata um período 'YYYY-MM' para exibição."""
        all_tx = self.transaction_repo.get_all()
        if all_tx.empty:
            return {"has_data": False}

        all_tx["date"] = pd.to_datetime(all_tx["date"])
        all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)
        all_tx_real = ind.exclude_self_transfers(all_tx)

        months_sorted = sorted(all_tx["month"].unique())
        if month is not None and month not in months_sorted:
            month = None  # mês inválido/inexistente -> cai pro período todo

        df_period = all_tx if month is None else all_tx[all_tx["month"] == month]
        df_period_real = all_tx_real if month is None else all_tx_real[all_tx_real["month"] == month]

        summary = ind.period_summary(df_period_real)

        prev_summary = None
        if month is not None:
            idx = months_sorted.index(month)
            if idx > 0:
                df_prev = all_tx_real[all_tx_real["month"] == months_sorted[idx - 1]]
                prev_summary = ind.period_summary(df_prev)
        delta = ind.month_over_month_delta(summary, prev_summary)

        by_cat = ind.category_breakdown(df_period_real)
        monthly = ind.monthly_evolution(all_tx_real)
        top_gastos = ind.top_expenses(df_period_real, n=10)
        by_merchant = ind.merchant_concentration(df_period_real, n=10)

        monthly_records = monthly.to_dict("records")
        for row in monthly_records:
            row["mes_label"] = month_label_fmt(row["month"])

        top_gastos_records = top_gastos.to_dict("records")
        for row in top_gastos_records:
            row["date"] = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")

        all_transactions_records = (
            df_period[["date", "description", "value", "bank_category", "merchant", "category"]]
            .sort_values("date", ascending=False)
            .to_dict("records")
        )
        for row in all_transactions_records:
            row["date"] = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")

        # Saldo diário (Módulo 3) só existe pra extratos XLS/XLSX do BTG, que
        # trazem a coluna "Saldo Diário" -- é um dado mais fino que o saldo
        # mensal agregado (monthly_evolution), então fica em separado.
        all_balances = self.balance_repo.get_all()
        daily_balance_records = []
        if not all_balances.empty:
            bal_period = all_balances.copy()
            bal_period["month"] = bal_period["date"].dt.to_period("M").astype(str)
            if month is not None:
                bal_period = bal_period[bal_period["month"] == month]
            if not bal_period.empty:
                bal_period = bal_period.sort_values("date")
                daily_balance_records = [
                    {"date": row["date"].strftime("%Y-%m-%d"), "balance": float(row["balance"])}
                    for _, row in bal_period.iterrows()
                ]

        return {
            "has_data": True,
            "months": months_sorted,
            "selected_month": month,
            "period_label": month_label_fmt(month) if month is not None else "todo o período importado",
            "receitas": float(summary["receitas"]),
            "despesas": float(summary["despesas"]),
            "saldo": float(summary["saldo"]),
            "taxa_poupanca_pct": float(summary["taxa_poupanca"]),
            "delta": delta,
            "self_transfer_total": float(ind.self_transfer_total(df_period)),
            "by_category": by_cat.to_dict("records"),
            "monthly_evolution": monthly_records,
            "top_expenses": top_gastos_records,
            "top_merchants": by_merchant.to_dict("records"),
            "all_transactions": all_transactions_records,
            "daily_balance": daily_balance_records,
        }

    def list_category_transactions(self, month: str | None, categoria: str) -> list[dict]:
        """Transações individuais de uma categoria (só despesas, mesmo filtro
        de category_breakdown) num mês — usado no drill-down ao clicar numa
        barra do gráfico "Gastos por categoria"."""
        all_tx = self.transaction_repo.get_all()
        if all_tx.empty:
            return []

        all_tx["date"] = pd.to_datetime(all_tx["date"])
        all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)
        all_tx_real = ind.exclude_self_transfers(all_tx)
        df_period_real = all_tx_real if month is None else all_tx_real[all_tx_real["month"] == month]

        gastos = df_period_real[
            (df_period_real["category"] == categoria) & (df_period_real["value"] < 0)
        ].copy()
        if gastos.empty:
            return []
        gastos = gastos.sort_values("value")  # mais negativo (maior gasto) primeiro
        gastos["date"] = gastos["date"].dt.strftime("%Y-%m-%d")
        return gastos[["date", "description", "value"]].to_dict("records")
