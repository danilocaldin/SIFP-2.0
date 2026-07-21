"""
intelligence/diagnostics.py
------------------------------
Módulo 10 — Diagnósticos automáticos. Cada regra é uma função pura que
recebe dados já calculados pelo IndicatorService (Módulo 9) e devolve
zero ou mais Diagnostic. Nenhuma regra acessa banco de dados ou Streamlit
diretamente — isso mantém cada uma testável isoladamente e reutilizável
em relatórios (Módulo 11) além do dashboard.

Desenhado para crescer: quando Orçamento/Metas (Fase 3) existirem, os
alertas deles viram só mais funções aqui dentro (ex:
check_orcamento_estourado, check_meta_atrasada), adicionadas à lista em
run_diagnostics(). O contrato (Diagnostic) e a forma como a UI consome a
lista não mudam.
"""

import pandas as pd

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO
from sifp.domain.models import Diagnostic, DiagnosticSeverity
from sifp.services.formatting import format_brl_md as _brl

# _brl formata 'R\$ 1.234,56' (padrão brasileiro, '$' escapado): Streamlit
# (e qualquer markdown baseado em markdown-it) trata um par de '$' como
# delimitador de fórmula LaTeX — como as mensagens de diagnóstico costumam
# citar mais de um valor em R$, sem escapar o texto quebra visivelmente.
# Formatar aqui, na origem, evita que cada regra nova precise lembrar disso.


# ---------------------------------------------------------------------
# Limiares — centralizados aqui pra facilitar ajuste sem caçar número
# espalhado pelas regras.
# ---------------------------------------------------------------------
TAXA_POUPANCA_BAIXA_PCT = 10.0
TAXA_POUPANCA_CRITICA_PCT = 0.0
CONCENTRACAO_CATEGORIA_ALTA_PCT = 30.0
MESES_NEGATIVOS_JANELA = 3
MESES_NEGATIVOS_LIMIAR = 2
PENDENTES_QTD_LIMIAR = 15
PENDENTES_PCT_LIMIAR = 5.0
RESERVA_EMERGENCIA_MESES_ALVO = 3.0


def check_saldo_negativo_recorrente(monthly: pd.DataFrame) -> list[Diagnostic]:
    """monthly: saída de indicator_service.monthly_evolution()
    (colunas month, Receitas, Despesas, Saldo)."""
    if monthly.empty:
        return []
    janela = monthly.tail(MESES_NEGATIVOS_JANELA)
    negativos = janela[janela["Saldo"] < 0]
    if len(negativos) < MESES_NEGATIVOS_LIMIAR:
        return []

    meses_str = ", ".join(negativos["month"])
    total_negativo = float(negativos["Saldo"].sum())
    severidade = (
        DiagnosticSeverity.CRITICA if len(negativos) == len(janela) else DiagnosticSeverity.ALTA
    )
    return [
        Diagnostic(
            codigo="saldo_negativo_recorrente",
            titulo="Saldo negativo recorrente",
            severidade=severidade,
            descricao=(
                f"{len(negativos)} dos últimos {len(janela)} meses fecharam no negativo "
                f"({meses_str}), somando {_brl(total_negativo)}."
            ),
            explicacao=(
                "Fechar o mês no vermelho repetidamente significa que as despesas estão "
                "consistentemente maiores que a receita — sem ajuste, isso corrói reservas "
                "ou gera dívida."
            ),
            recomendacao=(
                "Reveja as categorias de maior gasto nesses meses (aba Dashboard) e "
                "identifique o que pode ser reduzido ou adiado."
            ),
            impacto_financeiro=total_negativo,
        )
    ]


