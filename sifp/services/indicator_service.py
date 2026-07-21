"""
services/indicator_service.py
--------------------------------
Módulo 9 — Indicadores financeiros. Funções puras: recebem um DataFrame
de transações já categorizado e devolvem números/DataFrames prontos para
exibição. Nenhuma chamada a Streamlit ou banco de dados aqui — por isso
são fáceis de testar isoladamente e reaproveitar (relatórios, futuros
diagnósticos automáticos etc. usam exatamente estas mesmas funções, em
vez de reimplementar o cálculo).

Extraído de app.py, onde esses cálculos viviam misturados com a
renderização da tela.
"""

import pandas as pd

from sifp.domain.categories import SELF_TRANSFER_CATEGORY


def exclude_self_transfers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove transferências entre contas próprias do titular (ex: indo para
    investimentos e voltando). Não são receita nem despesa real — é o
    mesmo dinheiro mudando de lugar — e contá-las gera um "fluxo falso"
    nos indicadores abaixo.
    """
    return df[df["category"] != SELF_TRANSFER_CATEGORY]


def period_summary(df: pd.DataFrame) -> dict:
    """Receitas, despesas, saldo e taxa de poupança de um período (já
    filtrado por mês e sem transferências internas)."""
    receitas = df[df["value"] > 0]["value"].sum()
    despesas = df[df["value"] < 0]["value"].abs().sum()
    saldo = receitas - despesas
    taxa_poupanca = (saldo / receitas * 100) if receitas > 0 else 0.0
    return {
        "receitas": receitas,
        "despesas": despesas,
        "saldo": saldo,
        "taxa_poupanca": taxa_poupanca,
    }


def month_over_month_delta(current: dict, previous: dict | None) -> dict:
    """Variação percentual de cada métrica de period_summary() vs o mês anterior."""
    if not previous:
        return {"receitas": None, "despesas": None, "saldo": None}

    def pct(atual, anterior):
        if anterior in (None, 0):
            return None
        return (atual - anterior) / abs(anterior) * 100

    return {
        "receitas": pct(current["receitas"], previous["receitas"]),
        "despesas": pct(current["despesas"], previous["despesas"]),
        "saldo": pct(current["saldo"], previous["saldo"]),
    }


def category_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Gastos por categoria (só despesas), do maior pro menor, com % do total."""
    gastos = df[df["value"] < 0].copy()
    if gastos.empty:
        return pd.DataFrame(columns=["category", "value_abs", "pct"])
    gastos["value_abs"] = gastos["value"].abs()
    by_cat = gastos.groupby("category", as_index=False)["value_abs"].sum()
    by_cat = by_cat.sort_values("value_abs", ascending=False).reset_index(drop=True)
    total = by_cat["value_abs"].sum()
    by_cat["pct"] = (by_cat["value_abs"] / total * 100) if total else 0.0
    return by_cat


