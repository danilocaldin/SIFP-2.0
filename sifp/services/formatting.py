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


def format_brl_number(value: float) -> str:
    """Só o número em padrão brasileiro (milhar com ponto, decimal com
    vírgula), sem o prefixo 'R$' — para compor em textos/tabelas que já
    escrevem o prefixo separadamente (ex: relatório em texto alinhado por
    coluna, onde 'R$' e o número ficam em posições fixas diferentes)."""
    s = f"{value:,.2f}"  # "3,006.49" (Python usa separador dos EUA)
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_brl(value: float) -> str:
    """Valor em R$ no padrão brasileiro, ex: 'R$ 3.006,49'. Uso geral —
    st.metric, dataframes, texto plano, JSON da API."""
    return f"R$ {format_brl_number(value)}"


def format_brl_md(value: float) -> str:
    """Mesma formatação, com o cifrão escapado pra uso dentro de
    st.markdown/st.error/st.warning/st.info/st.write/st.caption do
    Streamlit (ver unescape_currency para o motivo do escape)."""
    return f"R\\$ {format_brl_number(value)}"