def check_taxa_poupanca_baixa(summary: dict, periodo_label: str) -> list[Diagnostic]:
    """summary: saída de indicator_service.period_summary() do mês mais recente."""
    taxa = summary.get("taxa_poupanca")
    if taxa is None or summary.get("receitas", 0) <= 0:
        return []
    if taxa >= TAXA_POUPANCA_BAIXA_PCT:
        return []

    severidade = (
        DiagnosticSeverity.CRITICA if taxa < TAXA_POUPANCA_CRITICA_PCT else DiagnosticSeverity.ALTA
    )
    return [
        Diagnostic(
            codigo="taxa_poupanca_baixa",
            titulo="Taxa de poupança baixa",
            severidade=severidade,
            descricao=(
                f"Em {periodo_label}, você guardou {taxa:.0f}% da renda "
                f"(receita {_brl(summary['receitas'])})."
            ),
            explicacao=(
                "Uma taxa de poupança consistentemente abaixo de 10% deixa pouca margem "
                "para imprevistos ou para construir patrimônio."
            ),
            recomendacao=(
                "Olhe o detalhamento por categoria do mês (aba Dashboard) e priorize cortar "
                "despesas variáveis (lazer, compras) antes das fixas."
            ),
            impacto_financeiro=summary.get("saldo"),
        )
    ]


def check_concentracao_categoria(by_cat: pd.DataFrame, periodo_label: str) -> list[Diagnostic]:
    """by_cat: saída de indicator_service.category_breakdown() do mês mais recente."""
    if by_cat.empty:
        return []
    top = by_cat.iloc[0]
    if top["pct"] < CONCENTRACAO_CATEGORIA_ALTA_PCT:
        return []

    return [
        Diagnostic(
            codigo="concentracao_categoria",
            titulo=f"Concentração alta em {top['category']}",
            severidade=DiagnosticSeverity.MEDIA,
            descricao=(
                f"'{top['category']}' respondeu por {top['pct']:.0f}% das despesas de "
                f"{periodo_label} ({_brl(top['value_abs'])})."
            ),
            explicacao=(
                "Concentrar boa parte do orçamento numa única categoria aumenta o risco de "
                "qualquer imprevisto nela (ex: aumento de aluguel) desequilibrar todo o mês."
            ),
            recomendacao=(
                "Veja se dá pra diversificar ou negociar especificamente essa categoria — "
                "vale mais esforço ali do que em categorias pequenas."
            ),
            impacto_financeiro=float(top["value_abs"]),
        )
    ]


def check_transacoes_pendentes(all_tx: pd.DataFrame) -> list[Diagnostic]:
    """all_tx: TransactionRepository.get_all() (todo o histórico, não só o período)."""
    if all_tx.empty:
        return []
    pendentes = int((all_tx["category"] == CATEGORIA_NAO_CATEGORIZADO).sum())
    total = len(all_tx)
    pct = pendentes / total * 100 if total else 0.0
    if pendentes < PENDENTES_QTD_LIMIAR and pct < PENDENTES_PCT_LIMIAR:
        return []

    return [
        Diagnostic(
            codigo="transacoes_pendentes",
            titulo="Muitas transações sem categoria",
            severidade=DiagnosticSeverity.BAIXA,
            descricao=f"{pendentes} transações ({pct:.0f}% do total) ainda estão como '{CATEGORIA_NAO_CATEGORIZADO}'.",
            explicacao=(
                "Enquanto essas transações não têm categoria, os indicadores de gasto e os "
                "outros diagnósticos ficam incompletos — o valor delas nem entra na análise."
            ),
            recomendacao=(
                "Vá na aba Revisão de Categorias; a categorização em lote resolve rápido o "
                "que for do mesmo estabelecimento."
            ),
            impacto_financeiro=None,
        )
    ]


