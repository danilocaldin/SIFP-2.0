"""
app.py
------
Sistema de Inteligência Financeira Pessoal (SIFP)
Camada de apresentação (Streamlit) — fina de propósito: só chama os
services/repositories de sifp/ e renderiza. Nenhuma regra de negócio
mora aqui (parsing, categorização, indicadores e persistência vivem em
sifp/importers, sifp/intelligence, sifp/services, sifp/repositories).

Rodar com:
    streamlit run app.py
"""

from dotenv import load_dotenv

load_dotenv()

import pandas as pd
import plotly.express as px
import streamlit as st

from sifp.domain.categories import CATEGORIAS_PADRAO, CATEGORIA_NAO_CATEGORIZADO, SELF_TRANSFER_CATEGORY
from sifp.importers.btg_importer import BTGImporter
from sifp.importers.btg_investment_importer import BTGInvestmentImporter
from sifp.domain.models import DiagnosticSeverity
from sifp.intelligence import diagnostics as diag
from sifp.intelligence.categorization import CategorizationService, is_pix_or_transfer
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.goal_repository import GoalRepository
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services import indicator_service as ind
from sifp.services import projection_service as proj
from sifp.services.formatting import format_brl, format_brl_md, formatar_mes
from sifp.services.chat_service import ChatIndisponivel, ChatService
from sifp.services.import_service import ImportService
from sifp.services.narrativa_service import NarrativaIndisponivel, NarrativaService
from sifp.services.pdf_report_service import generate_pdf_report
from sifp.services.report_service import generate_text_report
from sifp.services.summary_service import SummaryService

st.set_page_config(
    page_title="Sifra — Inteligência Financeira Pessoal",
    page_icon="💰",
    layout="wide",
)

init_db()

transaction_repo = TransactionRepository()
balance_repo = BalanceRepository()
asset_repo = AssetRepository()
budget_repo = BudgetRepository()
goal_repo = GoalRepository()
investment_importer = BTGInvestmentImporter()
summary_service = SummaryService(transaction_repo, balance_repo, asset_repo, budget_repo, goal_repo)
narrativa_service = NarrativaService(summary_service, transaction_repo)
chat_service = ChatService(transaction_repo, asset_repo)

# ---------------------------------------------------------------------
# Estado da sessão
# ---------------------------------------------------------------------
if "categorization" not in st.session_state:
    st.session_state.categorization = CategorizationService.load()
if "last_import_msg" not in st.session_state:
    st.session_state.last_import_msg = None

import_service = ImportService(
    importers=[BTGImporter()],
    categorization=st.session_state.categorization,
    transaction_repo=transaction_repo,
    balance_repo=balance_repo,
)


def refresh_model() -> str:
    training_df = transaction_repo.get_training_data()
    return st.session_state.categorization.train(training_df)


# ---------------------------------------------------------------------
# Constantes e helpers compartilhados entre abas
# ---------------------------------------------------------------------
# Paleta fixa: verde = receita/positivo, vermelho = despesa/negativo,
# azul = neutro (saldo, evolução, magnitude por categoria). Usada em todos
# os gráficos para que a mesma cor sempre signifique a mesma coisa.
COLOR_RECEITA = "#0ca30c"
COLOR_DESPESA = "#d03b3b"
COLOR_SALDO = "#2a78d6"
BLUE_SEQUENTIAL = ["#cde2fb", "#6da7ec", "#2a78d6", "#0d366b"]

SEVERITY_ICON = {
    DiagnosticSeverity.CRITICA: "🔴",
    DiagnosticSeverity.ALTA: "🟠",
    DiagnosticSeverity.MEDIA: "🟡",
    DiagnosticSeverity.BAIXA: "🔵",
}
SEVERITY_RENDER = {
    DiagnosticSeverity.CRITICA: st.error,
    DiagnosticSeverity.ALTA: st.warning,
    DiagnosticSeverity.MEDIA: st.warning,
    DiagnosticSeverity.BAIXA: st.info,
}


_formatar_mes = formatar_mes


def _delta_str(pct: float | None) -> str | None:
    return None if pct is None else f"{pct:+.0f}% vs mês anterior"


st.title("💰 Sifra")
st.caption("Inteligência financeira pessoal • Upload de extratos • Categorização automática (regras + Machine Learning) • Dashboard")

(
    tab_resumo, tab_upload, tab_revisao, tab_dashboard, tab_patrimonio,
    tab_orcamento, tab_projecoes, tab_diagnosticos, tab_relatorio, tab_chat,
) = st.tabs([
    "🏠 Resumo", "📤 Upload", "✏️ Revisão de Categorias", "📊 Dashboard", "💼 Patrimônio",
    "🎯 Orçamento e Metas", "🔮 Projeções", "🩺 Diagnósticos", "📄 Relatório", "💬 Chat",
])