def merchant_concentration(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Gastos por estabelecimento (Módulo 4 + 9) — usa o nome canônico do
    MerchantNormalizer, então "UBER TRIP" e "UBER*123" somam juntos."""
    gastos = df[(df["value"] < 0) & (df["merchant"].fillna("") != "")].copy()
    if gastos.empty:
        return pd.DataFrame(columns=["merchant", "value_abs", "n_transacoes"])
    gastos["value_abs"] = gastos["value"].abs()
    by_merchant = gastos.groupby("merchant", as_index=False).agg(
        value_abs=("value_abs", "sum"), n_transacoes=("value_abs", "count")
    )
    return by_merchant.sort_values("value_abs", ascending=False).head(n).reset_index(drop=True)


def monthly_evolution(df: pd.DataFrame) -> pd.DataFrame:
    """Receita/Despesa/Saldo por mês (já sem transferências internas), para
    comparar a evolução ao longo do tempo."""
    if df.empty:
        return pd.DataFrame(columns=["month", "Receitas", "Despesas", "Saldo"])
    work = df.copy()
    work["month"] = pd.to_datetime(work["date"]).dt.to_period("M").astype(str)
    monthly = work.groupby("month").apply(
        lambda d: pd.Series(
            {
                "Receitas": d[d["value"] > 0]["value"].sum(),
                "Despesas": d[d["value"] < 0]["value"].abs().sum(),
            }
        )
    ).reset_index()
    monthly["Saldo"] = monthly["Receitas"] - monthly["Despesas"]
    return monthly.sort_values("month").reset_index(drop=True)


def top_expenses(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Os N maiores gastos individuais do período (complementa a visão por
    categoria — às vezes um lançamento único é mais revelador que a soma)."""
    top = df[df["value"] < 0].copy()
    if top.empty:
        return pd.DataFrame(columns=["date", "description", "category", "value_abs"])
    top["value_abs"] = top["value"].abs()
    return top.sort_values("value_abs", ascending=False).head(n).reset_index(drop=True)


def self_transfer_total(df: pd.DataFrame) -> float:
    """Quanto foi movimentado entre contas próprias no período (nota de
    transparência: não conta como receita/despesa, mas o usuário deve ver o valor)."""
    return df[df["category"] == SELF_TRANSFER_CATEGORY]["value"].abs().sum()


def category_trend(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gasto por categoria E por mês (ao contrário de category_breakdown, que
    só olha um período de cada vez). Base para detectar tendências — ex:
    "gastos com Lazer cresceram X% nos últimos 3 meses" — que category_breakdown
    sozinho não consegue expressar porque descarta a dimensão tempo.
    """
    gastos = df[df["value"] < 0].copy()
    if gastos.empty:
        return pd.DataFrame(columns=["month", "category", "value_abs"])
    gastos["month"] = pd.to_datetime(gastos["date"]).dt.to_period("M").astype(str)
    gastos["value_abs"] = gastos["value"].abs()
    trend = gastos.groupby(["month", "category"], as_index=False)["value_abs"].sum()
    return trend.sort_values(["month", "value_abs"], ascending=[True, False]).reset_index(drop=True)


def average_spend_by_category(df: pd.DataFrame, janela: int = 3) -> pd.DataFrame:
    """
    Gasto médio mensal por categoria nos últimos `janela` meses com dados.
    Base para sugerir limites de orçamento a partir do histórico real, em
    vez de o usuário ter que adivinhar um valor do zero.
    """
    trend = category_trend(df)
    if trend.empty:
        return pd.DataFrame(columns=["category", "media_mensal"])
    meses_recentes = sorted(trend["month"].unique())[-janela:]
    recorte = trend[trend["month"].isin(meses_recentes)]
    n_meses = len(meses_recentes)
    agg = recorte.groupby("category", as_index=False)["value_abs"].sum()
    agg["media_mensal"] = agg["value_abs"] / n_meses
    return agg[["category", "media_mensal"]].sort_values("media_mensal", ascending=False).reset_index(drop=True)


def weekend_vs_weekday_spending(df: pd.DataFrame) -> dict:
    """
    Gasto médio por DIA de fim de semana vs dia útil, considerando todo o
    período recebido (não só um mês — é um padrão comportamental, quanto
    mais histórico, mais confiável a média). Compara médias por dia (não
    somas totais), porque há mais dias úteis que de fim de semana numa
    semana normal — comparar somas distorceria a favor dos dias úteis.
    """
    despesas = df[df["value"] < 0].copy()
    if despesas.empty:
        return {"media_fim_de_semana": 0.0, "media_dia_util": 0.0, "dias_fim_de_semana": 0, "dias_uteis": 0}

    despesas["date"] = pd.to_datetime(despesas["date"])
    despesas["dia"] = despesas["date"].dt.date
    despesas["fim_de_semana"] = despesas["date"].dt.dayofweek >= 5  # 5=sábado, 6=domingo

    por_dia = despesas.groupby(["dia", "fim_de_semana"])["value"].sum().abs().reset_index()
    dias_fds = por_dia[por_dia["fim_de_semana"]]
    dias_uteis = por_dia[~por_dia["fim_de_semana"]]

    return {
        "media_fim_de_semana": float(dias_fds["value"].mean()) if not dias_fds.empty else 0.0,
        "media_dia_util": float(dias_uteis["value"].mean()) if not dias_uteis.empty else 0.0,
        "dias_fim_de_semana": len(dias_fds),
        "dias_uteis": len(dias_uteis),
    }


def net_worth_history(assets_df: pd.DataFrame) -> pd.DataFrame:
    """
    Evolução do patrimônio (Módulo 8): soma do saldo líquido de TODOS os
    ativos por data de referência. Cada snapshot importado (um extrato de
    investimento por mês, por exemplo) vira um ponto — com um único
    extrato importado, o resultado é um gráfico de um ponto só, o que é
    esperado até haver mais histórico.

    Recebe o histórico completo (AssetRepository.get_all(), não só as
    posições mais recentes) porque é exatamente a variação ao longo do
    tempo que interessa aqui.
    """
    if assets_df.empty:
        return pd.DataFrame(columns=["data_referencia", "patrimonio_total"])
    grouped = assets_df.groupby("data_referencia", as_index=False)["saldo_liquido"].sum()
    grouped = grouped.rename(columns={"saldo_liquido": "patrimonio_total"})
    return grouped.sort_values("data_referencia").reset_index(drop=True)


def average_balance(balances_df: pd.DataFrame) -> dict:
    """
    Saldo médio da conta corrente e quantos dias essa média representa —
    base para estimar o custo de oportunidade de manter dinheiro parado
    (BalanceRepository.get_all(), o histórico de saldo diário do
    extrato). `dias` conta os registros diários existentes, não o
    calendário — se faltar algum dia no extrato, a média/contagem
    continuam consistentes entre si.
    """
    if balances_df.empty:
        return {"saldo_medio": 0.0, "dias": 0}
    return {"saldo_medio": float(balances_df["balance"].mean()), "dias": len(balances_df)}
