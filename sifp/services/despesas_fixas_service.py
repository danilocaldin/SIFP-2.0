"""
despesas_fixas_service.py
---------------------------
Composição para a tela "Despesas Fixas" (Módulo 17): total mensal
comprometido com despesas fixas declaradas manualmente, comparado contra
a renda média recente — a base pra responder "cabe mais uma dívida?".
Mesmo padrão dos outros *_service.py.
"""

from __future__ import annotations

import pandas as pd

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO, CATEGORIAS_PADRAO
from sifp.services import indicator_service as ind

PREFERENCIA_LIMITE_PCT = "limite_despesas_fixas_pct"

_JANELA_RECEITA_MESES = 3


class DespesasFixasService:
    def __init__(self, despesa_fixa_repo, preferencia_repo, transaction_repo):
        self.despesa_fixa_repo = despesa_fixa_repo
        self.preferencia_repo = preferencia_repo
        self.transaction_repo = transaction_repo

    def _receita_media_mensal(self) -> float:
        all_tx = self.transaction_repo.get_all()
        if all_tx.empty:
            return 0.0
        all_tx = all_tx.copy()
        all_tx["date"] = pd.to_datetime(all_tx["date"])
        all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)
        real = ind.exclude_self_transfers(all_tx)
        monthly = ind.monthly_evolution(real)
        if monthly.empty:
            return 0.0
        return float(monthly["Receitas"].tail(_JANELA_RECEITA_MESES).mean())

    def get_limite_alerta_pct(self) -> float | None:
        valor = self.preferencia_repo.get(PREFERENCIA_LIMITE_PCT)
        return float(valor) if valor is not None else None

    def set_limite_alerta_pct(self, pct: float) -> None:
        self.preferencia_repo.set(PREFERENCIA_LIMITE_PCT, str(pct))

    def build_despesas_fixas(self) -> dict:
        despesas_df = self.despesa_fixa_repo.get_all(apenas_ativas=True)

        despesas = []
        for _, row in despesas_df.iterrows():
            parcelas_totais = row.get("parcelas_totais")
            parcela_atual = row.get("parcela_atual")
            parcelas_restantes = None
            if pd.notna(parcelas_totais) and pd.notna(parcela_atual):
                parcelas_restantes = max(int(parcelas_totais) - int(parcela_atual), 0)
            despesas.append(
                {
                    "id": int(row["id"]),
                    "nome": row["nome"],
                    "categoria": row["categoria"],
                    "valor_mensal": float(row["valor_mensal"]),
                    "tipo": row["tipo"],
                    "data_inicio": row["data_inicio"],
                    "parcela_atual": int(parcela_atual) if pd.notna(parcela_atual) else None,
                    "parcelas_totais": int(parcelas_totais) if pd.notna(parcelas_totais) else None,
                    "parcelas_restantes": parcelas_restantes,
                }
            )

        total_mensal = float(despesas_df["valor_mensal"].sum()) if not despesas_df.empty else 0.0
        receita_media = self._receita_media_mensal()
        pct_comprometido = (total_mensal / receita_media * 100) if receita_media > 0 else None
        margem_mensal = (receita_media - total_mensal) if receita_media > 0 else None

        return {
            "despesas": despesas,
            "total_mensal": total_mensal,
            "receita_media_mensal": receita_media,
            "pct_comprometido": pct_comprometido,
            "margem_mensal": margem_mensal,
            "limite_alerta_pct": self.get_limite_alerta_pct(),
            "categorias": [c for c in CATEGORIAS_PADRAO if c != CATEGORIA_NAO_CATEGORIZADO],
        }
