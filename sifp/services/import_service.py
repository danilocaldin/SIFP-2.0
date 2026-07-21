"""
services/import_service.py
-----------------------------
Orquestra a importação de um extrato: escolhe o importador certo
(Módulo 1), roda o motor de relacionamento e a categorização
(Módulo 3 + 4), e grava via repositories (Módulo 5). Antes, essa
orquestração estava espalhada dentro do app.py (Streamlit) — agora é
testável sem UI nenhuma.
"""

import pandas as pd

from sifp.importers.base import StatementImporter
from sifp.intelligence.categorization import CategorizationService
from sifp.intelligence.merchant_normalizer import MerchantNormalizer
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.transaction_repository import TransactionRepository


class ImportService:
    def __init__(
        self,
        importers: list[StatementImporter],
        categorization: CategorizationService,
        transaction_repo: TransactionRepository,
        balance_repo: BalanceRepository,
        merchant_normalizer: MerchantNormalizer | None = None,
    ):
        self.importers = importers
        self.categorization = categorization
        self.transaction_repo = transaction_repo
        self.balance_repo = balance_repo
        self.merchant_normalizer = merchant_normalizer or MerchantNormalizer()

    def _find_importer(self, filename: str) -> StatementImporter:
        for importer in self.importers:
            if importer.supports(filename):
                return importer
        raise ValueError(
            f"Nenhum importador suporta o arquivo '{filename}'. "
            f"Formatos aceitos: CSV, XLS, XLSX do BTG Pactual."
        )

    def parse(self, uploaded_file) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Só lê e normaliza o arquivo (Módulo 1 + 2), sem categorizar nem
        gravar — usado para a pré-visualização antes do usuário confirmar."""
        importer = self._find_importer(getattr(uploaded_file, "name", ""))
        return importer.read(uploaded_file)

    def categorize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona merchant (Módulo 4) e category/confidence/category_source (Módulo 3)."""
        df = df.copy()
        df["merchant"] = self.merchant_normalizer.normalize_batch(df["description"])

        learned_map = self.transaction_repo.get_learned_categories()
        preds = self.categorization.predict_batch(
            df["description"],
            bank_categories=df.get("bank_category"),
            learned_map=learned_map,
            self_transfers=df.get("self_transfer"),
        )
        return pd.concat([df.reset_index(drop=True), preds.reset_index(drop=True)], axis=1)

    def persist(self, df: pd.DataFrame, balances: pd.DataFrame, source_file: str) -> dict:
        """Categoriza e grava um DataFrame já lido por parse() — separado de
        import_and_persist() porque a UI lê o arquivo uma vez só (para
        mostrar a pré-visualização) e não pode reler o mesmo upload depois
        (o stream já foi consumido)."""
        df_final = self.categorize(df)
        inserted = self.transaction_repo.insert_new(df_final, source_file=source_file)
        saldos_gravados = self.balance_repo.insert_many(balances, source_file=source_file)

        return {
            "total_lidas": len(df_final),
            "inseridas": inserted,
            "ignoradas_duplicadas": len(df_final) - inserted,
            "saldos_gravados": saldos_gravados,
        }

    def import_and_persist(self, uploaded_file) -> dict:
        """Fluxo completo num único passo: ler -> categorizar -> gravar.
        Útil para testes e scripts; a UI usa parse() + persist() separados."""
        df, balances = self.parse(uploaded_file)
        return self.persist(df, balances, source_file=getattr(uploaded_file, "name", ""))
