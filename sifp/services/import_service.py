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

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO, CATEGORIAS_PADRAO
from sifp.importers.base import StatementImporter
from sifp.intelligence.categorization import CategorizationService, is_pix_or_transfer
from sifp.intelligence.merchant_normalizer import MerchantNormalizer
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.transaction_repository import TransactionRepository, make_tx_hash, normalize_tx_date


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
        inserted_hashes = self.transaction_repo.insert_new(df_final, source_file=source_file)
        saldos_gravados = self.balance_repo.insert_many(balances, source_file=source_file)

        return {
            "total_lidas": len(df_final),
            "inseridas": len(inserted_hashes),
            "ignoradas_duplicadas": len(df_final) - len(inserted_hashes),
            "saldos_gravados": saldos_gravados,
            "revisao_pendente": self._revisao_pendente(df_final, inserted_hashes),
            "categorias": CATEGORIAS_PADRAO,
        }

    def _revisao_pendente(self, df_final: pd.DataFrame, inserted_hashes: list[str]) -> list[dict]:
        """Entre as linhas recém-inseridas (não as duplicadas ignoradas),
        seleciona o que vale a pena perguntar pro usuário logo após o
        upload: toda transferência pra outra pessoa (Pix/Transferência
        sempre pode significar algo diferente a cada vez, mesmo pra mesma
        pessoa) e todo estabelecimento que o sistema não teve confiança
        suficiente pra categorizar sozinho (o BTG nem sempre categoriza
        certo). Transferência entre contas do próprio usuário
        (self_transfer) fica de fora — já é detectada com certeza e
        categorizada automaticamente, perguntar de novo seria ruído."""
        df = df_final.copy()
        df["date"] = df["date"].apply(normalize_tx_date)
        df["tx_hash"] = df.apply(
            lambda r: make_tx_hash(r["date"], r["description"], r["value"]), axis=1
        )
        novos = df[df["tx_hash"].isin(inserted_hashes)]
        # .astype(bool): numa Series vazia, .apply() numa coluna PyArrow-backed
        # infere dtype "str" em vez de "bool" (não tem elemento pra inferir
        # de verdade), e "str" | "bool" explode — ver gotcha já documentada
        # sobre pandas 3.0 + PyArrow em CLAUDE do projeto.
        is_transfer = novos["description"].apply(is_pix_or_transfer).astype(bool)
        is_self_transfer = novos["self_transfer"].astype(bool)
        novos = novos.assign(is_transfer=is_transfer)
        precisa_revisao = novos[
            (is_transfer & ~is_self_transfer) | (novos["category"] == CATEGORIA_NAO_CATEGORIZADO)
        ]
        records = precisa_revisao[
            ["tx_hash", "date", "description", "value", "category", "is_transfer"]
        ].to_dict("records")
        # tipos nativos Python -- numpy.bool_/numpy.float64 não serializam
        # em JSON (ver mesma sanitização em sifp/api/main.py).
        for r in records:
            r["value"] = float(r["value"])
            r["is_transfer"] = bool(r["is_transfer"])
        return records

    def import_and_persist(self, uploaded_file) -> dict:
        """Fluxo completo num único passo: ler -> categorizar -> gravar.
        Útil para testes e scripts; a UI usa parse() + persist() separados."""
        df, balances = self.parse(uploaded_file)
        return self.persist(df, balances, source_file=getattr(uploaded_file, "name", ""))