def check_reserva_emergencia(patrimonio_total: float, despesa_media_mensal: float) -> list[Diagnostic]:
    if despesa_media_mensal <= 0:
        return []
    meses_cobertos = patrimonio_total / despesa_media_mensal
    if meses_cobertos >= RESERVA_EMERGENCIA_MESES_ALVO:
        return []

    severidade = DiagnosticSeverity.CRITICA if meses_cobertos < 1 else DiagnosticSeverity.ALTA
    faltante = (RESERVA_EMERGENCIA_MESES_ALVO * despesa_media_mensal) - patrimonio_total
    return [
        Diagnostic(
            codigo="reserva_emergencia_insuficiente",
            titulo="Reserva de emergência insuficiente",
            severidade=severidade,
            descricao=(
                f"Seu patrimônio atual ({_brl(patrimonio_total)}) cobre "
                f"{meses_cobertos:.1f} mês(es) de despesa, com base numa despesa média de "
                f"{_brl(despesa_media_mensal)}/mês. O recomendado geralmente é ter "
                f"{RESERVA_EMERGENCIA_MESES_ALVO:.0f}+ meses guardados."
            ),
            explicacao=(
                "Sem reserva suficiente, qualquer imprevisto (perda de renda, gasto médico) "
                "força endividamento."
            ),
            recomendacao=(
                "Priorize direcionar parte do saldo positivo dos próximos meses para "
                "investimentos de liquidez imediata até atingir a meta de meses de reserva."
            ),
            impacto_financeiro=faltante,
        )
    ]


ORCAMENTO_EXCESSO_ALTA_PCT = 20.0
META_RISCO_DIAS_RESTANTES = 90
META_RISCO_PROGRESSO_PCT = 50.0


def check_orcamento_estourado(by_cat: pd.DataFrame, limits: dict, periodo_label: str) -> list[Diagnostic]:
    """
    by_cat: indicator_service.category_breakdown() do mês em análise.
    limits: BudgetRepository.get_limits_dict() — {categoria: limite_mensal}.
    Uma categoria sem limite configurado (não está no dict) simplesmente
    não é avaliada — orçamento é opt-in por categoria.
    """
    if by_cat.empty or not limits:
        return []
    diagnostics: list[Diagnostic] = []
    for _, row in by_cat.iterrows():
        limite = limits.get(row["category"])
        if limite is None or limite <= 0:
            continue
        gasto = float(row["value_abs"])
        if gasto <= limite:
            continue
        excesso = gasto - limite
        excesso_pct = excesso / limite * 100
        severidade = (
            DiagnosticSeverity.ALTA if excesso_pct >= ORCAMENTO_EXCESSO_ALTA_PCT else DiagnosticSeverity.MEDIA
        )
        diagnostics.append(
            Diagnostic(
                codigo=f"orcamento_estourado_{row['category']}",
                titulo=f"Orçamento de {row['category']} estourado",
                severidade=severidade,
                descricao=(
                    f"Em {periodo_label}, '{row['category']}' teve {_brl(gasto)} de gasto, "
                    f"{excesso_pct:.0f}% acima do limite de {_brl(limite)}."
                ),
                explicacao=(
                    "Estourar o orçamento planejado repetidamente sinaliza que o limite não "
                    "reflete mais o padrão real de gasto, ou que há espaço pra cortar aqui."
                ),
                recomendacao=(
                    "Ajuste o limite na aba Orçamento e Metas se ele não é mais realista, ou "
                    "reveja os gastos dessa categoria no período (aba Dashboard)."
                ),
                impacto_financeiro=excesso,
            )
        )
    return diagnostics


