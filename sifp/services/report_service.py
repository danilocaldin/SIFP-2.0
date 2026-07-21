"""
services/report_service.py
------------------------------
Módulo 11 — Relatórios. Primeira versão: texto plano (a spec original
pede texto primeiro, PDF/Excel/HTML depois). Nenhuma lógica nova aqui —
é só consolidação e formatação do que os outros services já calculam
(IndicatorService, diagnostics, AssetRepository), então o relatório não
pode nunca ficar "diferente" do que as outras abas mostram: é a mesma
fonte de dados, só reorganizada num documento único.
"""

import pandas as pd

from sifp.domain.models import Diagnostic
from sifp.services.formatting import unescape_currency as _plain

_SEP = "-" * 60


def _section(title: str) -> list[str]:
    return ["", title.upper(), _SEP]


def generate_text_report(
    period_label: str,
    summary: dict,
    by_cat: pd.DataFrame,
    by_merchant: pd.DataFrame,
    monthly: pd.DataFrame,
    diagnostics: list[Diagnostic],
    asset_positions: pd.DataFrame,
    debt_transactions: pd.DataFrame,
) -> str:
    """
    Monta o relatório em texto para um período.

    summary: indicator_service.period_summary()
    by_cat: indicator_service.category_breakdown()
    by_merchant: indicator_service.merchant_concentration()
    monthly: indicator_service.monthly_evolution() (histórico completo, não só o período)
    diagnostics: diagnostics.run_diagnostics()
    asset_positions: AssetRepository.get_latest_positions()
    debt_transactions: transações do período com category == "Dívida"
    """
    lines: list[str] = []
    lines.append(f"RELATÓRIO FINANCEIRO — {period_label}")
    lines.append("=" * 60)

    lines += _section("Resumo financeiro")
    lines.append(f"Receitas............... R$ {summary['receitas']:>14,.2f}")
    lines.append(f"Despesas............... R$ {summary['despesas']:>14,.2f}")
    lines.append(f"Saldo.................. R$ {summary['saldo']:>14,.2f}")
    lines.append(f"Taxa de poupança....... {summary['taxa_poupanca']:>17.1f}%")

    lines += _section("Gastos por categoria")
    if by_cat.empty:
        lines.append("(sem despesas no período)")
    else:
        for _, row in by_cat.iterrows():
            lines.append(f"  {row['category']:<28} R$ {row['value_abs']:>12,.2f}  ({row['pct']:.0f}%)")

    lines += _section("Maiores estabelecimentos")
    if by_merchant.empty:
        lines.append("(sem dados de estabelecimento no período)")
    else:
        for _, row in by_merchant.iterrows():
            lines.append(
                f"  {row['merchant']:<28} R$ {row['value_abs']:>12,.2f}  ({int(row['n_transacoes'])}x)"
            )

    lines += _section("Evolução mensal (Receita / Despesa / Saldo)")
    if monthly.empty:
        lines.append("(sem histórico)")
    else:
        for _, row in monthly.iterrows():
            lines.append(
                f"  {row['month']}   R$ {row['Receitas']:>10,.2f}   "
                f"R$ {row['Despesas']:>10,.2f}   R$ {row['Saldo']:>10,.2f}"
            )

    lines += _section("Diagnósticos")
    if not diagnostics:
        lines.append("Nenhum diagnóstico no momento.")
    else:
        for d in diagnostics:
            lines.append(f"[{d.severidade.value.upper()}] {d.titulo}")
            lines.append(f"  {_plain(d.descricao)}")
            lines.append(f"  Recomendação: {_plain(d.recomendacao)}")
            lines.append("")

    lines += _section("Patrimônio e investimentos")
    if asset_positions.empty:
        lines.append("(nenhum ativo importado)")
    else:
        for _, row in asset_positions.iterrows():
            lines.append(f"  {row['nome']:<32} R$ {row['saldo_liquido']:>12,.2f}  ({row['tipo']})")
        total_patrimonio = asset_positions["saldo_liquido"].sum()
        lines.append(f"  {'TOTAL':<32} R$ {total_patrimonio:>12,.2f}")

    lines += _section("Dívidas")
    if debt_transactions.empty:
        lines.append("(nenhuma transação categorizada como Dívida no período)")
    else:
        for _, row in debt_transactions.iterrows():
            lines.append(f"  {row['date']}  {row['description']:<38} R$ {row['value']:>10,.2f}")
        total_divida = debt_transactions["value"].abs().sum()
        lines.append(f"  {'TOTAL':<50} R$ {total_divida:>10,.2f}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("SIFP — Sistema de Inteligência Financeira Pessoal")

    return "\n".join(lines)
