"""
projection_service.py
----------------------
Módulo de Projeções (Fase 5). Funções puras — nada de I/O, mesmo padrão do
indicator_service — que estendem o histórico observado para cenários
futuros simples. Deliberadamente lineares (repete o saldo médio recente):
mais fácil de auditar e confiar do que um modelo sofisticado que o usuário
não consegue verificar por conta própria.
"""

from __future__ import annotations

import math

import pandas as pd


def average_monthly_saldo(monthly: pd.DataFrame, janela: int = 3) -> float:
    """Saldo médio mensal dos últimos `janela` meses (ou todos, se houver menos)."""
    if monthly.empty:
        return 0.0
    recent = monthly.tail(janela)
    return float(recent["Saldo"].mean())


def saldo_range(monthly: pd.DataFrame, janela: int = 3) -> dict:
    """Pior, média e melhor saldo mensal observado na janela recente —
    usados pra desenhar não só uma linha de projeção, mas uma faixa entre
    "se o pior mês recente virar a regra" e "se o melhor virar a regra".

    Deliberadamente usa o mínimo/máximo OBSERVADO em vez de um intervalo
    estatístico (ex: desvio-padrão): com só 3-6 meses de histórico esse
    tipo de cálculo é instável, e o ponto do módulo inteiro é ser auditável
    à vista — min/max são meses reais que já aconteceram, não uma
    estimativa que o usuário precisa confiar às cegas."""
    if monthly.empty:
        return {"pior": 0.0, "media": 0.0, "melhor": 0.0}
    recent = monthly.tail(janela)
    return {
        "pior": float(recent["Saldo"].min()),
        "media": float(recent["Saldo"].mean()),
        "melhor": float(recent["Saldo"].max()),
    }


def project_patrimonio(patrimonio_atual: float, saldo_medio_mensal: float, meses: int = 12) -> pd.DataFrame:
    """Projeta o patrimônio mês a mês assumindo que o saldo médio mensal se repete.

    Não considera rendimento dos investimentos — use `project_patrimonio_com_rendimento`
    quando houver uma taxa de rentabilidade conhecida (ver `weighted_avg_rentabilidade`).
    """
    rows = []
    acumulado = patrimonio_atual
    for offset in range(1, meses + 1):
        acumulado += saldo_medio_mensal
        rows.append({"mes_offset": offset, "patrimonio_projetado": acumulado})
    return pd.DataFrame(rows, columns=["mes_offset", "patrimonio_projetado"])


def weighted_avg_rentabilidade(latest_assets: pd.DataFrame, campo: str = "rentabilidade_12m_pct") -> float | None:
    """Rentabilidade ponderada pelo saldo de cada ativo, para o campo pedido
    (`rentabilidade_12m_pct` por padrão; também serve para `rentabilidade_mes_pct`
    ou `benchmark_mes_pct` — qualquer coluna percentual de AssetPosition).

    Usa a rentabilidade real de cada investimento (não o benchmark) porque é
    o que aquele dinheiro de fato rendeu — a base mais defensável pra projetar
    "se nada mudar", e também a única forma correta de falar em "crescimento"
    de um ativo que recebe aportes/resgates com frequência (rentabilidade de
    cota já isola o efeito de aportes/resgates; a variação bruta do saldo entre
    duas datas não isola — ver Resumo tab). None se não há nenhum ativo com o
    campo pedido conhecido.
    """
    if latest_assets is None or latest_assets.empty or campo not in latest_assets.columns:
        return None
    valid = latest_assets.dropna(subset=[campo])
    valid = valid[valid["saldo_liquido"] > 0]
    if valid.empty:
        return None
    total = valid["saldo_liquido"].sum()
    if total <= 0:
        return None
    return float((valid[campo] * valid["saldo_liquido"]).sum() / total)


def project_patrimonio_com_rendimento(
    patrimonio_atual: float, saldo_medio_mensal: float, taxa_anual_pct: float, meses: int = 12
) -> pd.DataFrame:
    """Projeta o patrimônio compondo mensalmente a rentabilidade anualizada
    informada (ex: `weighted_avg_rentabilidade` dos ativos atuais) e somando
    o aporte médio mensal de poupança em cima."""
    taxa_mensal = (1 + taxa_anual_pct / 100) ** (1 / 12) - 1
    rows = []
    acumulado = patrimonio_atual
    for offset in range(1, meses + 1):
        acumulado = acumulado * (1 + taxa_mensal) + saldo_medio_mensal
        rows.append({"mes_offset": offset, "patrimonio_projetado": acumulado})
    return pd.DataFrame(rows, columns=["mes_offset", "patrimonio_projetado"])


def project_goal_eta_months(valor_necessario: float, valor_acumulado: float, saldo_medio_mensal: float) -> int | None:
    """Meses até atingir a meta no ritmo médio de poupança atual.

    Retorna 0 se já atingida, None se o ritmo atual nunca chega lá
    (saldo médio <= 0 com valor ainda faltando).
    """
    faltante = valor_necessario - valor_acumulado
    if faltante <= 0:
        return 0
    if saldo_medio_mensal <= 0:
        return None
    return math.ceil(faltante / saldo_medio_mensal)