def check_metas(goals_df: pd.DataFrame, hoje: str | None = None) -> list[Diagnostic]:
    """
    goals_df: GoalRepository.get_all() (colunas id, nome, valor_necessario,
    valor_acumulado, prazo). `hoje` é injetável para teste; em produção
    usa a data atual.
    """
    if goals_df.empty:
        return []
    hoje_ts = pd.Timestamp(hoje) if hoje else pd.Timestamp.now().normalize()

    diagnostics: list[Diagnostic] = []
    for _, row in goals_df.iterrows():
        valor_necessario = float(row["valor_necessario"])
        if valor_necessario <= 0:
            continue
        valor_acumulado = float(row["valor_acumulado"])
        progresso_pct = min(valor_acumulado / valor_necessario * 100, 100.0)
        if progresso_pct >= 100:
            continue  # meta concluída, nada a diagnosticar

        prazo_ts = pd.Timestamp(row["prazo"])
        faltante = valor_necessario - valor_acumulado

        if prazo_ts < hoje_ts:
            diagnostics.append(
                Diagnostic(
                    codigo=f"meta_atrasada_{row['id']}",
                    titulo=f"Meta atrasada: {row['nome']}",
                    severidade=DiagnosticSeverity.ALTA,
                    descricao=(
                        f"O prazo de '{row['nome']}' ({prazo_ts.date()}) já passou e a meta "
                        f"está em {progresso_pct:.0f}% ({_brl(valor_acumulado)} de {_brl(valor_necessario)})."
                    ),
                    explicacao=(
                        "Uma meta com prazo vencido perde a função de guiar decisões — ou o "
                        "prazo ou o ritmo de aporte precisam mudar."
                    ),
                    recomendacao="Revise o prazo para algo realista ou aumente o aporte mensal para essa meta.",
                    impacto_financeiro=faltante,
                )
            )
            continue

        dias_restantes = (prazo_ts - hoje_ts).days
        if dias_restantes <= META_RISCO_DIAS_RESTANTES and progresso_pct < META_RISCO_PROGRESSO_PCT:
            diagnostics.append(
                Diagnostic(
                    codigo=f"meta_em_risco_{row['id']}",
                    titulo=f"Meta em risco: {row['nome']}",
                    severidade=DiagnosticSeverity.MEDIA,
                    descricao=(
                        f"Faltam {dias_restantes} dia(s) para '{row['nome']}' e o progresso "
                        f"está em {progresso_pct:.0f}% ({_brl(valor_acumulado)} de {_brl(valor_necessario)})."
                    ),
                    explicacao=(
                        "Com o prazo se aproximando e menos da metade do valor guardado, "
                        "alcançar a meta a tempo vai exigir aportes bem maiores que os atuais."
                    ),
                    recomendacao="Reforce os aportes para essa meta ou reavalie o prazo.",
                    impacto_financeiro=faltante,
                )
            )
    return diagnostics


# ---------------------------------------------------------------------
# Regras "narrativas": comparam períodos/dimensões entre si em vez de só
# checar um número contra um limiar fixo — mais próximas do tipo de
# leitura que um analista financeiro faria ("cresceu X% em Y meses",
# "rendeu abaixo do CDI", "gasta mais no fim de semana").
# ---------------------------------------------------------------------
INVESTIMENTO_ABAIXO_BENCHMARK_LIMIAR_PP = 0.5  # pontos percentuais de diferença mínimos pra valer o alerta
TENDENCIA_CATEGORIA_MESES_JANELA = 3
TENDENCIA_CATEGORIA_CRESCIMENTO_PCT = 25.0
TENDENCIA_CATEGORIA_MAX_DIAGNOSTICOS = 3  # nao inundar a tela: só as categorias que mais cresceram em R$
FIM_DE_SEMANA_DIFERENCA_PCT = 30.0
FIM_DE_SEMANA_MIN_DIAS = 4  # precisa de uma amostra mínima de dias de cada tipo pra a média significar algo


