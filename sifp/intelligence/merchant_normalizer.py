"""
intelligence/merchant_normalizer.py
-------------------------------------
Módulo 4 — Motor de relacionamento: reconhece que "UBER TRIP", "UBER" e
"UBER*123" (ou, no formato real do BTG, "Compra no débito autorizada -
Uber") representam o MESMO estabelecimento, e devolve um nome canônico
("Uber"). Usado em relatórios/gráficos por estabelecimento (ex:
"Concentração por estabelecimento" do Módulo 9), que sem isso ficariam
fragmentados em várias linhas para o mesmo lugar.

Estratégia: regras determinísticas (limpeza de ruído + dicionário de
aliases), não fuzzy matching probabilístico — mais fácil de auditar e de
estender manualmente, no mesmo espírito das regras de categorização
(intelligence/categorization.py).
"""

import re

import pandas as pd

from sifp.importers.br_format_utils import strip_accents

# Sufixos de razão social comuns em descrições de PJ, sem valor pra
# identificar o estabelecimento pro usuário final.
LEGAL_SUFFIXES = ["LTDA", "EIRELI", "EPP", "ME", "S/A", "SA", "CIA"]

# Nome canônico por token identificador. A busca é feita tanto por
# igualdade quanto por substring (ver normalize()), então uma chave como
# "UBER" também casa com "UBER TRIP", "UBER*RIDE" (já sem o código), etc.
# Sinta-se à vontade para estender — mesmo espírito de KEYWORD_RULES.
MERCHANT_ALIASES = {
    "UBER": "Uber",
    "99APP": "99",
    "99POP": "99",
    "IFOOD": "iFood",
    "RAPPI": "Rappi",
    "NETFLIX": "Netflix",
    "SPOTIFY": "Spotify",
    "AMAZON PRIME": "Amazon Prime",
    "AMAZON": "Amazon",
    "MERCADO LIVRE": "Mercado Livre",
    "SHOPEE": "Shopee",
    "MAGAZINE LUIZA": "Magazine Luiza",
    "AMERICANAS": "Americanas",
    "DISNEY": "Disney+",
    "HBO": "HBO Max",
    "STARBUCKS": "Starbucks",
    "MCDONALD": "McDonald's",
    "BURGER KING": "Burger King",
    "CARREFOUR": "Carrefour",
    "ASSAI": "Assaí",
    "PAO DE ACUCAR": "Pão de Açúcar",
    "EXTRA HIPER": "Extra",
    "DROGASIL": "Drogasil",
}

_TRAILING_CODE_RE = re.compile(r"\*.*$")               # "IFOOD*12345" -> "IFOOD"
_LEADING_NUMERIC_RE = re.compile(r"^([\d\s]+?)(?=[^\d\s])")  # captura prefixo numérico (validado por qtde de dígitos abaixo)
_TRAILING_NUMERIC_RE = re.compile(r"\s+\d{2,}$")         # "UBER 123456" -> "UBER"
_MULTISPACE_RE = re.compile(r"\s+")
_SUFFIX_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(s) for s in LEGAL_SUFFIXES) + r")\.?\s*$"
)

# Só tratamos um prefixo numérico como "código de ruído" (documento,
# autorização) quando ele tem bastante dígito pra não ser confundido com
# um nome de marca curto como "99" (99 Pay, 99Táxi).
_MIN_NOISE_DIGITS = 5


def _strip_leading_numeric_code(text: str) -> str:
    match = _LEADING_NUMERIC_RE.match(text)
    if not match:
        return text
    prefix = match.group(1)
    if sum(c.isdigit() for c in prefix) >= _MIN_NOISE_DIGITS:
        return text[len(prefix):].strip()
    return text


class MerchantNormalizer:
    def normalize(self, description: str) -> str:
        text = (description or "").strip()
        if not text:
            return "Desconhecido"

        # Descrições no formato "Tipo de transação - Contraparte" (padrão
        # do extrato em Excel do BTG, e comum em outros bancos BR): o
        # estabelecimento está depois do último " - ".
        if " - " in text:
            text = text.rsplit(" - ", 1)[-1].strip()

        text = _TRAILING_CODE_RE.sub("", text).strip()
        text = _strip_leading_numeric_code(text)
        text = _TRAILING_NUMERIC_RE.sub("", text).strip()

        if not text:
            return "Desconhecido"

        lookup_key = strip_accents(text).upper()
        lookup_key = _SUFFIX_RE.sub("", lookup_key).strip()
        lookup_key = _MULTISPACE_RE.sub(" ", lookup_key).strip()

        if not lookup_key:
            return text.title()

        if lookup_key in MERCHANT_ALIASES:
            return MERCHANT_ALIASES[lookup_key]
        for alias_key, canonical in MERCHANT_ALIASES.items():
            if alias_key in lookup_key:
                return canonical

        return text.title()

    def normalize_batch(self, descriptions: pd.Series) -> pd.Series:
        return descriptions.apply(self.normalize)
