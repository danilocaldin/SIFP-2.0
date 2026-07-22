"""
sifp/services/chat_service.py
-------------------------------
Fase 6 (IA): perguntas livres sobre as finanças ("quanto gastei com Uber
esse ano?"), via chat. Diferente de narrativa_service.py (que só manda
números já agregados), aqui o Claude decide, por conta própria, quais
consultas fazer nos dados reais — usando tool use (function calling) em
vez de receber tudo pronto de antemão. Isso é o que permite responder
perguntas abertas, que não dá pra prever de antemão.

Modelo: Claude Haiku (mesma escolha de custo do narrativa_service — ver
docstring lá). As tools nunca devolvem a base inteira de uma vez (sempre
com um teto de linhas de exemplo), pra manter o custo e o volume de dado
pessoal exposto por chamada sob controle.

A conversa é stateless do lado do servidor: quem mantém o histórico é o
cliente (Streamlit/frontend), que reenvia todas as mensagens a cada
pergunta nova — mesmo padrão do resto da API, sem sessão/login.
"""

from __future__ import annotations

import json
import os

import pandas as pd

from sifp.domain.categories import CATEGORIAS_PADRAO
from sifp.services import indicator_service as ind
from sifp.services.formatting import formatar_mes

MODEL = "claude-haiku-4-5"

MAX_TRANSACOES_EXEMPLO = 15

_SYSTEM_PROMPT_BASE = (
    "Você é um assistente financeiro pessoal, respondendo em português do "
    "Brasil. Você tem ferramentas para consultar os dados financeiros REAIS "
    "do usuário (transações, resumos de período, patrimônio) — use-as "
    "sempre que a pergunta depender de um número real. Nunca invente ou "
    "estime um valor que você não obteve de uma ferramenta. Se a pergunta "
    "for ambígua sobre período (ex: 'esse ano'), assuma o ano mais recente "
    "disponível nos dados, mas deixe claro qual período você usou. Se não "
    "encontrar dados suficientes para responder, diga isso claramente em "
    "vez de chutar. Para perguntas sobre o maior gasto ou a maior receita "
    "de um período, use sempre os campos 'maior_despesa'/'maior_receita' "
    "de buscar_transacoes — nunca tente descobrir isso examinando a lista "
    "de exemplos, que é limitada e ordenada por data, não por valor. "
    "Responda de forma direta e curta (poucas frases), em "
    "texto simples — sem markdown, sem negrito, sem itálico, sem listas "
    "com marcadores. Não dê conselho de investimento nem recomendação de "
    "compra/venda de ativos — só informe os números."
)


class ChatIndisponivel(Exception):
    """Recurso desligado (sem ANTHROPIC_API_KEY configurada)."""


