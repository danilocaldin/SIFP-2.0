"""
pdf_report_service.py
----------------------
Módulo 11 — Relatórios, versão PDF. Mesma regra do report_service (texto):
nenhuma lógica nova aqui, só formatação do que RelatorioService já compõe —
o PDF não pode nunca mostrar um número diferente do que a tela de Relatório
(texto) ou o Resumo mostram.

Pensado pra ser curto e simples de ler ("mesmo o usuário mais leigo
entenda", pedido explícito do Danilo) — não um documento institucional
denso: capa + resumo do mês + dois gráficos + os 3 diagnósticos mais
relevantes. Usa reportlab (puro Python, sem dependência nativa de SO) e as
mesmas cores da identidade visual do frontend (ver globals.css) — os tokens
do tema claro, já que um PDF é sempre uma superfície clara.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.shapes import Drawing

from sifp.domain.models import Diagnostic, DiagnosticSeverity
from sifp.services.formatting import format_brl, unescape_currency

# Paleta — mesmos hex do tema claro em frontend/src/app/globals.css.
INK = colors.HexColor("#16211f")
MUTED = colors.HexColor("#52625e")
BORDER = colors.HexColor("#dde5e2")
CARD = colors.HexColor("#f6f8f7")
PRIMARY = colors.HexColor("#0d5c63")
TEAL = colors.HexColor("#7fdcca")
RECEITA = colors.HexColor("#008300")
DESPESA = colors.HexColor("#e34948")
SALDO = colors.HexColor("#2a78d6")

_SEVERITY_COLOR = {
    DiagnosticSeverity.CRITICA: DESPESA,
    DiagnosticSeverity.ALTA: DESPESA,
    DiagnosticSeverity.MEDIA: colors.HexColor("#c98a1c"),
    DiagnosticSeverity.BAIXA: MUTED,
}

_PAGE_MARGIN = 1.8 * cm

_STYLES = {
    "brand": ParagraphStyle("brand", fontName="Helvetica-Bold", fontSize=15, textColor=INK, leading=18),
    "tagline": ParagraphStyle("tagline", fontName="Helvetica", fontSize=9.5, textColor=MUTED, leading=12),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=12, textColor=INK, spaceBefore=14, spaceAfter=6),
    "hero_label": ParagraphStyle("hero_label", fontName="Helvetica", fontSize=10, textColor=MUTED, leading=13),
    "hero_number": ParagraphStyle(
        "hero_number", fontName="Helvetica-Bold", fontSize=30, textColor=PRIMARY, leading=34, spaceBefore=2
    ),
    "stat_label": ParagraphStyle("stat_label", fontName="Helvetica", fontSize=8.5, textColor=MUTED, leading=11),
    "stat_value": ParagraphStyle(
        "stat_value", fontName="Helvetica-Bold", fontSize=14, textColor=INK, leading=17, spaceBefore=2
    ),
    "diag_title": ParagraphStyle(
        "diag_title", fontName="Helvetica-Bold", fontSize=10, textColor=INK, leading=13
    ),
    "diag_body": ParagraphStyle("diag_body", fontName="Helvetica", fontSize=9, textColor=MUTED, leading=12.5),
    "footer": ParagraphStyle("footer", fontName="Helvetica", fontSize=7.5, textColor=MUTED),
}


class _Rule(Flowable):
    """Linha horizontal fina — separador entre seções."""

    def __init__(self, width, color=BORDER, thickness=0.6):
        super().__init__()
        self.width = width
        self.color = color
        self.thickness = thickness

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


def _stat_cell(label: str, value: str, value_color=INK) -> list:
    style_value = ParagraphStyle(
        "stat_value_dyn", parent=_STYLES["stat_value"], textColor=value_color
    )
    return [Paragraph(label, _STYLES["stat_label"]), Paragraph(value, style_value)]


def _resumo_table(summary: dict, content_width: float) -> Table:
    cols = [content_width / 4.0] * 4
    row = [
        _stat_cell("Receitas", format_brl(summary["receitas"]), RECEITA),
        _stat_cell("Despesas", format_brl(summary["despesas"]), DESPESA),
        _stat_cell("Saldo", format_brl(summary["saldo"]), SALDO if summary["saldo"] >= 0 else DESPESA),
        _stat_cell("Taxa de poupança", f"{summary['taxa_poupanca']:.0f}%"),
    ]
    table = Table([row], colWidths=cols)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _categoria_chart(by_cat: pd.DataFrame, content_width: float) -> Drawing:
    top = by_cat.head(6).iloc[::-1]  # inverte pra maior categoria ficar no topo do gráfico horizontal
    labels = [f"{row['category'][:22]}" for _, row in top.iterrows()]
    values = [float(v) for v in top["value_abs"]]

    height = max(28 * len(values) + 20, 60)
    d = Drawing(content_width, height)

    chart = HorizontalBarChart()
    chart.x = 4
    chart.y = 4
    chart.width = content_width - 8
    chart.height = height - 12
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8.5
    chart.categoryAxis.labels.fillColor = INK
    chart.valueAxis.visible = False
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = DESPESA
    chart.bars.strokeColor = None
    chart.barWidth = 10
    chart.barSpacing = 6
    chart.groupSpacing = 0
    chart.barLabelFormat = lambda v: format_brl(v)
    chart.barLabels.fontName = "Helvetica-Bold"
    chart.barLabels.fontSize = 8
    chart.barLabels.fillColor = INK
    chart.barLabels.nudge = 10
    chart.barLabels.dx = 0
    d.add(chart)
    return d


def _evolucao_chart(monthly: pd.DataFrame, content_width: float) -> Drawing:
    recent = monthly.tail(6)
    months = [str(m).split("-")[-1] + "/" + str(m).split("-")[0][2:] for m in recent["month"]]
    receitas = [float(v) for v in recent["Receitas"]]
    despesas = [float(v) for v in recent["Despesas"]]

    height = 130
    d = Drawing(content_width, height)

    chart = VerticalBarChart()
    chart.x = 30
    chart.y = 20
    chart.width = content_width - 40
    chart.height = height - 30
    chart.data = [receitas, despesas]
    chart.categoryAxis.categoryNames = months
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.fillColor = MUTED
    chart.valueAxis.visible = False
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = RECEITA
    chart.bars[1].fillColor = DESPESA
    chart.bars.strokeColor = None
    chart.barWidth = 8
    chart.groupSpacing = 14
    chart.barSpacing = 2
    d.add(chart)
    return d


def _diagnosticos_section(diagnostics: list[Diagnostic], content_width: float) -> list:
    story: list = []
    principais = sorted(diagnostics, key=lambda d: d.prioridade)[:3]
    if not principais:
        story.append(Paragraph("Nenhum diagnóstico relevante neste período.", _STYLES["diag_body"]))
        return story

    for d in principais:
        dot_color = _SEVERITY_COLOR[d.severidade]
        dot_style = ParagraphStyle("dot", parent=_STYLES["diag_title"], textColor=dot_color)
        row = Table(
            [[Paragraph("●", dot_style), Paragraph(d.titulo, _STYLES["diag_title"])]],
            colWidths=[12, content_width - 12],
        )
        row.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(row)
        story.append(Paragraph(unescape_currency(d.recomendacao), _STYLES["diag_body"]))
        story.append(Spacer(1, 10))
    return story


def generate_pdf_report(
    period_label: str,
    summary: dict,
    by_cat: pd.DataFrame,
    monthly: pd.DataFrame,
    diagnostics: list[Diagnostic],
    patrimonio_total: float,
) -> bytes:
    buffer = BytesIO()
    content_width = A4[0] - 2 * _PAGE_MARGIN

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.6)
        y = _PAGE_MARGIN - 10
        canvas.line(_PAGE_MARGIN, y, A4[0] - _PAGE_MARGIN, y)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        gerado_em = datetime.now().strftime("%d/%m/%Y")
        canvas.drawString(_PAGE_MARGIN, y - 12, f"Sifra — Inteligência Financeira Pessoal · gerado em {gerado_em}")
        canvas.drawRightString(A4[0] - _PAGE_MARGIN, y - 12, f"Página {doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=_PAGE_MARGIN,
        rightMargin=_PAGE_MARGIN,
        topMargin=_PAGE_MARGIN,
        bottomMargin=_PAGE_MARGIN + 14,
        title=f"Relatório Sifra — {period_label}",
    )
    frame = Frame(_PAGE_MARGIN, _PAGE_MARGIN + 14, content_width, A4[1] - 2 * _PAGE_MARGIN - 14, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_footer)])

    story: list = []

    # Cabeçalho de marca
    story.append(Paragraph("SIFRA", _STYLES["brand"]))
    story.append(Paragraph(f"Relatório financeiro · {period_label}", _STYLES["tagline"]))
    story.append(Spacer(1, 14))

    # Hero — patrimônio
    story.append(Paragraph("Patrimônio total", _STYLES["hero_label"]))
    story.append(Paragraph(format_brl(patrimonio_total), _STYLES["hero_number"]))
    story.append(Spacer(1, 14))
    story.append(_Rule(content_width))
    story.append(Spacer(1, 10))

    # Resumo do mês
    story.append(Paragraph("Resumo do mês", _STYLES["h1"]))
    story.append(_resumo_table(summary, content_width))
    story.append(Spacer(1, 6))

    # Gastos por categoria
    if not by_cat.empty:
        story.append(Paragraph("Gastos por categoria", _STYLES["h1"]))
        story.append(_categoria_chart(by_cat, content_width))

    # Evolução mensal
    if not monthly.empty:
        story.append(Paragraph("Evolução mensal", _STYLES["h1"]))
        legend = Table(
            [[Paragraph("● Receitas", ParagraphStyle("lr", parent=_STYLES["stat_label"], textColor=RECEITA)),
              Paragraph("● Despesas", ParagraphStyle("ld", parent=_STYLES["stat_label"], textColor=DESPESA))]],
            colWidths=[80, 80],
        )
        legend.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
        story.append(legend)
        story.append(_evolucao_chart(monthly, content_width))

    # Diagnósticos
    story.append(Paragraph("Principais diagnósticos", _STYLES["h1"]))
    story += _diagnosticos_section(diagnostics, content_width)

    doc.build(story)
    return buffer.getvalue()
