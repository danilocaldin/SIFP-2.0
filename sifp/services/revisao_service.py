"""
revisao_service.py
--------------------
Composição para a tela "Revisão de Categorias": monta a lista de
transações com a coluna "situação" (por que o sistema sugeriu, ou não,
aquela categoria) e agrupa estabelecimentos pendentes pra categorização
em lote — mesma lógica que já existia embutida em app.py (Streamlit),
extraída pra ser compartilhada com a API REST e nunca divergir.
"""

from __future__ import annotations

import pandas as pd

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO, CATEGORIAS_PADRAO, SELF_TRANSFER_CATEGORY
from sifp.intelligence.categorization import is_pix_or_transfer


def _situacao(row, learned_map: dict) -> str:
    entry = learned_map.get(row["description"])
    if entry and entry["variable"]:
        hist = ", ".join(f"{c} ({n}x)" for c, n in entry["history"])
        return f"Variável — já foi: {hist}"
    if bool(row.get("self_transfer")) and row["category"] == SELF_TRANSFER_CATEGORY:
        return "Transferência interna (detectada automaticamente)"
    if row["confidence"] >= 0.95:
        return "Alta confiança"
    if row["confidence"] >= 0.6:
        return "Conferir"
    return "Novo / revisar"


class RevisaoService:
    def __init__(self, transaction_repo):
        self.transaction_repo = transaction_repo

    def build_revisao(self) -> dict:
        all_tx = self.transaction_repo.get_all()
        if all_tx.empty:
            return {"has_data": False}

        all_tx = all_tx.copy()
        learned_map = self.transaction_repo.get_learned_categories()
        all_tx["situacao"] = all_tx.apply(lambda row: _situacao(row, learned_map), axis=1)
        all_tx["date"] = pd.to_datetime(all_tx["date"]).dt.strftime("%Y-%m-%d %H:%M")

        pending = all_tx[all_tx["category"] == CATEGORIA_NAO_CATEGORIZADO]
        establishment_pending = pending[~pending["description"].apply(is_pix_or_transfer)]
        lote_pendentes = (
            establishment_pending.groupby("description")
            .size()
            .reset_index(name="quantidade")
            .sort_values("quantidade", ascending=False)
            .rename(columns={"description": "descricao"})
        )
        lote_pendentes["quantidade"] = lote_pendentes["quantidade"].astype(int)

        return {
            "has_data": True,
            "total": len(all_tx),
            "categorias": CATEGORIAS_PADRAO,
            "categoria_nao_categorizada": CATEGORIA_NAO_CATEGORIZADO,
            "transactions": all_tx[
                ["tx_hash", "date", "description", "value", "bank_category", "situacao", "category", "confidence"]
            ].to_dict("records"),
            "lote_pendentes": lote_pendentes.to_dict("records"),
        }

    def bulk_apply_by_description(self, description: str, category: str) -> int:
        """Aplica `category` a todas as transações atualmente pendentes com
        essa descrição exata (mesmo escopo do agrupamento em `build_revisao`).
        Retorna quantas linhas foram atualizadas."""
        all_tx = self.transaction_repo.get_all()
        pending = all_tx[all_tx["category"] == CATEGORIA_NAO_CATEGORIZADO]
        hashes = pending.loc[pending["description"] == description, "tx_hash"].tolist()
        if hashes:
            self.transaction_repo.bulk_update_categories([(h, category) for h in hashes])
        return len(hashes)
