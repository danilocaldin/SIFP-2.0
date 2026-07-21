"""
formatting.py
--------------
Helpers de formatação de exibição — puros, sem I/O — compartilhados entre
o app Streamlit (app.py) e a API REST (sifp/api), pra nunca haver duas
implementações que podem divergir.
"""

MESES_PT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


def formatar_mes(periodo_str: str) -> str:
    """'2026-06' -> 'Jun/2026'"""
    ano, mes = periodo_str.split("-")
    return f"{MESES_PT[int(mes)]}/{ano}"


def unescape_currency(text: str) -> str:
    """Diagnostic.descricao/explicacao/recomendacao vêm com '\\$' escapado
    (pensado para o markdown do Streamlit não confundir 'R$' repetido com
    delimitador de fórmula LaTeX — ver diagnostics._brl). Qualquer consumidor
    que NÃO renderiza markdown (relatório em texto puro, API/JSON pro
    frontend) precisa desfazer isso, senão a barra invertida aparece
    visível pro usuário final."""
    return text.replace("\\$", "$")