# =======================================================================
# TAB 0 - RESUMO
# =======================================================================
with tab_resumo:
    st.subheader("Como você está agora")

    resumo = summary_service.build_resumo(_formatar_mes)

    if not resumo["has_data"]:
        st.info("Ainda não há dados importados. Comece pela aba **Upload**.")
    else:
        saldo_home, taxa_home = resumo["saldo"], resumo["taxa_poupanca_pct"]
        patrimonio_total_home, latest_label_home = resumo["patrimonio_total"], resumo["mes_label"]

        # ---- Frase-headline: interpreta antes de mostrar números soltos ----
        frases = []
        if patrimonio_total_home > 0:
            frases.append(f"Seu patrimônio é **{format_brl_md(patrimonio_total_home)}**.")
            if resumo["taxa_mes_pct"] is not None:
                if resumo["benchmark_mes_pct"] is not None:
                    comparacao = "acima" if resumo["taxa_mes_pct"] >= resumo["benchmark_mes_pct"] else "abaixo"
                    frases.append(
                        f"Seus investimentos renderam **{resumo['taxa_mes_pct']:.2f}%** em {latest_label_home} "
                        f"— **{comparacao}** de {resumo['benchmark_nome']} ({resumo['benchmark_mes_pct']:.2f}%)."
                    )
                else:
                    frases.append(
                        f"Seus investimentos renderam **{resumo['taxa_mes_pct']:.2f}%** em {latest_label_home}."
                    )
        if saldo_home >= 0:
            frases.append(
                f"Em **{latest_label_home}**, você guardou **{taxa_home:.0f}%** da renda "
                f"({format_brl_md(saldo_home)})."
            )
        else:
            frases.append(
                f"Em **{latest_label_home}**, você fechou **{format_brl_md(abs(saldo_home))} no vermelho**."
            )
        st.markdown(" ".join(frases))

        col1, col2, col3 = st.columns(3)
        col1.metric("Patrimônio total", format_brl(patrimonio_total_home))
        col2.metric(
            f"Saldo em {latest_label_home}", format_brl(saldo_home),
            delta=_delta_str(resumo["delta_saldo_pct"]),
        )
        col3.metric("Taxa de poupança", f"{taxa_home:.0f}%")

        st.divider()
        st.markdown("**O que mais importa agora**")

        diagnostics_home = resumo["diagnostics"]
        if not diagnostics_home:
            st.success(
                "✅ Nada pedindo atenção agora — suas finanças estão dentro dos "
                "parâmetros que o sistema verifica hoje."
            )
        else:
            top = diagnostics_home[0]  # run_diagnostics já devolve ordenado por prioridade
            severidade_top = DiagnosticSeverity(top["severidade"])
            render_fn = SEVERITY_RENDER[severidade_top]
            icon = SEVERITY_ICON[severidade_top]
            impacto = (
                f"\n\n**Impacto:** {format_brl_md(abs(top['impacto_financeiro']))}"
                if top["impacto_financeiro"] is not None else ""
            )
            render_fn(
                f"{icon} **{top['titulo']}**\n\n{top['descricao']}\n\n"
                f"*Recomendação:* {top['recomendacao']}{impacto}"
            )
            restantes = len(diagnostics_home) - 1
            if restantes > 0:
                st.caption(f"+ {restantes} outro(s) ponto(s) de atenção na aba 🩺 Diagnósticos.")

        if resumo["saldo_medio_3m"] > 0 and resumo["projecao_12m"] is not None:
            st.caption(
                f"📈 No ritmo atual, seu patrimônio deve chegar perto de "
                f"**{format_brl_md(resumo['projecao_12m'])}** em 12 meses. Veja a aba 🔮 Projeções para mais detalhes."
            )
        else:
            st.caption(
                "📉 Nos últimos 3 meses seu saldo médio foi negativo — no ritmo atual, seu "
                "patrimônio não cresce. Veja a aba 🔮 Projeções."
            )

        st.divider()
        if st.button("🤖 Explicar este mês em linguagem natural"):
            with st.spinner("Gerando explicação..."):
                try:
                    st.session_state.narrativa_texto = narrativa_service.explicar_mes()
                    st.session_state.narrativa_erro = None
                except NarrativaIndisponivel as e:
                    st.session_state.narrativa_texto = None
                    st.session_state.narrativa_erro = str(e)
                except Exception:
                    st.session_state.narrativa_texto = None
                    st.session_state.narrativa_erro = "Falha ao gerar a explicação. Tente novamente em instantes."

        if st.session_state.get("narrativa_texto"):
            st.info(st.session_state.narrativa_texto)
        elif st.session_state.get("narrativa_erro"):
            st.warning(st.session_state.narrativa_erro)

# =======================================================================
# TAB 1 - UPLOAD
# =======================================================================
with tab_upload:
    st.subheader("Importar extrato do BTG Pactual")
    uploaded_file = st.file_uploader(
        "Selecione o arquivo (CSV, XLS ou XLSX)", type=["csv", "xls", "xlsx"]
    )

    if uploaded_file is not None:
        try:
            df_parsed, df_balances = import_service.parse(uploaded_file)
            st.success(f"Arquivo lido com sucesso: {len(df_parsed)} transações encontradas.")
            st.dataframe(df_parsed.head(10), use_container_width=True)

            if st.button("Processar e Categorizar", type="primary"):
                summary = import_service.persist(df_parsed, df_balances, source_file=uploaded_file.name)
                st.session_state.last_import_msg = (
                    f"✅ {summary['inseridas']} transações novas importadas. "
                    f"{summary['ignoradas_duplicadas']} já existiam no banco e foram ignoradas (sem duplicidade)."
                )
                st.rerun()

        except ValueError as e:
            st.error(str(e))

    if st.session_state.last_import_msg:
        st.info(st.session_state.last_import_msg)
        st.session_state.last_import_msg = None

    st.divider()
    with st.expander("ℹ️ Formatos suportados"):
        st.markdown(
            """
            **CSV** — o parser identifica automaticamente as colunas de:
            - **Data** (`Data`, `Data Lançamento`, ...)
            - **Descrição** (`Descrição`, `Histórico`, `Lançamento`, ...)
            - **Valor** (`Valor`, formatos como `1.234,56` ou `-45,00`)

            **XLS / XLSX** — o extrato de conta corrente baixado pelo internet
            banking do BTG (com bloco de Cliente/CPF/Agência/Conta no topo,
            que se repete a cada página). O parser localiza a tabela de
            lançamentos automaticamente, ignora linhas de "Saldo Diário",
            detecta transferências para você mesmo (ex: para uma conta
            investimento) e aproveita a coluna **Categoria** que o próprio
            BTG já preenche como uma pista extra para a categorização
            automática.

            Em ambos os formatos, datas no padrão brasileiro (`dd/mm/aaaa`)
            e valores com vírgula decimal são convertidos automaticamente.
            Despesas devem vir como valores negativos e receitas como
            positivos (padrão dos extratos bancários brasileiros).
            """
        )