def check_investimento_abaixo_benchmark(latest_assets: pd.DataFrame) -> list[Diagnostic]:
    """
    latest_assets: AssetRepository.get_latest_positions(). Compara a
    rentabilidade de 12 meses do ativo com a do próprio benchmark
    (guardados lado a lado desde a extração do PDF) — ex: "seu patrimônio
    cresceu abaixo do CDI". Ativos sem benchmark numérico (extratos mais
    antigos, ou tipos de ativo sem benchmark) são ignorados, não quebram.
    """
    if latest_assets.empty:
        return []
    diagnostics: list[Diagnostic] = []
    for _, row in latest_assets.iterrows():
        rent = row.get("rentabilidade_12m_pct")
        bench = row.get("benchmark_12m_pct")
        bench_nome = row.get("benchmark")
        if rent is None or bench is None or pd.isna(rent) or pd.isna(bench):
            continue
        diferenca_pp = rent - bench
        if diferenca_pp >= -INVESTIMENTO_ABAIXO_BENCHMARK_LIMIAR_PP:
            continue  # rendeu igual ou acima do benchmark (dentro da margem) -> nada a dizer
        diagnostics.append(
            Diagnostic(
                codigo=f"investimento_abaixo_benchmark_{row['identificador']}",
                titulo=f"{row['nome']} rendeu abaixo do {bench_nome}",
                severidade=DiagnosticSeverity.MEDIA if diferenca_pp >= -2 else DiagnosticSeverity.ALTA,
                descricao=(
                    f"Nos últimos 12 meses, '{row['nome']}' rendeu {rent:.2f}%, contra "
                    f"{bench:.2f}% do {bench_nome} — {abs(diferenca_pp):.2f} pontos percentuais abaixo."
                ),
                explicacao=(
                    "Um investimento que perde do seu próprio benchmark de referência por um "
                    "período prolongado pode não estar justificando o risco/custo em relação a "
                    "uma alternativa mais simples atrelada ao benchmark."
                ),
                recomendacao=(
                    f"Avalie se vale continuar neste ativo ou migrar para algo com histórico "
                    f"mais consistente acima do {bench_nome}."
                ),
                impacto_financeiro=None,
            )
        )
    return diagnostics


def check_tendencia_categoria(category_trend_df: pd.DataFrame) -> list[Diagnostic]:
    """
    category_trend_df: indicator_service.category_trend() (histórico
    completo, colunas month/category/value_abs). Compara a média mensal
    de cada categoria na janela mais recente contra a janela anterior —
    ex: "gastos com Lazer cresceram 37% nos últimos 3 meses". Precisa de
    pelo menos 2 janelas completas de histórico (6 meses pra janela=3);
    com menos que isso, não há base de comparação confiável, então não
    diagnostica nada (silêncio é melhor que um falso alarme com 1-2 meses de dado).
    """
    if category_trend_df.empty:
        return []
    n = TENDENCIA_CATEGORIA_MESES_JANELA
    meses = sorted(category_trend_df["month"].unique())
    if len(meses) < n * 2:
        return []

    recentes = set(meses[-n:])
    anteriores = set(meses[-2 * n:-n])

    diagnostics: list[Diagnostic] = []
    for categoria in category_trend_df["category"].unique():
        cat_df = category_trend_df[category_trend_df["category"] == categoria]
        media_recente = cat_df[cat_df["month"].isin(recentes)]["value_abs"].sum() / n
        media_anterior = cat_df[cat_df["month"].isin(anteriores)]["value_abs"].sum() / n
        if media_anterior <= 0:
            continue
        crescimento_pct = (media_recente - media_anterior) / media_anterior * 100
        if crescimento_pct < TENDENCIA_CATEGORIA_CRESCIMENTO_PCT:
            continue
        diagnostics.append(
            Diagnostic(
                codigo=f"categoria_crescendo_{categoria}",
                titulo=f"Gasto crescente em {categoria}",
                severidade=DiagnosticSeverity.MEDIA,
                descricao=(
                    f"Nos últimos {n} meses, '{categoria}' custou em média {_brl(media_recente)}/mês, "
                    f"{crescimento_pct:.0f}% acima da média dos {n} meses anteriores "
                    f"({_brl(media_anterior)}/mês)."
                ),
                explicacao=(
                    "Uma categoria crescendo de forma sustentada — mesmo que a renda não "
                    "acompanhe — corrói a taxa de poupança aos poucos, de um jeito fácil de não "
                    "perceber mês a mês."
                ),
                recomendacao=(
                    f"Veja o que mudou em '{categoria}' nesse período (aba Dashboard, filtrando "
                    f"por mês) — um hábito novo recorrente é mais fácil de ajustar quando "
                    f"identificado cedo."
                ),
                impacto_financeiro=(media_recente - media_anterior) * n,
            )
        )
    diagnostics.sort(key=lambda d: d.impacto_financeiro or 0, reverse=True)
    return diagnostics[:TENDENCIA_CATEGORIA_MAX_DIAGNOSTICOS]


