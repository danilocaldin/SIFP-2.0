"""
summary_service.py
-------------------
Composição para a tela "Resumo" (Módulo 16): agrega indicadores,
diagnósticos e projeções num único payload. Extraído de app.py para que a
API REST (sifp/api) e o app Streamlit leiam exatamente os mesmos números,
sem duas implementações que podem divergir com o tempo.
"""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from sifp.domain.models import Diagnostic
from sifp.intelligence import diagnostics as diag
from sifp.services import indicator_service as ind
from sifp.services import projection_service as proj
from sifp.services.despesas_fixas_service import DespesasFixasService


def diagnostic_to_dict(d: Diagnostic) -> dict:
    payload = asdict(d)
    payload["severidade"] = d.severidade.value
    payload["prioridade"] = d.prioridade
    return payload


class SummaryService:
    def __init__(
        self, transaction_repo, balance_repo, asset_repo, budget_repo, goal_repo,
        despesa_fixa_repo, preferencia_repo,
    ):
        self.transaction_repo = transaction_repo
        self.balance_repo = balance_repo
        self.asset_repo = asset_repo
        self.budget_repo = budget_repo
        self.goal_repo = goal_repo
        self.despesa_fixa_repo = despesa_fixa_repo
        self.preferencia_repo = preferencia_repo

    def diagnostics_for_month(
        self, all_tx_full: pd.DataFrame, all_tx_real: pd.DataFrame, month: str, month_label: str
    ) -> list[Diagnostic]:
        """Roda o motor de diagnósticos (Módulo 10) para um mês específico."""
        monthly = ind.monthly_evolution(all_tx_real)
        period_df = all_tx_real[all_tx_real["month"] == month]
        summary = ind.period_summary(period_df)
        by_cat = ind.category_breakdown(period_df)
        latest_assets = self.asset_repo.get_latest_positions()
        patrimonio_total = float(latest_assets["saldo_liquido"].sum()) if not latest_assets.empty else 0.0
        despesa_media_mensal = float(monthly["Despesas"].mean()) if not monthly.empty else 0.0

        despesas_fixas = DespesasFixasService(
            self.despesa_fixa_repo, self.preferencia_repo, self.transaction_repo
        ).build_despesas_fixas()

        return diag.run_diagnostics(
            monthly=monthly,
            latest_summary=summary,
            latest_period_label=month_label,
            latest_by_cat=by_cat,
            all_tx=all_tx_full,
            patrimonio_total=patrimonio_total,
            despesa_media_mensal=despesa_media_mensal,
            budget_limits=self.budget_repo.get_limits_dict(),
            goals=self.goal_repo.get_all(),
            latest_assets=latest_assets,
            category_trend_df=ind.category_trend(all_tx_real),
            weekend_stats=ind.weekend_vs_weekday_spending(all_tx_real),
            latest_month=month,
            balance_stats=ind.average_balance(self.balance_repo.get_all()),
            despesas_fixas_total=despesas_fixas["total_mensal"],
            receita_media_mensal=despesas_fixas["receita_media_mensal"],
            despesas_fixas_limite_pct=despesas_fixas["limite_alerta_pct"],
        )

    def build_resumo(self, month_label_fmt) -> dict:
        """Payload completo da tela Resumo. `month_label_fmt` formata um
        período 'YYYY-MM' para exibição (ex: 'Jun/2026') — mantido como
        parâmetro em vez de importado, porque hoje só existe em app.py."""
        all_tx = self.transaction_repo.get_all()
        if all_tx.empty:
            return {"has_data": False}

        all_tx["date"] = pd.to_datetime(all_tx["date"])
        all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)
        all_tx_real = ind.exclude_self_transfers(all_tx)

        monthly = ind.monthly_evolution(all_tx_real)
        latest_month = monthly.iloc[-1]["month"]
        latest_label = month_label_fmt(latest_month)
        latest_df = all_tx_real[all_tx_real["month"] == latest_month]
        summary = ind.period_summary(latest_df)

        months_sorted = sorted(all_tx_real["month"].unique())
        idx = months_sorted.index(latest_month)
        prev_summary = None
        if idx > 0:
            df_prev = all_tx_real[all_tx_real["month"] == months_sorted[idx - 1]]
            prev_summary = ind.period_summary(df_prev)
        delta = ind.month_over_month_delta(summary, prev_summary)

        latest_assets = self.asset_repo.get_latest_positions()
        patrimonio_total = float(latest_assets["saldo_liquido"].sum()) if not latest_assets.empty else 0.0

        # Rentabilidade real do mês (não a variação bruta do saldo entre
        # snapshots) — ver nota em app.py / memória do projeto: ativos que
        # recebem aportes/resgates com frequência tornam a variação bruta
        # enganosa. Rentabilidade de cota já isola esse efeito.
        taxa_mes = proj.weighted_avg_rentabilidade(latest_assets, campo="rentabilidade_mes_pct")
        benchmarks = latest_assets["benchmark"].dropna().unique() if not latest_assets.empty else []
        benchmark_mes = (
            proj.weighted_avg_rentabilidade(latest_assets, campo="benchmark_mes_pct")
            if len(benchmarks) == 1 else None
        )
        benchmark_nome = benchmarks[0] if len(benchmarks) == 1 else None

        diagnostics = self.diagnostics_for_month(all_tx, all_tx_real, latest_month, latest_label)

        saldo_medio_3m = proj.average_monthly_saldo(monthly, janela=3)
        projecao_12m = None
        if saldo_medio_3m > 0:
            taxa_12m = proj.weighted_avg_rentabilidade(latest_assets, campo="rentabilidade_12m_pct")
            if taxa_12m is not None:
                df_proj = proj.project_patrimonio_com_rendimento(patrimonio_total, saldo_medio_3m, taxa_12m, meses=12)
            else:
                df_proj = proj.project_patrimonio(patrimonio_total, saldo_medio_3m, meses=12)
            projecao_12m = float(df_proj.iloc[-1]["patrimonio_projetado"])

        return {
            "has_data": True,
            "mes": latest_month,
            "mes_label": latest_label,
            "patrimonio_total": patrimonio_total,
            "taxa_mes_pct": taxa_mes,
            "benchmark_mes_pct": benchmark_mes,
            "benchmark_nome": benchmark_nome,
            "saldo": float(summary["saldo"]),
            "taxa_poupanca_pct": float(summary["taxa_poupanca"]),
            "delta_saldo_pct": delta["saldo"],
            "saldo_medio_3m": saldo_medio_3m,
            "projecao_12m": projecao_12m,
            "diagnostics": [diagnostic_to_dict(d) for d in diagnostics],
        }