# =======================================================================
# TAB 2 - REVISÃO (Human-in-the-loop)
# =======================================================================
with tab_revisao:
    st.subheader("Revise e corrija as categorias sugeridas")
    st.caption(
        "O que você salvar aqui vira memória permanente por descrição: uma descrição que "
        "você **sempre** classifica igual (ex: um mercado, um app de transporte) passa a ser "
        "categorizada sozinha nas próximas importações. Uma descrição que **já variou** "
        "entre categorias diferentes (ex: um Pix para a mesma pessoa que às vezes é uma coisa, "
        "às vezes é outra) o sistema deixa sempre marcada como 'Não categorizado', porque sabe "
        "que precisa da sua decisão a cada vez."
    )

    all_tx = transaction_repo.get_all()

    if all_tx.empty:
        st.warning("Nenhuma transação importada ainda. Vá para a aba **Upload**.")
    else:
        # ---- Categorização em lote para estabelecimentos ----
        # Pix/Transferência ficam de fora de propósito: a mesma pessoa pode
        # significar coisas diferentes a cada Pix, então essas continuam
        # sendo revisadas uma a uma no editor abaixo. Já uma compra num
        # estabelecimento (ex: "Marceloaloisio") tende a ser sempre a mesma
        # categoria, e nesse caso vale aplicar de uma vez a todas as
        # ocorrências pendentes em vez de clicar linha por linha.
        pending = all_tx[all_tx["category"] == CATEGORIA_NAO_CATEGORIZADO]
        is_pix_or_transfer_mask = pending["description"].apply(is_pix_or_transfer)
        establishment_pending = pending[~is_pix_or_transfer_mask]

        if not establishment_pending.empty:
            st.markdown("#### 🏪 Categorizar estabelecimentos pendentes em lote")
            st.caption(
                "Cada linha agrupa todas as transações pendentes com a mesma descrição. "
                "Escolha a categoria e clique em Aplicar — resolve todas de uma vez."
            )
            grouped = (
                establishment_pending.groupby("description")
                .size()
                .reset_index(name="n")
                .sort_values("n", ascending=False)
            )
            for _, grp in grouped.iterrows():
                desc, n = grp["description"], grp["n"]
                col_desc, col_cat, col_btn = st.columns([3, 2, 1])
                col_desc.write(f"**{desc}** ({n}x)")
                chosen_cat = col_cat.selectbox(
                    "Categoria", CATEGORIAS_PADRAO, key=f"bulk_cat_{desc}",
                    label_visibility="collapsed",
                )
                if col_btn.button("Aplicar", key=f"bulk_apply_{desc}"):
                    hashes = all_tx.loc[all_tx["description"] == desc, "tx_hash"].tolist()
                    transaction_repo.bulk_update_categories([(h, chosen_cat) for h in hashes])
                    msg = refresh_model()
                    st.success(f"{len(hashes)} transação(ões) de '{desc}' -> {chosen_cat}. {msg}")
                    st.rerun()
            st.divider()

        learned_map = transaction_repo.get_learned_categories()

        def _situacao(row):
            entry = learned_map.get(row["description"])
            if entry and entry["variable"]:
                hist = ", ".join(f"{c} ({n}x)" for c, n in entry["history"])
                return f"🔁 Variável — já foi: {hist}"
            if bool(row.get("self_transfer")) and row["category"] == SELF_TRANSFER_CATEGORY:
                return "↔️ Transferência interna (detectada automaticamente)"
            if row["confidence"] >= 0.95:
                return "✅ Alta confiança"
            if row["confidence"] >= 0.6:
                return "🔎 Conferir"
            return "🆕 Novo / revisar"

        all_tx["situacao"] = all_tx.apply(_situacao, axis=1)

        col1, col2, col3 = st.columns(3)
        with col1:
            only_pending = st.checkbox("Mostrar apenas 'Não categorizado'", value=False)
        with col2:
            low_confidence = st.checkbox("Mostrar apenas baixa confiança (<0.6)", value=False)
        with col3:
            st.metric("Total de transações", len(all_tx))

        df_view = all_tx.copy()
        if only_pending:
            df_view = df_view[df_view["category"] == CATEGORIA_NAO_CATEGORIZADO]
        if low_confidence:
            df_view = df_view[df_view["confidence"] < 0.6]

        st.caption(
            "Altere a categoria diretamente na coluna 'Categoria'. Clique em **Salvar** para "
            "confirmar as linhas visíveis com categoria escolhida (mesmo as que você não mudou — "
            "revisar e manter também é uma confirmação) e re-treinar o modelo. Linhas que continuarem "
            "como 'Não categorizado' **não** são marcadas como confirmadas — seguem pendentes e vão "
            "aparecer de novo aqui até você de fato escolher uma categoria."
        )

        df_view["value"] = df_view["value"].apply(format_brl)

        edited_df = st.data_editor(
            df_view[
                ["tx_hash", "date", "description", "value", "bank_category",
                 "situacao", "category", "confidence"]
            ],
            column_config={
                "tx_hash": None,  # coluna técnica, oculta
                "date": st.column_config.TextColumn("Data", disabled=True),
                "description": st.column_config.TextColumn("Descrição", disabled=True, width="large"),
                "value": st.column_config.TextColumn("Valor (R$)", disabled=True),
                "bank_category": st.column_config.TextColumn(
                    "Categoria BTG", disabled=True, help="Categoria sugerida pelo próprio banco (referência)."
                ),
                "situacao": st.column_config.TextColumn(
                    "Situação", disabled=True, width="medium",
                    help="Por que o sistema sugeriu (ou não sugeriu) essa categoria.",
                ),
                "category": st.column_config.SelectboxColumn(
                    "Categoria", options=CATEGORIAS_PADRAO, required=True
                ),
                "confidence": st.column_config.ProgressColumn(
                    "Confiança da IA", min_value=0.0, max_value=1.0, format="%.0f%%"
                ),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key="editor",
        )

        if st.button("💾 Salvar e confirmar linhas visíveis", type="primary"):
            old_categories = df_view["category"].values
            new_categories = edited_df["category"].values
            n_changed = int((old_categories != new_categories).sum())
            n_still_pending = int((new_categories == CATEGORIA_NAO_CATEGORIZADO).sum())
            n_confirmed = len(new_categories) - n_still_pending

            updates = list(zip(df_view["tx_hash"], new_categories))
            transaction_repo.bulk_update_categories(updates)
            msg = refresh_model()

            st.session_state.last_import_msg = None
            pending_note = (
                f" {n_still_pending} continuam pendentes (ainda 'Não categorizado', vão reaparecer aqui)."
                if n_still_pending else ""
            )
            st.success(
                f"{n_confirmed} transação(ões) confirmada(s) ({n_changed} corrigida(s) agora). "
                f"Essas descrições já entram na memória do sistema.{pending_note} {msg}"
            )
            st.rerun()

        st.divider()
        if st.button("🔁 Re-treinar modelo manualmente"):
            msg = refresh_model()
            st.info(msg)

# =======================================================================
# TAB 3 - DASHBOARD
# =======================================================================
with tab_dashboard:
    st.subheader("Visão geral das finanças")

    all_tx = transaction_repo.get_all()
    all_balances = balance_repo.get_all()

    if all_tx.empty:
        st.warning("Nenhuma transação importada ainda.")
    else:
        all_tx["date"] = pd.to_datetime(all_tx["date"])
        all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)

        months_sorted = sorted(all_tx["month"].unique())
        selected_month = st.selectbox(
            "Filtrar por mês", options=["Todos"] + list(reversed(months_sorted))
        )

        all_tx_real = ind.exclude_self_transfers(all_tx)

        df_period = all_tx if selected_month == "Todos" else all_tx[all_tx["month"] == selected_month]
        df_period_real = (
            all_tx_real if selected_month == "Todos" else all_tx_real[all_tx_real["month"] == selected_month]
        )

        summary = ind.period_summary(df_period_real)
        receitas, despesas, saldo, taxa_poupanca = (
            summary["receitas"], summary["despesas"], summary["saldo"], summary["taxa_poupanca"]
        )
        self_transfer_periodo = ind.self_transfer_total(df_period)

        # Comparação com o mês anterior (só faz sentido com um mês específico selecionado)
        prev_summary = None
        if selected_month != "Todos":
            idx = months_sorted.index(selected_month)
            if idx > 0:
                df_prev = all_tx_real[all_tx_real["month"] == months_sorted[idx - 1]]
                prev_summary = ind.period_summary(df_prev)
        delta = ind.month_over_month_delta(summary, prev_summary)

        # ---- Resumo em linguagem simples ----
        # "\$" (não "$"): st.markdown trata pares de "$" como delimitador de
        # fórmula LaTeX, e com "R$" aparecendo 2-3x na mesma frase o texto
        # entre o 1º e o 2º "$" vira uma tentativa de fórmula, quebrando tanto
        # o cifrão quanto o negrito ao redor. Escapar evita isso.
        periodo_label = _formatar_mes(selected_month) if selected_month != "Todos" else "todo o período importado"
        if saldo >= 0:
            st.markdown(
                f"Em **{periodo_label}**, você recebeu **{format_brl_md(receitas)}**, gastou "
                f"**{format_brl_md(despesas)}** e guardou **{format_brl_md(saldo)}** "
                f"— uma taxa de poupança de **{taxa_poupanca:.0f}%** da sua renda."
            )
        else:
            st.markdown(
                f"Em **{periodo_label}**, você recebeu **{format_brl_md(receitas)}** mas gastou "
                f"**{format_brl_md(despesas)}** — ficou **{format_brl_md(abs(saldo))} no vermelho**."
            )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Receitas", format_brl(receitas), delta=_delta_str(delta["receitas"]))
        col2.metric(
            "Despesas", format_brl(despesas),
            delta=_delta_str(delta["despesas"]), delta_color="inverse",
        )
        col3.metric("Saldo", format_brl(saldo), delta=_delta_str(delta["saldo"]))
        col4.metric("Taxa de poupança", f"{taxa_poupanca:.0f}%")

        if self_transfer_periodo > 0:
            st.caption(
                f"↔️ {format_brl_md(self_transfer_periodo)} foram movimentados entre suas próprias "
                f"contas neste período (ex: indo para investimentos e voltando) — **não contam** "
                f"como receita nem despesa acima."
            )

        st.divider()

        # ---- Evolução do saldo no período (dado exclusivo do extrato XLS do BTG) ----
        st.markdown("**Evolução do saldo**")
        bal_period = pd.DataFrame()
        if not all_balances.empty:
            bal_period = all_balances.copy()
            bal_period["month"] = bal_period["date"].dt.to_period("M").astype(str)
            if selected_month != "Todos":
                bal_period = bal_period[bal_period["month"] == selected_month]

        if not bal_period.empty:
            fig_saldo = px.line(bal_period, x="date", y="balance", markers=True)
            fig_saldo.update_traces(line_color=COLOR_SALDO, marker_color=COLOR_SALDO)
            fig_saldo.update_layout(
                yaxis_title="Saldo (R$)", xaxis_title="",
                hovermode="x unified", showlegend=False,
            )
            st.plotly_chart(fig_saldo, use_container_width=True)
        else:
            st.caption(
                "Sem dados de saldo diário para este período. Essa evolução só está "
                "disponível em extratos importados no formato XLS/XLSX do BTG."
            )

        st.divider()

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**Gastos por categoria**")
            by_cat = ind.category_breakdown(df_period_real)

            if not by_cat.empty:
                by_cat["label"] = by_cat.apply(
                    lambda r: f"{format_brl(r['value_abs'])} ({r['pct']:.0f}%)", axis=1
                )
                fig_cat = px.bar(
                    by_cat, x="value_abs", y="category", orientation="h",
                    color="value_abs", color_continuous_scale=BLUE_SEQUENTIAL,
                    text="label",
                )
                fig_cat.update_layout(
                    showlegend=False, coloraxis_showscale=False,
                    xaxis_title="R$ gasto", yaxis_title="",
                    yaxis={"categoryorder": "total ascending"},
                )
                fig_cat.update_traces(textposition="outside", cliponaxis=False)
                st.plotly_chart(fig_cat, use_container_width=True)
            else:
                st.info("Sem despesas no período selecionado.")

        with col_b:
            st.markdown("**Receita, despesa e saldo por mês**")
            monthly = ind.monthly_evolution(all_tx_real)
            monthly["mes_label"] = monthly["month"].apply(_formatar_mes)
            monthly_long = monthly.melt(
                id_vars="mes_label", value_vars=["Receitas", "Despesas", "Saldo"],
                var_name="tipo", value_name="valor",
            )
            fig_month = px.bar(
                monthly_long, x="mes_label", y="valor", color="tipo", barmode="group",
                color_discrete_map={
                    "Receitas": COLOR_RECEITA, "Despesas": COLOR_DESPESA, "Saldo": COLOR_SALDO
                },
                labels={"mes_label": "", "valor": "R$", "tipo": ""},
            )
            fig_month.update_layout(legend_title_text="")
            st.plotly_chart(fig_month, use_container_width=True)

        st.divider()

        col_c, col_d = st.columns(2)

        with col_c:
            st.markdown("**Maiores gastos individuais do período**")
            top_gastos = ind.top_expenses(df_period_real, n=10)
            if not top_gastos.empty:
                top_gastos = top_gastos.copy()
                top_gastos["value_abs"] = top_gastos["value_abs"].apply(format_brl)
                st.dataframe(
                    top_gastos[["date", "description", "category", "value_abs"]],
                    column_config={
                        "date": st.column_config.TextColumn("Data"),
                        "description": st.column_config.TextColumn("Descrição", width="large"),
                        "category": st.column_config.TextColumn("Categoria"),
                        "value_abs": st.column_config.TextColumn("Valor (R$)"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("Sem despesas no período selecionado.")

        with col_d:
            st.markdown("**Onde o dinheiro foi (por estabelecimento)**")
            by_merchant = ind.merchant_concentration(df_period_real, n=10)
            if not by_merchant.empty:
                by_merchant = by_merchant.copy()
                by_merchant["value_abs"] = by_merchant["value_abs"].apply(format_brl)
                st.dataframe(
                    by_merchant,
                    column_config={
                        "merchant": st.column_config.TextColumn("Estabelecimento"),
                        "value_abs": st.column_config.TextColumn("Valor (R$)"),
                        "n_transacoes": st.column_config.NumberColumn("Nº de compras"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info(
                    "Sem dados de estabelecimento no período (só disponível para "
                    "transações importadas depois da Fase 1 da arquitetura)."
                )

        with st.expander("Ver todas as transações do período"):
            st.dataframe(
                df_period[["date", "description", "value", "bank_category", "merchant", "category"]]
                .sort_values("date", ascending=False),
                use_container_width=True,
            )

# =======================================================================
# TAB 4 - PATRIMÔNIO (Módulo 6, Fase 2)
# =======================================================================
with tab_patrimonio:
    st.subheader("Patrimônio — Ativos")
    st.caption(
        "Ainda não há dívidas/passivos cadastrados, então por enquanto o patrimônio "
        "líquido é a soma dos seus ativos."
    )

    uploaded_pdf = st.file_uploader(
        "Importar extrato da conta investimento (PDF)", type=["pdf"], key="asset_upload"
    )
    if uploaded_pdf is not None:
        try:
            positions = investment_importer.read(uploaded_pdf)
            n = asset_repo.insert_many(positions)
            st.success(
                f"✅ {n} posição(ões) importada(s)/atualizada(s). Reimportar o mesmo "
                f"extrato atualiza o snapshot da data em vez de duplicar."
            )
        except ValueError as e:
            st.error(str(e))

    st.divider()

    latest_assets = asset_repo.get_latest_positions()
    if latest_assets.empty:
        st.info("Nenhum ativo importado ainda. Envie um extrato de conta investimento em PDF acima.")
    else:
        latest_assets = latest_assets.copy()
        latest_assets["data_referencia"] = latest_assets["data_referencia"].dt.strftime("%Y-%m-%d")

        patrimonio_total = latest_assets["saldo_liquido"].sum()
        st.metric("Patrimônio total (Ativos)", format_brl(patrimonio_total))

        latest_assets["saldo_liquido"] = latest_assets["saldo_liquido"].apply(format_brl)
        st.dataframe(
            latest_assets[
                ["nome", "tipo", "instituicao", "data_referencia", "saldo_liquido",
                 "rentabilidade_12m_pct", "benchmark", "benchmark_12m_pct"]
            ],
            column_config={
                "nome": st.column_config.TextColumn("Ativo"),
                "tipo": st.column_config.TextColumn("Tipo"),
                "instituicao": st.column_config.TextColumn("Instituição"),
                "data_referencia": st.column_config.TextColumn("Data ref."),
                "saldo_liquido": st.column_config.TextColumn("Saldo líquido (R$)"),
                "rentabilidade_12m_pct": st.column_config.NumberColumn("Rent. 12m (%)", format="%.2f%%"),
                "benchmark": st.column_config.TextColumn("Benchmark"),
                "benchmark_12m_pct": st.column_config.NumberColumn("Benchmark 12m (%)", format="%.2f%%"),
            },
            hide_index=True,
            use_container_width=True,
        )

        st.divider()
        st.markdown("**Evolução do patrimônio**")
        all_asset_snapshots = asset_repo.get_all()
        net_worth = ind.net_worth_history(all_asset_snapshots)
        if len(net_worth) >= 2:
            fig_networth = px.line(net_worth, x="data_referencia", y="patrimonio_total", markers=True)
            fig_networth.update_traces(line_color=COLOR_SALDO, marker_color=COLOR_SALDO)
            fig_networth.update_layout(
                yaxis_title="Patrimônio (R$)", xaxis_title="", hovermode="x unified", showlegend=False,
            )
            st.plotly_chart(fig_networth, use_container_width=True)
        else:
            st.caption(
                "Só há um snapshot importado até agora — envie extratos de meses "
                "diferentes pra ver a evolução ao longo do tempo."
            )

        with st.expander("Ver histórico completo (todos os snapshots importados)"):
            all_asset_snapshots_display = all_asset_snapshots.copy()
            all_asset_snapshots_display["data_referencia"] = all_asset_snapshots_display["data_referencia"].dt.strftime("%Y-%m-%d")
            st.dataframe(all_asset_snapshots_display, use_container_width=True)

# =======================================================================
# TAB 5 - ORÇAMENTO E METAS (Módulos 13 e 14, Fase 3)
# =======================================================================
with tab_orcamento:
    st.subheader("Orçamento e Metas")
    st.caption(
        "Defina limites de gasto por categoria e metas financeiras — os alertas da aba "
        "Diagnósticos e o Relatório passam a considerá-los automaticamente assim que você "
        "cadastrar algum."
    )

    col_orc, col_metas = st.columns(2)

    # ---- Orçamento: limite por categoria ----
    with col_orc:
        st.markdown("#### 🎯 Limite por categoria")

        # Calculado uma vez e reaproveitado tanto pra sugerir o limite quanto
        # pra comparar o gasto do mês atual contra o limite salvo, mais abaixo.
        all_tx_orc = transaction_repo.get_all()
        all_tx_orc_real = pd.DataFrame()
        if not all_tx_orc.empty:
            all_tx_orc["date"] = pd.to_datetime(all_tx_orc["date"])
            all_tx_orc["month"] = all_tx_orc["date"].dt.to_period("M").astype(str)
            all_tx_orc_real = ind.exclude_self_transfers(all_tx_orc)

        media_gasto_map = {}
        if not all_tx_orc_real.empty:
            media_by_cat = ind.average_spend_by_category(all_tx_orc_real, janela=3)
            media_gasto_map = dict(zip(media_by_cat["category"], media_by_cat["media_mensal"]))

        categoria_limite = st.selectbox(
            "Categoria", [c for c in CATEGORIAS_PADRAO if c != CATEGORIA_NAO_CATEGORIZADO],
            key="categoria_limite_select",
        )
        media_sugerida = media_gasto_map.get(categoria_limite)
        if media_sugerida:
            st.caption(
                f"💡 Você gastou em média {format_brl_md(media_sugerida)}/mês nessa categoria nos "
                f"últimos meses — usamos como ponto de partida abaixo, ajuste se quiser."
            )

        with st.form("novo_limite_orcamento"):
            valor_limite = st.number_input(
                "Limite mensal (R$)", min_value=0.0,
                value=round(float(media_sugerida), 2) if media_sugerida else 0.0,
                step=50.0, format="%.2f",
                key=f"valor_limite_input_{categoria_limite}",
            )
            if st.form_submit_button("Salvar limite", type="primary"):
                if valor_limite > 0:
                    budget_repo.set_limit(categoria_limite, valor_limite)
                    st.success(f"Limite de {categoria_limite} definido: {format_brl_md(valor_limite)}/mês.")
                    st.rerun()
                else:
                    st.warning("Informe um valor maior que zero.")

        limits_df = budget_repo.get_all()
        if limits_df.empty:
            st.caption("Nenhum limite definido ainda.")
        else:
            # gasto do mes mais recente, pra comparar contra o limite
            gasto_atual = {}
            if not all_tx_orc_real.empty:
                latest_month_orc = all_tx_orc_real["month"].max()
                latest_df_orc = all_tx_orc_real[all_tx_orc_real["month"] == latest_month_orc]
                by_cat_orc = ind.category_breakdown(latest_df_orc)
                gasto_atual = dict(zip(by_cat_orc["category"], by_cat_orc["value_abs"]))

            for _, row in limits_df.iterrows():
                gasto = gasto_atual.get(row["category"], 0.0)
                limite = row["limite_mensal"]
                pct = min(gasto / limite, 1.0) if limite > 0 else 0.0
                st.write(f"**{row['category']}** — {format_brl_md(gasto)} / {format_brl_md(limite)}")
                st.progress(pct)
                if st.button(f"Remover limite de {row['category']}", key=f"rm_budget_{row['category']}"):
                    budget_repo.remove_limit(row["category"])
                    st.rerun()

    # ---- Metas financeiras ----
    with col_metas:
        st.markdown("#### 🏁 Metas financeiras")

        with st.form("nova_meta"):
            nome_meta = st.text_input("Nome da meta (ex: Reserva de emergência)")
            valor_necessario_meta = st.number_input("Valor necessário (R$)", min_value=0.0, step=100.0, format="%.2f")
            prazo_meta = st.date_input("Prazo")
            if st.form_submit_button("Criar meta", type="primary"):
                if nome_meta and valor_necessario_meta > 0:
                    goal_repo.create(nome_meta, valor_necessario_meta, prazo_meta.strftime("%Y-%m-%d"))
                    st.success(f"Meta '{nome_meta}' criada.")
                    st.rerun()
                else:
                    st.warning("Preencha o nome e um valor maior que zero.")

        goals_df = goal_repo.get_all()
        if goals_df.empty:
            st.caption("Nenhuma meta cadastrada ainda.")
        else:
            for _, row in goals_df.iterrows():
                progresso_pct = min(row["valor_acumulado"] / row["valor_necessario"] * 100, 100.0) if row["valor_necessario"] > 0 else 0.0
                st.write(
                    f"**{row['nome']}** — {format_brl_md(row['valor_acumulado'])} / "
                    f"{format_brl_md(row['valor_necessario'])} ({progresso_pct:.0f}%) — prazo {row['prazo']}"
                )
                st.progress(min(progresso_pct / 100, 1.0))
                col_novo_valor, col_salvar, col_excluir = st.columns([2, 1, 1])
                novo_valor = col_novo_valor.number_input(
                    "Atualizar valor acumulado", min_value=0.0, value=float(row["valor_acumulado"]),
                    step=50.0, format="%.2f", key=f"goal_value_{row['id']}", label_visibility="collapsed",
                )
                if col_salvar.button("Salvar", key=f"goal_save_{row['id']}"):
                    goal_repo.update_progress(int(row["id"]), novo_valor)
                    st.rerun()
                if col_excluir.button("Excluir", key=f"goal_del_{row['id']}"):
                    goal_repo.delete(int(row["id"]))
                    st.rerun()
                st.divider()

# =======================================================================
# TAB 6 - PROJEÇÕES (Fase 5)
# =======================================================================
with tab_projecoes:
    st.subheader("Projeções")
    st.caption(
        "Se o seu ritmo de poupança dos últimos meses continuar, é para onde sua vida "
        "financeira está indo. Não é uma previsão do futuro — é o que aconteceria se "
        "nada mudasse."
    )

    all_tx_proj = transaction_repo.get_all()

    if all_tx_proj.empty:
        st.warning("Nenhuma transação importada ainda.")
    else:
        all_tx_proj["date"] = pd.to_datetime(all_tx_proj["date"])
        all_tx_proj["month"] = all_tx_proj["date"].dt.to_period("M").astype(str)
        all_tx_proj_real = ind.exclude_self_transfers(all_tx_proj)
        monthly_proj = ind.monthly_evolution(all_tx_proj_real)

        saldo_medio = proj.average_monthly_saldo(monthly_proj, janela=3)

        latest_assets_proj = asset_repo.get_latest_positions()
        patrimonio_atual_proj = (
            float(latest_assets_proj["saldo_liquido"].sum()) if not latest_assets_proj.empty else 0.0
        )
        taxa_rentabilidade_proj = proj.weighted_avg_rentabilidade(latest_assets_proj)

        horizonte = st.radio(
            "Horizonte", [6, 12, 24], index=1, horizontal=True, format_func=lambda m: f"{m} meses"
        )

        if saldo_medio <= 0:
            st.warning(
                f"Nos últimos meses seu saldo médio foi **{format_brl_md(saldo_medio)}/mês** — no "
                f"ritmo atual, seu patrimônio não cresce. Ajustar isso é o primeiro passo antes "
                f"de projetar crescimento (veja a aba Dashboard para identificar onde cortar)."
            )
        else:
            if taxa_rentabilidade_proj is not None:
                projecao = proj.project_patrimonio_com_rendimento(
                    patrimonio_atual_proj, saldo_medio, taxa_rentabilidade_proj, meses=horizonte
                )
                rendimento_nota = (
                    f", considerando também que seus investimentos atuais rendem em média "
                    f"**{taxa_rentabilidade_proj:.2f}% a.a.**"
                )
            else:
                projecao = proj.project_patrimonio(patrimonio_atual_proj, saldo_medio, meses=horizonte)
                rendimento_nota = ""
            patrimonio_final = projecao.iloc[-1]["patrimonio_projetado"]
            st.markdown(
                f"No ritmo médio dos últimos 3 meses (**{format_brl_md(saldo_medio)}/mês** guardados){rendimento_nota}, "
                f"seu patrimônio deve ir de **{format_brl_md(patrimonio_atual_proj)}** para "
                f"**{format_brl_md(patrimonio_final)}** em {horizonte} meses."
            )

            hist_networth = ind.net_worth_history(asset_repo.get_all())
            if not hist_networth.empty:
                hist_display = hist_networth.rename(columns={"data_referencia": "data"}).copy()
                hist_display["data"] = pd.to_datetime(hist_display["data"])
                hist_display["tipo"] = "Histórico"

                last_date = hist_display["data"].iloc[-1]
                proj_rows = [{"data": last_date, "patrimonio_total": patrimonio_atual_proj, "tipo": "Projeção"}]
                for _, r in projecao.iterrows():
                    proj_rows.append({
                        "data": last_date + pd.DateOffset(months=int(r["mes_offset"])),
                        "patrimonio_total": r["patrimonio_projetado"],
                        "tipo": "Projeção",
                    })
                combined = pd.concat(
                    [hist_display[["data", "patrimonio_total", "tipo"]], pd.DataFrame(proj_rows)],
                    ignore_index=True,
                )

                fig_proj = px.line(
                    combined, x="data", y="patrimonio_total", color="tipo", markers=True,
                    line_dash="tipo",
                    color_discrete_map={"Histórico": COLOR_SALDO, "Projeção": "#9b59b6"},
                    line_dash_map={"Histórico": "solid", "Projeção": "dash"},
                    labels={"data": "", "patrimonio_total": "Patrimônio (R$)", "tipo": ""},
                )
                fig_proj.update_layout(hovermode="x unified")
                st.plotly_chart(fig_proj, use_container_width=True)
            else:
                st.caption(
                    "Sem histórico de patrimônio suficiente pra desenhar o gráfico — importe "
                    "extratos de investimento em meses diferentes na aba Patrimônio."
                )

        st.divider()
        st.markdown("**Suas metas nesse ritmo**")

        goals_proj = goal_repo.get_all()
        if goals_proj.empty:
            st.caption("Nenhuma meta cadastrada — defina uma na aba Orçamento e Metas.")
        else:
            for _, row in goals_proj.iterrows():
                eta = proj.project_goal_eta_months(row["valor_necessario"], row["valor_acumulado"], saldo_medio)
                prazo = pd.to_datetime(row["prazo"])
                if eta == 0:
                    st.success(f"✅ **{row['nome']}** já está concluída.")
                elif eta is None:
                    faltante = row["valor_necessario"] - row["valor_acumulado"]
                    st.error(
                        f"🔴 **{row['nome']}** — no ritmo atual de poupança, essa meta não é "
                        f"atingida (faltam {format_brl_md(faltante)} e o saldo médio recente é zero ou "
                        f"negativo)."
                    )
                else:
                    data_prevista = pd.Timestamp.today() + pd.DateOffset(months=eta)
                    dentro_do_prazo = data_prevista <= prazo
                    render_fn = st.info if dentro_do_prazo else st.warning
                    icon = "🔵" if dentro_do_prazo else "🟠"
                    relacao_prazo = "antes do" if dentro_do_prazo else "depois do"
                    render_fn(
                        f"{icon} **{row['nome']}** — no ritmo atual, atingida em ~{eta} mês(es) "
                        f"(por volta de {data_prevista.strftime('%m/%Y')}), {relacao_prazo} prazo "
                        f"definido ({prazo.strftime('%m/%Y')})."
                    )

# =======================================================================
# TAB 7 - DIAGNÓSTICOS
# =======================================================================
with tab_diagnosticos:
    st.subheader("Diagnósticos automáticos")
    st.caption(
        "Leituras automáticas sobre suas finanças — não é só o número, é uma explicação do "
        "porquê ele importa e uma recomendação do que fazer a respeito."
    )

    all_tx_diag = transaction_repo.get_all()

    if all_tx_diag.empty:
        st.warning("Nenhuma transação importada ainda.")
    else:
        all_tx_diag["date"] = pd.to_datetime(all_tx_diag["date"])
        all_tx_diag["month"] = all_tx_diag["date"].dt.to_period("M").astype(str)
        all_tx_diag_real = ind.exclude_self_transfers(all_tx_diag)

        monthly_diag = ind.monthly_evolution(all_tx_diag_real)
        latest_month = monthly_diag.iloc[-1]["month"]
        latest_month_label = _formatar_mes(latest_month)

        diagnostics = summary_service.diagnostics_for_month(all_tx_diag, all_tx_diag_real, latest_month, latest_month_label)

        if not diagnostics:
            st.success(
                "✅ Nenhum diagnóstico no momento — suas finanças estão dentro dos "
                "parâmetros que o sistema verifica hoje."
            )
        else:
            n_total = len(diagnostics)
            n_critica = sum(1 for d in diagnostics if d.severidade == DiagnosticSeverity.CRITICA)
            n_alta = sum(1 for d in diagnostics if d.severidade == DiagnosticSeverity.ALTA)
            plural = "s" if n_total != 1 else ""
            if n_critica:
                st.error(
                    f"🔴 {n_total} ponto{plural} de atenção agora — {n_critica} crítico(s), "
                    f"comece por eles."
                )
            elif n_alta:
                st.warning(f"🟠 {n_total} ponto{plural} de atenção agora — nada crítico, mas vale olhar.")
            else:
                st.info(f"🔵 {n_total} ponto{plural} de atenção agora — nada urgente.")

            for d in diagnostics:
                render_fn = SEVERITY_RENDER[d.severidade]
                icon = SEVERITY_ICON[d.severidade]
                impacto = (
                    f"\n\n**Impacto:** {format_brl_md(abs(d.impacto_financeiro))}"
                    if d.impacto_financeiro is not None else ""
                )
                render_fn(
                    f"{icon} **{d.titulo}**\n\n"
                    f"{d.descricao}\n\n"
                    f"*Por quê isso importa:* {d.explicacao}\n\n"
                    f"*Recomendação:* {d.recomendacao}"
                    f"{impacto}"
                )

# =======================================================================
# TAB 8 - RELATÓRIO
# =======================================================================
with tab_relatorio:
    st.subheader("Relatório financeiro")
    st.caption(
        "Consolida em um único texto o que as outras abas já mostram — resumo, categorias, "
        "estabelecimentos, diagnósticos, patrimônio e dívidas — pronto pra copiar, salvar ou "
        "compartilhar."
    )

    all_tx_rel = transaction_repo.get_all()

    if all_tx_rel.empty:
        st.warning("Nenhuma transação importada ainda.")
    else:
        all_tx_rel["date"] = pd.to_datetime(all_tx_rel["date"])
        all_tx_rel["month"] = all_tx_rel["date"].dt.to_period("M").astype(str)
        all_tx_rel_real = ind.exclude_self_transfers(all_tx_rel)

        months_rel = sorted(all_tx_rel["month"].unique())
        selected_month_rel = st.selectbox(
            "Mês do relatório", options=list(reversed(months_rel)), key="report_month"
        )
        period_label_rel = _formatar_mes(selected_month_rel)

        period_df_rel = all_tx_rel[all_tx_rel["month"] == selected_month_rel]
        period_df_rel_real = all_tx_rel_real[all_tx_rel_real["month"] == selected_month_rel]

        summary_rel = ind.period_summary(period_df_rel_real)
        by_cat_rel = ind.category_breakdown(period_df_rel_real)
        by_merchant_rel = ind.merchant_concentration(period_df_rel_real)
        monthly_rel = ind.monthly_evolution(all_tx_rel_real)
        latest_assets_rel = asset_repo.get_latest_positions()

        diagnostics_rel = summary_service.diagnostics_for_month(all_tx_rel, all_tx_rel_real, selected_month_rel, period_label_rel)

        debt_transactions_rel = period_df_rel[period_df_rel["category"] == "Dívida"]

        report_text = generate_text_report(
            period_label=period_label_rel,
            summary=summary_rel,
            by_cat=by_cat_rel,
            by_merchant=by_merchant_rel,
            monthly=monthly_rel,
            diagnostics=diagnostics_rel,
            asset_positions=latest_assets_rel,
            debt_transactions=debt_transactions_rel,
        )

        st.text_area("Relatório", report_text, height=500, label_visibility="collapsed")

        col_txt, col_pdf = st.columns(2)
        with col_txt:
            st.download_button(
                "⬇️ Baixar relatório (.txt)",
                data=report_text,
                file_name=f"relatorio_sifp_{selected_month_rel}.txt",
                mime="text/plain",
            )
        with col_pdf:
            patrimonio_total_rel = float(latest_assets_rel["saldo_liquido"].sum()) if not latest_assets_rel.empty else 0.0
            pdf_bytes_rel = generate_pdf_report(
                period_label=period_label_rel,
                summary=summary_rel,
                by_cat=by_cat_rel,
                monthly=monthly_rel,
                diagnostics=diagnostics_rel,
                patrimonio_total=patrimonio_total_rel,
            )
            st.download_button(
                "⬇️ Baixar relatório (PDF)",
                data=pdf_bytes_rel,
                file_name=f"relatorio_sifra_{selected_month_rel}.pdf",
                mime="application/pdf",
            )

# =======================================================================
# TAB 9 - CHAT
# =======================================================================
with tab_chat:
    st.subheader("Pergunte sobre suas finanças")
    st.caption("As respostas vêm sempre dos seus dados reais, nunca de estimativas.")

    if "chat_mensagens" not in st.session_state:
        st.session_state.chat_mensagens = []

    for msg in st.session_state.chat_mensagens:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    pergunta = st.chat_input("Pergunte algo sobre suas finanças...")
    if pergunta:
        st.session_state.chat_mensagens.append({"role": "user", "content": pergunta})
        with st.chat_message("user"):
            st.markdown(pergunta)
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                try:
                    resposta = chat_service.responder(st.session_state.chat_mensagens)
                except ChatIndisponivel as e:
                    resposta = f"⚠️ {e}"
                except Exception:
                    resposta = "⚠️ Falha ao gerar a resposta. Tente novamente em instantes."
            st.markdown(resposta)
        st.session_state.chat_mensagens.append({"role": "assistant", "content": resposta})