def check_gasto_fim_de_semana(weekend_stats: dict) -> list[Diagnostic]:
    """
    weekend_stats: indicator_service.weekend_vs_weekday_spending() —
    {media_fim_de_semana, media_dia_util, dias_fim_de_semana, dias_uteis}.
    Compara o gasto médio POR DIA (não a soma) entre fim de semana e dia
    útil, sobre todo o histórico disponível — é um padrão de
    comportamento, não algo específico de um mês.
    """
    dias_fds = weekend_stats.get("dias_fim_de_semana", 0)
    dias_uteis = weekend_stats.get("dias_uteis", 0)
    if dias_fds < FIM_DE_SEMANA_MIN_DIAS or dias_uteis < FIM_DE_SEMANA_MIN_DIAS:
        return []  # amostra pequena demais pra a média significar algo

    media_fds = weekend_stats["media_fim_de_semana"]
    media_uteis = weekend_stats["media_dia_util"]
    if media_uteis <= 0:
        return []

    diferenca_pct = (media_fds - media_uteis) / media_uteis * 100
    if diferenca_pct < FIM_DE_SEMANA_DIFERENCA_PCT:
        return []

    return [
        Diagnostic(
            codigo="gasto_fim_de_semana_elevado",
            titulo="Gasto de fim de semana bem acima do normal",
            severidade=DiagnosticSeverity.BAIXA,
            descricao=(
                f"Seu gasto médio por dia de fim de semana ({_brl(media_fds)}) é "
                f"{diferenca_pct:.0f}% maior que em dias úteis ({_brl(media_uteis)}), "
                f"considerando todo o histórico importado."
            ),
            explicacao=(
                "Um padrão consistente de gasto elevado no fim de semana costuma vir de "
                "lazer, delivery ou saídas — não é necessariamente ruim, mas vale confirmar "
                "se é um padrão consciente ou só hábito."
            ),
            recomendacao=(
                "Veja as categorias 'Lazer' e 'Alimentação' no Dashboard nos dias de fim de "
                "semana pra confirmar a origem."
            ),
            impacto_financeiro=(media_fds - media_uteis) * dias_fds,
        )
    ]


CUSTO_DINHEIRO_PARADO_MIN_DIAS = 15  # amostra mínima de dias de saldo pra confiar na média
CUSTO_DINHEIRO_PARADO_LIMIAR_RS = 30.0  # abaixo disso não vale a pena nem mencionar


