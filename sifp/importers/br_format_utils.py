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


def normalize_description_key(description: str) -> str:
    """Chave de comparação pra "memória" de categoria por descrição
    (TransactionRepository.get_learned_categories) -- achado real de
    auditoria: agrupar/comparar pela descrição crua (sem tirar
    acento/caixa) fazia a mesma contraparte ("José Silva" vs "JOSE
    SILVA", conforme o banco formata o extrato) virar duas entradas
    diferentes na memória, perdendo a categorização já confirmada pelo
    usuário sempre que a formatação variava."""
    return strip_accents(description or "").strip().upper()


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
    Exemplos aceitos: '1.234,56' | 'R$ 1.234,56' | '-45,00' | '45,00 D' |
    '1.500' (sem decimais) | '500 D' (débito sem decimais) | '(150,00)'
    (negativo entre parênteses, convenção contábil).
    Números já numéricos (int/float, como vêm de células do Excel) passam
    direto, sem tentar re-interpretar o separador decimal.
    """
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    negative = False

    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]

    # Achado real de auditoria: \bD\b exige uma fronteira de palavra dos
    # dois lados, mas "D"/dígito são ambos \w -- em "45,00D" (sufixo
    # colado, sem espaço) não há fronteira nenhuma entre o "0" e o "D", e
    # o débito virava positivo silenciosamente. O sufixo de débito/crédito
    # sempre vem no FINAL do valor (com ou sem espaço antes) -- checar
    # isso diretamente cobre os dois formatos sem exigir separador.
    if re.search(r"\d\s*D$", s.upper()):
        negative = True
    if "-" in s:
        negative = True

    s = re.sub(r"[Rr]\$", "", s)
    s = s.replace(" ", "")
    s = re.sub(r"[A-Za-z]", "", s)  # remove sufixos tipo 'D'/'C'
    s = s.replace("-", "")

    # formato brasileiro: ponto SEMPRE separa milhar (nunca é decimal),
    # vírgula é o separador decimal quando presente. Precisa remover o
    # ponto incondicionalmente -- não só quando há vírgula -- senão um
    # valor redondo em milhares sem decimais ('1.500') vira 1.5 (float()
    # interpreta o ponto como decimal), erro de 3 ordens de grandeza.
    s = s.replace(".", "")
    if "," in s:
        s = s.replace(",", ".")

    try:
        num = float(s) if s else 0.0
    except ValueError:
        num = 0.0

    return -abs(num) if negative else num


def parse_brl_date(value):
    """Converte data em formato brasileiro (dd/mm/aaaa[ hh:mm]) para datetime.

    format="mixed" é essencial aqui: sem ele, pd.to_datetime infere o
    formato a partir do PRIMEIRO valor da coluna e aplica esse mesmo
    formato a todos os outros -- uma coluna real com "05/01/2026 14:30"
    e "06/01/2026" misturados (com/sem horário) faz a linha minoritária
    virar NaT e ser descartada em silêncio pelo importador, mesmo sendo
    uma data brasileira perfeitamente válida.
    """
    return pd.to_datetime(value, dayfirst=True, format="mixed", errors="coerce")
