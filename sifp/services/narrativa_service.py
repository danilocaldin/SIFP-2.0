"""
sifp/services/narrativa_service.py
-----------------------------------
Fase 6 (IA): explica as oscilações financeiras do mês em linguagem natural,
sob demanda (botão na tela Resumo, não em toda carga de página), usando a
API da Anthropic. Modelo: Claude Haiku (mais barato/rápido da família —
escolhido porque essa é uma explicação de texto curto, não uma tarefa de
raciocínio complexo, e o uso pode ser frequente).

Só números já agregados (os mesmos que a tela Resumo mostra) vão pro
prompt — nenhuma transação individual ou descrição bruta é enviada à
Anthropic, o que minimiza custo e a superfície de dados pessoais
compartilhada com terceiros.

Sem ANTHROPIC_API_KEY configurada, o recurso fica indisponível
(NarrativaIndisponivel) mas o resto do sistema funciona normalmente — é
uma funcionalidade opcional, não uma dependência dura.
"""

from __future__ import annotations

import os

import pandas as pd

from sifp.services import indicator_service as ind
from sifp.services.formatting import formatar_mes
from sifp.services.summary_service import SummaryService

MODEL = "claude-haiku-4-5"

_SYSTEM_PROMPT = (
    "Você explica finanças pessoais em português do Brasil, em linguagem "
    "simples, para uma pessoa sem formação financeira. Responda em no "
    "máximo 3-4 frases curtas, sem jargão técnico, sem markdown, sem "
    "saudação — vá direto ao ponto. Explique POR QUE o saldo e os gastos "
    "se comportaram assim no mês, usando só os números fornecidos. Nunca "
    "invente número que não esteja nos dados. Não dê conselho de "
    "investimento nem recomendação de compra/venda de ativos."
)


class NarrativaIndisponivel(Exception):
    """Recurso desligado (sem API key configurada) ou sem dados suficientes."""


class NarrativaService:
    def __init__(self, summary_service: SummaryService, transaction_repo):
        self.summary_service = summary_service
        self.transaction_repo = transaction_repo

    def _montar_contexto(self) -> dict | None:
        resumo = self.summary_service.build_resumo(formatar_mes)
        if not resumo.get("has_data"):
            return None

        all_tx = self.transaction_repo.get_all()
        all_tx["date"] = pd.to_datetime(all_tx["date"])
        all_tx["month"] = all_tx["date"].dt.to_period("M").astype(str)
        all_tx_real = ind.exclude_self_transfers(all_tx)
        monthly = ind.monthly_evolution(all_tx_real)

        latest_month = resumo["mes"]
        period_df = all_tx_real[all_tx_real["month"] == latest_month]
        by_cat = ind.category_breakdown(period_df).head(5)

        return {
            "resumo": resumo,
            "monthly_recent": monthly.tail(4).to_dict("records"),
            "top_categorias": by_cat.to_dict("records"),
        }

    def _montar_prompt(self, ctx: dict) -> str:
        resumo = ctx["resumo"]
        linhas = [
            f"Mês analisado: {resumo['mes_label']}",
            f"Saldo do mês: R$ {resumo['saldo']:.2f}",
            f"Taxa de poupança do mês: {resumo['taxa_poupanca_pct']:.1f}%",
        ]
        if resumo["delta_saldo_pct"] is not None:
            linhas.append(f"Variação do saldo em relação ao mês anterior: {resumo['delta_saldo_pct']:.1f}%")
        if resumo["patrimonio_total"]:
            linhas.append(f"Patrimônio total atual: R$ {resumo['patrimonio_total']:.2f}")
        if resumo["taxa_mes_pct"] is not None:
            linhas.append(f"Rentabilidade dos investimentos no mês: {resumo['taxa_mes_pct']:.2f}%")

        if ctx["monthly_recent"]:
            linhas.append("\nÚltimos meses (receitas / despesas / saldo):")
            for m in ctx["monthly_recent"]:
                linhas.append(
                    f"- {formatar_mes(m['month'])}: R$ {m['Receitas']:.2f} / R$ {m['Despesas']:.2f} / R$ {m['Saldo']:.2f}"
                )

        if ctx["top_categorias"]:
            linhas.append("\nMaiores categorias de gasto no mês:")
            for c in ctx["top_categorias"]:
                linhas.append(f"- {c['category']}: R$ {c['value_abs']:.2f} ({c['pct']:.1f}% do total)")

        diagnosticos = resumo.get("diagnostics") or []
        if diagnosticos:
            linhas.append("\nAlertas automáticos detectados (mais prioritário primeiro):")
            for d in diagnosticos[:3]:
                linhas.append(f"- {d['titulo']}: {d['descricao']}")

        return "\n".join(linhas)

    def explicar_mes(self) -> str:
        ctx = self._montar_contexto()
        if ctx is None:
            raise NarrativaIndisponivel("Ainda não há dados suficientes para gerar uma explicação.")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise NarrativaIndisponivel("ANTHROPIC_API_KEY não configurada.")

        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": self._montar_prompt(ctx)}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()