def check_custo_dinheiro_parado(
    saldo_medio_conta_corrente: float, dias: int, taxa_anual_referencia: float | None, benchmark_nome: str | None,
) -> list[Diagnostic]:
    """
    Estima quanto o saldo médio mantido em conta corrente deixou de render
    se tivesse ficado investido a uma taxa de referência (o benchmark do
    seu próprio investimento, ex: CDI) — responde diretamente "quanto
    estou perdendo por manter dinheiro parado". `taxa_anual_referencia`
    vem de AssetPosition.benchmark_12m_pct; sem nenhum investimento
    importado ainda, não há taxa de referência e a regra fica em silêncio
    em vez de inventar um número.
    """
    if dias < CUSTO_DINHEIRO_PARADO_MIN_DIAS or saldo_medio_conta_corrente <= 0:
        return []
    if taxa_anual_referencia is None or taxa_anual_referencia <= 0:
        return []

    custo_oportunidade = saldo_medio_conta_corrente * (taxa_anual_referencia / 100) * (dias / 365)
    if custo_oportunidade < CUSTO_DINHEIRO_PARADO_LIMIAR_RS:
        return []

    bench = benchmark_nome or "seu benchmark de referência"
    return [
        Diagnostic(
            codigo="custo_dinheiro_parado",
            titulo="Dinheiro parado na conta corrente",
            severidade=DiagnosticSeverity.BAIXA,
            descricao=(
                f"Nos últimos {dias} dias com saldo registrado, você manteve em média "
                f"{_brl(saldo_medio_conta_corrente)} na conta corrente. Rendendo à taxa do "
                f"{bench} ({taxa_anual_referencia:.2f}% a.a.), esse valor teria gerado "
                f"aproximadamente {_brl(custo_oportunidade)} a mais no período."
            ),
            explicacao=(
                "Parte do saldo em conta corrente naturalmente serve para cobrir despesas do "
                "dia a dia — isso não é 'desperdício' automaticamente. Mas o que fica MANTIDO "
                "acima do necessário pra isso deixa de render, e esse custo é silencioso "
                "porque nunca aparece como uma despesa."
            ),
            recomendacao=(
                "Considere manter na conta corrente só o equivalente a 1-2 meses de despesas "
                "e investir o excedente."
            ),
            impacto_financeiro=custo_oportunidade,
        )
    ]


def run_diagnostics(
    monthly: pd.DataFrame,
    latest_summary: dict,
    latest_period_label: str,
    latest_by_cat: pd.DataFrame,
    all_tx: pd.DataFrame,
    patrimonio_total: float = 0.0,
    despesa_media_mensal: float = 0.0,
    budget_limits: dict | None = None,
    goals: pd.DataFrame | None = None,
    hoje: str | None = None,
    latest_assets: pd.DataFrame | None = None,
    category_trend_df: pd.DataFrame | None = None,
    weekend_stats: dict | None = None,
    balance_stats: dict | None = None,
) -> list[Diagnostic]:
    """
    Roda todas as regras cadastradas e devolve a lista ordenada por
    prioridade (mais grave primeiro). Adicionar uma regra nova = escrever
    a função check_* e somar ela aqui — nada mais precisa mudar.
    """
    diagnostics: list[Diagnostic] = []
    diagnostics += check_saldo_negativo_recorrente(monthly)
    diagnostics += check_taxa_poupanca_baixa(latest_summary, latest_period_label)
    diagnostics += check_concentracao_categoria(latest_by_cat, latest_period_label)
    diagnostics += check_transacoes_pendentes(all_tx)
    diagnostics += check_reserva_emergencia(patrimonio_total, despesa_media_mensal)
    if budget_limits:
        diagnostics += check_orcamento_estourado(latest_by_cat, budget_limits, latest_period_label)
    if goals is not None and not goals.empty:
        diagnostics += check_metas(goals, hoje=hoje)
    if latest_assets is not None and not latest_assets.empty:
        diagnostics += check_investimento_abaixo_benchmark(latest_assets)
    if category_trend_df is not None and not category_trend_df.empty:
        diagnostics += check_tendencia_categoria(category_trend_df)
    if weekend_stats is not None:
        diagnostics += check_gasto_fim_de_semana(weekend_stats)
    if balance_stats is not None and latest_assets is not None and not latest_assets.empty:
        primeiro_ativo = latest_assets.iloc[0]
        diagnostics += check_custo_dinheiro_parado(
            saldo_medio_conta_corrente=balance_stats.get("saldo_medio", 0.0),
            dias=balance_stats.get("dias", 0),
            taxa_anual_referencia=primeiro_ativo.get("benchmark_12m_pct"),
            benchmark_nome=primeiro_ativo.get("benchmark"),
        )
    return sorted(diagnostics, key=lambda d: d.prioridade)
