"""
projecoes_service.py
---------------------
Composição para a tela "Projeções": projeção de patrimônio (com/sem
rendimento composto dos investimentos) e ETA de cada meta no ritmo atual
de poupança. Mesmo padrão dos outros *_service.py — compartilhado entre
o app Streamlit e a API REST.
"""

from __future__ import annotations

import pandas as pd

from sifp.services import indicator_service as ind
from sifp.services import projection_service as proj


class ProjecoesService:
    def __init__(self, transaction_repo, asset_repo, goal_repo):
        self.transaction_repo = transaction_repo
        self.asset_repo = asset_repo
        self.goal_repo = goal_repo

    def build_projecoes(self, horizonte: int = 12) -> dict:
        all_tx = self.transaction_repo.get_all()
        if all_tx.empty:
            return {"has_data": False}

        all_tx["date"] = pd.to_datetime(all_tx["date"])
        all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)
        all_tx_real = ind.exclude_self_transfers(all_tx)
        monthly = ind.monthly_evolution(all_tx_real)
        saldo_medio = proj.average_monthly_saldo(monthly, janela=3)

        latest_assets = self.asset_repo.get_latest_positions()
        patrimonio_atual = float(latest_assets["saldo_liquido"].sum()) if not latest_assets.empty else 0.0
        taxa_12m = proj.weighted_avg_rentabilidade(latest_assets, campo="rentabilidade_12m_pct")

        result = {
            "has_data": True,
            "saldo_medio_3m": saldo_medio,
            "patrimonio_atual": patrimonio_atual,
            "taxa_rentabilidade_12m": taxa_12m,
            "horizonte": horizonte,
            "patrimonio_final": None,
            "chart": [],
            "goals": self._build_goals(saldo_medio),
        }

        if saldo_medio > 0:
            if taxa_12m is not None:
                df_proj = proj.project_patrimonio_com_rendimento(
                    patrimonio_atual, saldo_medio, taxa_12m, meses=horizonte
                )
            else:
                df_proj = proj.project_patrimonio(patrimonio_atual, saldo_medio, meses=horizonte)
            result["patrimonio_final"] = float(df_proj.iloc[-1]["patrimonio_projetado"])
            result["chart"] = self._build_chart(df_proj, patrimonio_atual)

        return result

    def _build_chart(self, df_proj: pd.DataFrame, patrimonio_atual: float) -> list[dict]:
        hist = ind.net_worth_history(self.asset_repo.get_all())
        if hist.empty:
            return []

        hist = hist.copy()
        hist["data_referencia"] = pd.to_datetime(hist["data_referencia"])
        chart = [
            {"data": row["data_referencia"].strftime("%Y-%m-%d"), "patrimonio": float(row["patrimonio_total"]), "tipo": "historico"}
            for _, row in hist.iterrows()
        ]

        last_date = hist["data_referencia"].iloc[-1]
        chart.append({"data": last_date.strftime("%Y-%m-%d"), "patrimonio": patrimonio_atual, "tipo": "projecao"})
        for _, r in df_proj.iterrows():
            d = last_date + pd.DateOffset(months=int(r["mes_offset"]))
            chart.append({"data": d.strftime("%Y-%m-%d"), "patrimonio": float(r["patrimonio_projetado"]), "tipo": "projecao"})
        return chart

    def _build_goals(self, saldo_medio: float) -> list[dict]:
        goals = self.goal_repo.get_all()
        out = []
        for _, row in goals.iterrows():
            eta = proj.project_goal_eta_months(row["valor_necessario"], row["valor_acumulado"], saldo_medio)
            prazo = pd.to_datetime(row["prazo"])
            entry = {
                "id": int(row["id"]),
                "nome": row["nome"],
                "valor_necessario": float(row["valor_necessario"]),
                "valor_acumulado": float(row["valor_acumulado"]),
                "prazo": prazo.strftime("%Y-%m-%d"),
                "eta_meses": eta,
                "data_prevista": None,
                "dentro_do_prazo": None,
            }
            if eta is not None and eta > 0:
                data_prevista = pd.Timestamp.today() + pd.DateOffset(months=eta)
                entry["data_prevista"] = data_prevista.strftime("%Y-%m-%d")
                entry["dentro_do_prazo"] = bool(data_prevista <= prazo)
            out.append(entry)
        return out
