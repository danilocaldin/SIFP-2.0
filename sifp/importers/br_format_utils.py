"""
importers/br_format_utils.py
-----------------------------
Utilidades de parsing compartilháveis por QUALQUER importador de banco
brasileiro (BTG hoje; Inter/Nubank/Santander/XP no futuro): datas
dd/mm/aaaa, moeda com vírgula decimal, remoção de acentos para
comparação de texto. Extraído do parser original para não duplicar essa
lógica a cada novo banco.
"""

import re
import unicodedata

import pandas as pd


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def normalize_col(col) -> str:
    return strip_accents(str(col)).strip().lower()


def find_column(columns_normalized: list[str], aliases: list[str]) -> int | None:
    for i, col in enumerate(columns_normalized):
        for alias in aliases:
            if alias in col:
                return i
    return None


def parse_brl_number(value) -> float:
    """
    Converte string de moeda no formato brasileiro para float.
    Exemplos aceitos: '1.234,56' | 'R$ 1.234,56' | '-45,00' | '45,00 D'
    Números já numéricos (int/float, como vêm de células do Excel) passam
    direto, sem tentar re-interpretar o separador decimal.
    """
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    negative = False

    if re.search(r"\bD\b", s.upper()) and "," in s:
        negative = True
    if "-" in s:
        negative = True

    s = re.sub(r"[Rr]\$", "", s)
    s = s.replace(" ", "")
    s = re.sub(r"[A-Za-z]", "", s)  # remove sufixos tipo 'D'/'C'
    s = s.replace("-", "")

    # formato brasileiro: milhar com ponto, decimal com vírgula
    if "," in s:
        s = s.replace(".", "").replace(",", ".")

    try:
        num = float(s) if s else 0.0
    except ValueError:
        num = 0.0

    return -abs(num) if negative else num


def parse_brl_date(value):
    """Converte data em formato brasileiro (dd/mm/aaaa[ hh:mm]) para datetime."""
    return pd.to_datetime(value, dayfirst=True, errors="coerce")