class ChatService:
    def __init__(self, transaction_repo, asset_repo):
        self.transaction_repo = transaction_repo
        self.asset_repo = asset_repo

    def _dados_base(self) -> pd.DataFrame | None:
        all_tx = self.transaction_repo.get_all()
        if all_tx.empty:
            return None
        all_tx["date"] = pd.to_datetime(all_tx["date"])
        all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)
        return all_tx

    def _montar_system_prompt(self, all_tx: pd.DataFrame) -> str:
        meses = sorted(all_tx["month"].unique())
        intervalo = f"{formatar_mes(meses[0])} até {formatar_mes(meses[-1])}" if meses else "nenhum"
        return (
            f"{_SYSTEM_PROMPT_BASE}\n\n"
            f"Período coberto pelos dados disponíveis: {intervalo}. "
            f"Categorias válidas: {', '.join(CATEGORIAS_PADRAO)}."
        )

    def _montar_tools(self, all_tx_full: pd.DataFrame):
        from anthropic import beta_tool

        all_tx = ind.exclude_self_transfers(all_tx_full)

        def _json(payload) -> str:
            # O Tool Runner exige que o retorno de uma tool seja string
            # (ou lista de content blocks) — nunca um dict/list Python cru.
            return json.dumps(payload, ensure_ascii=False)

        def _filtrar_periodo(df: pd.DataFrame, mes_inicio: str, mes_fim: str) -> pd.DataFrame:
            if mes_inicio:
                df = df[df["month"] >= mes_inicio]
            if mes_fim:
                df = df[df["month"] <= mes_fim]
            return df

        @beta_tool
        def listar_categorias() -> str:
            """Lista as categorias válidas de transação neste sistema.

            Use antes de filtrar por categoria, para não inventar um nome
            de categoria que não existe.
            """
            return _json(CATEGORIAS_PADRAO)

        @beta_tool
        def buscar_transacoes(
            descricao_contem: str = "",
            categoria: str = "",
            mes_inicio: str = "",
            mes_fim: str = "",
        ) -> str:
            """Busca transações financeiras reais, com filtros opcionais.

            Devolve totais e a maior despesa/receita já calculados sobre
            TODAS as transações que casam com o filtro (não só a amostra)
            -- use "maior_despesa"/"maior_receita" para perguntas do tipo
            "qual foi meu maior gasto", nunca tente inferir isso a partir
            de "transacoes_exemplo_mais_recentes", que é só uma amostra
            limitada ordenada por data, não por valor.

            Args:
                descricao_contem: texto que deve aparecer na descrição da
                    transação (ex: "uber"), sem diferenciar maiúsculas/minúsculas.
                    Deixe vazio para não filtrar por texto.
                categoria: nome exato de uma categoria válida (ver
                    listar_categorias). Deixe vazio para não filtrar.
                mes_inicio: mês inicial no formato "YYYY-MM". Deixe vazio
                    para não limitar o início do período.
                mes_fim: mês final no formato "YYYY-MM" (inclusive). Deixe
                    vazio para não limitar o fim do período.
            """
            df = _filtrar_periodo(all_tx, mes_inicio, mes_fim)
            if descricao_contem:
                df = df[df["description"].str.contains(descricao_contem, case=False, na=False)]
            if categoria:
                df = df[df["category"] == categoria]

            if df.empty:
                return _json({
                    "quantidade": 0, "total_despesas": 0.0, "total_receitas": 0.0,
                    "maior_despesa": None, "maior_receita": None, "transacoes_exemplo_mais_recentes": [],
                })

            def _linha(row) -> dict:
                return {
                    "data": row["date"].strftime("%Y-%m-%d"),
                    "descricao": row["description"],
                    "categoria": row["category"],
                    "valor": float(row["value"]),
                }

            despesas_df = df[df["value"] < 0]
            receitas_df = df[df["value"] > 0]
            despesas = despesas_df["value"].abs().sum()
            receitas = receitas_df["value"].sum()
            # Calculado sobre TODO o conjunto filtrado (não a amostra
            # abaixo) -- se a amostra fosse a única fonte, perguntas como
            # "qual foi meu maior gasto" ficariam sujeitas a um recorte
            # (as N mais recentes) que pode não conter o maior valor real.
            maior_despesa = _linha(despesas_df.loc[despesas_df["value"].idxmin()]) if not despesas_df.empty else None
            maior_receita = _linha(receitas_df.loc[receitas_df["value"].idxmax()]) if not receitas_df.empty else None
            exemplo = df.sort_values("date", ascending=False).head(MAX_TRANSACOES_EXEMPLO)
            return _json({
                "quantidade": int(len(df)),
                "total_despesas": float(despesas),
                "total_receitas": float(receitas),
                "maior_despesa": maior_despesa,
                "maior_receita": maior_receita,
                "transacoes_exemplo_mais_recentes": [_linha(row) for _, row in exemplo.iterrows()],
            })

        @beta_tool
        def resumo_periodo(mes_inicio: str = "", mes_fim: str = "") -> str:
            """Resumo financeiro (receitas, despesas, saldo, taxa de
            poupança e gasto por categoria) de um período.

            Args:
                mes_inicio: mês inicial no formato "YYYY-MM". Deixe vazio
                    para começar do início dos dados disponíveis.
                mes_fim: mês final no formato "YYYY-MM" (inclusive). Deixe
                    vazio para ir até o mês mais recente disponível.
            """
            df = _filtrar_periodo(all_tx, mes_inicio, mes_fim)
            if df.empty:
                return _json({"has_data": False})
            summary = ind.period_summary(df)
            by_cat = ind.category_breakdown(df)
            return _json({
                "has_data": True,
                "receitas": float(summary["receitas"]),
                "despesas": float(summary["despesas"]),
                "saldo": float(summary["saldo"]),
                "taxa_poupanca_pct": float(summary["taxa_poupanca"]),
                "por_categoria": [
                    {"categoria": r["category"], "total": float(r["value_abs"]), "pct": float(r["pct"])}
                    for _, r in by_cat.iterrows()
                ],
            })

        @beta_tool
        def patrimonio_atual() -> str:
            """Patrimônio total atual e a posição de cada ativo de investimento."""
            assets = self.asset_repo.get_latest_positions()
            if assets.empty:
                return _json({"has_data": False})
            return _json({
                "has_data": True,
                "patrimonio_total": float(assets["saldo_liquido"].sum()),
                "ativos": [
                    {
                        "nome": r["nome"],
                        "tipo": r["tipo"],
                        "saldo": float(r["saldo_liquido"]),
                        "rentabilidade_12m_pct": (
                            float(r["rentabilidade_12m_pct"]) if pd.notna(r["rentabilidade_12m_pct"]) else None
                        ),
                    }
                    for _, r in assets.iterrows()
                ],
            })

        return [listar_categorias, buscar_transacoes, resumo_periodo, patrimonio_atual]

    def responder(self, mensagens: list[dict]) -> str:
        all_tx = self._dados_base()
        if all_tx is None:
            raise ChatIndisponivel("Ainda não há dados suficientes para responder perguntas.")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ChatIndisponivel("ANTHROPIC_API_KEY não configurada.")

        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=1024,
            system=self._montar_system_prompt(all_tx),
            tools=self._montar_tools(all_tx),
            messages=mensagens,
        )

        last = None
        for message in runner:
            last = message

        if last is None:
            raise ChatIndisponivel("O modelo não retornou nenhuma resposta.")

        return "".join(block.text for block in last.content if block.type == "text").strip()
