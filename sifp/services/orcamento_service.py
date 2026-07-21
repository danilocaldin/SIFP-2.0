"""
orcamento_service.py
---------------------
Composição para a tela "Orçamento": limites por categoria, quanto já foi
gasto no mês mais recente em cada uma, e uma sugestão de valor inicial
baseada na média histórica — mesmo padrão dos outros *_service.py.
Metas (Módulo 14) não precisam de composição própria: é CRUD puro sobre
GoalRepository, sem nenhum cálculo extra, então a API chama o repository
direto (ver sifp/api/main.py).
"""

from __future__ import annotations

import pandas as pd

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO, CATEGORIAS_PADRAO
from sifp.services import indicator_service as ind


class OrcamentoService:
    def __init__(self, transaction_repo, budget_repo):
        self.transaction_repo = transaction_repo
        self.budget_repo = budget_repo

    def build_orcamento(self) -> dict:
        all_tx = self.transaction_repo.get_all()

        media_gasto_map: dict[str, float] = {}
        gasto_atual_map: dict[str, float] = {}
        if not all_tx.empty:
            all_tx["date"] = pd.to_datetime(all_tx["date"])
            all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)
            all_tx_real = ind.exclude_self_transfers(all_tx)

            media_by_cat = ind.average_spend_by_category(all_tx_real, janela=3)
            media_gasto_map = dict(zip(media_by_cat["category"], media_by_cat["media_mensal"]))

            latest_month = all_tx_real["month"].max()
            latest_df = all_tx_real[all_tx_real["month"] == latest_month]
            by_cat = ind.category_breakdown(latest_df)
            gasto_atual_map = dict(zip(by_cat["category"], by_cat["value_abs"]))

        limits_df = self.budget_repo.get_all()
        limits = [
            {
                "category": row["category"],
                "limite_mensal": float(row["limite_mensal"]),
                "gasto_atual": float(gasto_atual_map.get(row["category"], 0.0)),
            }
            for _, row in limits_df.iterrows()
        ]

        categorias_disponiveis = [c for c in CATEGORIAS_PADRAO if c != CATEGORIA_NAO_CATEGORIZADO]

        return {
            "categorias": categorias_disponiveis,
            "sugestoes": {c: media_gasto_map[c] for c in categorias_disponiveis if c in media_gasto_map},
            "limites": limits,
        }
