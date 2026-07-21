"""
intelligence/categorization.py
--------------------------------
CategorizationService: cinco camadas de categorização automática, usadas
em conjunto, da mais para a menos confiável. Lógica portada de
categorizer.py (já validada), reorganizada como classe com o modelo de ML
injetado (em vez de módulo global) para ficar testável sem tocar disco.

0) MEMÓRIA POR DESCRIÇÃO EXATA (aprendida com as suas confirmações)
   Sempre que você revisa e salva uma transação na aba "Revisão", o
   sistema guarda qual categoria você deu para aquela descrição exata.
   Estável (sempre a mesma categoria) -> aplica automaticamente. Variável
   (categorias diferentes ao longo do tempo, ex: Pix para a mesma pessoa
   que às vezes é uma coisa, às vezes é outra) -> força revisão manual
   sempre, porque o próprio histórico prova que não tem significado fixo.

1) TRANSFERÊNCIA PARA SI MESMO (sinal estrutural)
   A "contraparte" da transação é o próprio titular da conta (ex: enviando
   para uma conta investimento). Vira SELF_TRANSFER_CATEGORY, que os
   indicadores excluem de Receita/Despesa.

2) REGRA DE PALAVRA-CHAVE (heurística determinística)
   Dicionário de substrings -> categoria. Funciona desde o primeiro dia.

3) CATEGORIA DO PRÓPRIO BANCO (quando disponível)
   O extrato em Excel do BTG já vem com uma coluna "Categoria".

4) MODELO DE MACHINE LEARNING (aprende com você)
   Pipeline TF-IDF (n-gramas de caracteres) + Regressão Logística.
   TF-IDF de caracteres (não de palavras) porque descrições de extrato
   bancário são cheias de códigos/CNPJs/abreviações; n-gramas de
   caracteres generalizam melhor nesse cenário. Regressão Logística é
   leve, treina rápido com poucos dados e devolve probabilidade (usada
   como "confiança").

Se nada bater, 'Não categorizado' com confiança 0.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO, SELF_TRANSFER_CATEGORY
from sifp.domain.models import CategorySource, CategorySuggestion
from sifp.importers.br_format_utils import strip_accents

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "categorizer_model.joblib"

# Regras de palavra-chave (case/acento-insensitive, substring match).
# Sinta-se à vontade para editar/expandir com seus próprios estabelecimentos.
KEYWORD_RULES = {
    "Mercado": ["MERCADO", "SUPERMERCADO", "ATACAD", "CARREFOUR", "PAO DE ACUCAR",
                "ASSAI", "EXTRA HIPER", "DIA SUPERMERCADO"],
    "Transporte": ["UBER", "99APP", "99POP", "POSTO", "COMBUSTIVEL", "IPVA",
                   "ESTACIONAMENTO", "PEDAGIO", "METRO", "BILHETE UNICO"],
    "Alimentação": ["IFOOD", "RAPPI", "RESTAURANTE", "LANCHONETE", "PADARIA",
                    "BAR ", "PIZZARIA", "BURGER", "MCDONALD", "STARBUCKS"],
    "Lazer": ["CINEMA", "INGRESSO", "STEAM", "PLAYSTATION", "XBOX", "SPOTIFY",
              "SHOW ", "TEATRO", "BALADA"],
    "Moradia": ["ALUGUEL", "CONDOMINIO", "IPTU", "IMOBILIARIA", "REFORMA"],
    "Saúde": ["FARMACIA", "DROGARIA", "HOSPITAL", "CLINICA", "PLANO DE SAUDE",
              "UNIMED", "AMIL", "LABORATORIO"],
    "Educação": ["FACULDADE", "UNIVERSIDADE", "ESCOLA", "CURSO", "UDEMY",
                 "ALURA", "MENSALIDADE ESCOLAR"],
    "Salário/Receita": ["SALARIO", "PROVENTOS", "PIX RECEBIDO", "TED RECEBID",
                         "RENDIMENTO", "DIVIDENDO"],
    "Assinaturas": ["NETFLIX", "AMAZON PRIME", "DISNEY", "HBO", "YOUTUBE PREMIUM",
                     "ASSINATURA", "ICLOUD", "GOOGLE ONE"],
    "Compras": ["MERCADO LIVRE", "AMAZON", "SHOPEE", "MAGAZINE LUIZA",
                "AMERICANAS", "SHEIN"],
    "Transferências": ["PIX ENVIADO", "TED ENVIAD", "DOC ENVIAD", "TRANSFERENCIA"],
    "Investimentos": ["TESOURO DIRETO", "APLICACAO", "RESGATE", "CDB", "FUNDO DE INVESTIMENTO"],
}

# Categoria bruta do BTG (coluna "Categoria" do extrato em Excel) -> nossa
# taxonomia. "Outra Categoria" é o cesto genérico do próprio BTG
# (equivalente ao nosso "Não categorizado") e por isso fica de fora —
# quando aparece, deixamos as próximas camadas decidirem.
BTG_CATEGORY_MAP = {
    "supermercado": "Mercado",
    "transporte": "Transporte",
    "alimentacao": "Alimentação",
    "saude": "Saúde",
    "investimentos": "Investimentos",
    "transferencia": "Transferências",
    "compras": "Compras",
    "tarifas": "Tarifas",
    "contas": "Contas",
    "cuidados pessoais": "Cuidados Pessoais",
    "lazer": "Lazer",
    "moradia": "Moradia",
    "educacao": "Educação",
}


def apply_keyword_rules(description: str) -> str | None:
    desc_upper = strip_accents(description).upper()
    for category, keywords in KEYWORD_RULES.items():
        for kw in keywords:
            if strip_accents(kw).upper() in desc_upper:
                return category
    return None


def map_bank_category(bank_category: str | None) -> str | None:
    if not bank_category:
        return None
    key = strip_accents(str(bank_category)).strip().lower()
    return BTG_CATEGORY_MAP.get(key)


_PIX_OR_TRANSFER_PREFIX = ("pix", "transfer")


def is_pix_or_transfer(description: str) -> bool:
    """
    Distingue "estabelecimento" (compra, boleto, dividendo — tende a
    significar sempre a mesma coisa) de "Pix/Transferência para uma
    pessoa" (pode significar coisas diferentes a cada vez). Usado na tela
    de Revisão para decidir o que é seguro categorizar em lote por
    descrição versus o que deve continuar sendo revisado uma a uma.
    """
    desc_norm = strip_accents(str(description)).strip().lower()
    return desc_norm.startswith(_PIX_OR_TRANSFER_PREFIX)


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, lowercase=True),
            ),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )


class CategorizationService:
    MIN_SAMPLES = 8
    MIN_CLASSES = 2

    LEARNED_STABLE_CONFIDENCE = 0.97
    SELF_TRANSFER_CONFIDENCE = 0.95
    RULE_CONFIDENCE = 0.99
    BANK_CATEGORY_CONFIDENCE = 0.9

    def __init__(self, model: Pipeline | None = None, model_path: Path = DEFAULT_MODEL_PATH):
        self.model = model
        self.model_path = model_path

    @classmethod
    def load(cls, model_path: Path = DEFAULT_MODEL_PATH) -> "CategorizationService":
        model = joblib.load(model_path) if model_path.exists() else None
        return cls(model=model, model_path=model_path)

    def train(self, training_df: pd.DataFrame) -> str:
        """
        Treina (ou re-treina) o modelo com as transações já classificadas
        manualmente, salva em disco e atualiza self.model. Retorna
        mensagem de status.
        """
        if training_df is None or training_df.empty:
            return "Ainda não há transações classificadas para treinar o modelo."

        n_samples = len(training_df)
        n_classes = training_df["category"].nunique()

        if n_samples < self.MIN_SAMPLES or n_classes < self.MIN_CLASSES:
            return (
                f"Poucos dados para treinar o modelo ainda "
                f"({n_samples} exemplos em {n_classes} categorias). "
                f"Continue classificando manualmente — assim que houver pelo menos "
                f"{self.MIN_SAMPLES} transações em {self.MIN_CLASSES}+ categorias, "
                f"o modelo de ML entra em ação automaticamente."
            )

        pipeline = build_pipeline()
        pipeline.fit(training_df["description"], training_df["category"])
        joblib.dump(pipeline, self.model_path)
        self.model = pipeline

        return f"Modelo treinado com {n_samples} exemplos em {n_classes} categorias."

    def predict(
        self,
        description: str,
        bank_category: str | None = None,
        learned_map: dict | None = None,
        self_transfer: bool = False,
    ) -> CategorySuggestion:
        if learned_map and description in learned_map:
            entry = learned_map[description]
            if entry["variable"]:
                return CategorySuggestion(
                    CATEGORIA_NAO_CATEGORIZADO, 0.0, CategorySource.LEARNED_VARIABLE
                )
            return CategorySuggestion(
                entry["category"], self.LEARNED_STABLE_CONFIDENCE, CategorySource.LEARNED_STABLE
            )

        if self_transfer:
            return CategorySuggestion(
                SELF_TRANSFER_CATEGORY, self.SELF_TRANSFER_CONFIDENCE, CategorySource.SELF_TRANSFER
            )

        rule_hit = apply_keyword_rules(description)
        if rule_hit:
            return CategorySuggestion(rule_hit, self.RULE_CONFIDENCE, CategorySource.KEYWORD_RULE)

        mapped_bank_cat = map_bank_category(bank_category)
        if mapped_bank_cat:
            return CategorySuggestion(
                mapped_bank_cat, self.BANK_CATEGORY_CONFIDENCE, CategorySource.BANK_CATEGORY
            )

        if self.model is not None:
            try:
                proba = self.model.predict_proba([description])[0]
                classes = self.model.classes_
                best_idx = proba.argmax()
                return CategorySuggestion(
                    classes[best_idx], float(proba[best_idx]), CategorySource.ML_MODEL
                )
            except Exception:
                pass

        return CategorySuggestion(CATEGORIA_NAO_CATEGORIZADO, 0.0, CategorySource.NONE)

    def predict_batch(
        self,
        descriptions: pd.Series,
        bank_categories: pd.Series | None = None,
        learned_map: dict | None = None,
        self_transfers: pd.Series | None = None,
    ) -> pd.DataFrame:
        if bank_categories is None:
            bank_categories = pd.Series([None] * len(descriptions), index=descriptions.index)
        if self_transfers is None:
            self_transfers = pd.Series([False] * len(descriptions), index=descriptions.index)

        results = [
            self.predict(desc, bcat, learned_map, bool(is_self))
            for desc, bcat, is_self in zip(descriptions, bank_categories, self_transfers)
        ]
        return pd.DataFrame(
            {
                "category": [r.category for r in results],
                "confidence": [r.confidence for r in results],
                "category_source": [r.source.value for r in results],
            }
        )
