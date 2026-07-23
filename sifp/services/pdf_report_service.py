"""
pdf_report_service.py
----------------------
Módulo 11 — Relatórios, versão PDF. Mesma regra do report_service (texto):
nenhuma lógica nova aqui, só formatação do que RelatorioService já compõe —
o PDF nunca pode mostrar um número diferente do que a tela de Relatório
(texto) ou o Resumo mostram. Paridade completa com o relatório em texto —
toda seção que existe lá existe aqui (categorias, estabelecimentos,
evolução mensal, todos os diagnósticos, patrimônio por ativo, dívidas).

Acabamento pensado pra cliente private de alta renda: predominantemente
tabelas (como um extrato de banco de verdade), só UM gráfico nativo bem
executado (evolução mensal — onde um gráfico realmente ajuda). Gastos por
categoria e maiores estabelecimentos deliberadamente NÃO são gráfico de
barras: com uma categoria concentrando a maior parte do gasto (comum em
extrato real), barras pequenas ficam ilegíveis e o rótulo de valor colide
com o eixo — tabela não tem esse problema e é mais fácil de ler em
qualquer distribuição de dados.

Usa reportlab (puro Python, sem dependência nativa de SO) e as mesmas
cores da identidade visual do frontend (ver globals.css) — os tokens do
tema claro, já que um PDF é sempre uma superfície clara.
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
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing

from sifp.domain.models import Diagnostic, DiagnosticSeverity
from sifp.services.formatting import format_brl, unescape_currency

# Paleta — mesmos hex da identidade visual em frontend/src/app/globals.css
# e frontend/src/app/icon.svg (marca: barras ascendentes em teal sobre
# fundo tinta).
INK = colors.HexColor("#16211f")
MUTED = colors.HexColor("#52625e")
BORDER = colors.HexColor("#dde5e2")
HEADER_BG = colors.HexColor("#f0f4f2")
PRIMARY = colors.HexColor("#0d5c63")
TEAL = colors.HexColor("#7fdcca")
RECEITA = colors.HexColor("#008300")
DESPESA = colors.HexColor("#e34948")
SALDO = colors.HexColor("#2a78d6")
AMBAR = colors.HexColor("#c98a1c")

_SEVERITY_COLOR = {
    DiagnosticSeverity.CRITICA: DESPESA,
    DiagnosticSeverity.ALTA: DESPESA,
    DiagnosticSeverity.MEDIA: AMBAR,
    DiagnosticSeverity.BAIXA: MUTED,
}
_SEVERITY_LABEL = {
    DiagnosticSeverity.CRITICA: "Crítico",
    DiagnosticSeverity.ALTA: "Alta prioridade",
    DiagnosticSeverity.MEDIA: "Atenção",
    DiagnosticSeverity.BAIXA: "Observação",
}

_PAGE_MARGIN = 1.9 * cm

_STYLES = {
    "h1": ParagraphStyle(
        "h1", fontName="Helvetica-Bold", fontSize=12.5, textColor=PRIMARY, spaceBefore=18, spaceAfter=8
    ),
    "stat_label": ParagraphStyle("stat_label", fontName="Helvetica", fontSize=8.5, textColor=MUTED, leading=11),
    "stat_value": ParagraphStyle(
        "stat_value", fontName="Helvetica-Bold", fontSize=14, textColor=INK, leading=17, spaceBefore=2
    ),
    "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, leading=10),
    "td": ParagraphStyle("td", fontName="Helvetica", fontSize=9, textColor=INK, leading=12),
    "td_muted": ParagraphStyle("td_muted", fontName="Helvetica", fontSize=9, textColor=MUTED, leading=12),
    "diag_title": ParagraphStyle("diag_title", fontName="Helvetica-Bold", fontSize=10.5, textColor=INK, leading=13),
    "diag_badge": ParagraphStyle("diag_badge", fontName="Helvetica-Bold", fontSize=7.5, leading=10),
    "diag_body": ParagraphStyle("diag_body", fontName="Helvetica", fontSize=9, textColor=MUTED, leading=13),
    "diag_reco_label": ParagraphStyle(
        "diag_reco_label", fontName="Helvetica-Bold", fontSize=8, textColor=PRIMARY, leading=11, spaceBefore=3
    ),
    "empty": ParagraphStyle("empty", fontName="Helvetica-Oblique", fontSize=9, textColor=MUTED, leading=12),
    "disclaimer_title": ParagraphStyle(
        "disclaimer_title", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, leading=11, spaceBefore=16
    ),
    "disclaimer": ParagraphStyle(
        "disclaimer", fontName="Helvetica-Oblique", fontSize=7.5, textColor=MUTED, leading=10.5
    ),
}

_DISCLAIMER = (
    "Este relatório é gerado automaticamente pelo Sifra com base nos extratos e posições importados pelo "
    "próprio usuário — não é auditado nem verificado por terceiros, e sua precisão depende da precisão dos "
    "dados de origem. O conteúdo tem finalidade exclusivamente informativa e não constitui recomendação de "
    "investimento, oferta, análise de valores mobiliários ou aconselhamento financeiro, contábil, jurídico ou "
    "tributário. O Sifra não é uma instituição financeira, corretora ou consultoria de investimentos "
    "registrada, e não se responsabiliza por decisões tomadas com base neste documento."
)


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


def _truncate(text: str, max_len: int) -> str:
    text = str(text)
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


def _stat_cell(label: str, value: str, value_color=INK) -> list:
    style_value = ParagraphStyle("stat_value_dyn", parent=_STYLES["stat_value"], textColor=value_color)
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


def _data_table(
    headers: list[str], rows: list[list], col_widths: list[float], align: list[str]
) -> Table:
    """Tabela padrão do relatório — cabeçalho com fundo sutil, linhas finas
    entre registros, numérico alinhado à direita. Reaproveitada por todas
    as seções tabulares (categorias, estabelecimentos, patrimônio, dívidas)."""
    header_row = [Paragraph(h, _STYLES["th"]) for h in headers]
    table = Table([header_row] + rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, BORDER),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for col, a in enumerate(align):
        if a == "right":
            style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    table.setStyle(TableStyle(style))
    return table


def _categoria_table(by_cat: pd.DataFrame, content_width: float) -> Table:
    rows = []
    for _, row in by_cat.iterrows():
        rows.append(
            [
                Paragraph(_truncate(row["category"], 34), _STYLES["td"]),
                Paragraph(format_brl(row["value_abs"]), _STYLES["td"]),
                Paragraph(f"{row['pct']:.0f}%", _STYLES["td_muted"]),
            ]
        )
    w = content_width
    return _data_table(
        ["Categoria", "Valor", "% do total"], rows, [w * 0.56, w * 0.28, w * 0.16], ["left", "right", "right"]
    )


def _estabelecimentos_table(by_merchant: pd.DataFrame, content_width: float) -> Table:
    rows = []
    for _, row in by_merchant.head(10).iterrows():
        rows.append(
            [
                Paragraph(_truncate(row["merchant"], 42), _STYLES["td"]),
                Paragraph(format_brl(row["value_abs"]), _STYLES["td"]),
                Paragraph(f"{int(row['n_transacoes'])}x", _STYLES["td_muted"]),
            ]
        )
    w = content_width
    return _data_table(
        ["Estabelecimento", "Valor", "Transações"], rows, [w * 0.58, w * 0.26, w * 0.16], ["left", "right", "right"]
    )


def _patrimonio_table(asset_positions: pd.DataFrame, content_width: float) -> Table:
    rows = []
    for _, row in asset_positions.iterrows():
        rows.append(
            [
                Paragraph(_truncate(row["nome"], 30), _STYLES["td"]),
                Paragraph(_truncate(row.get("tipo") or "—", 28), _STYLES["td_muted"]),
                Paragraph(format_brl(row["saldo_liquido"]), _STYLES["td"]),
            ]
        )
    w = content_width
    return _data_table(
        ["Ativo", "Tipo", "Valor"], rows, [w * 0.42, w * 0.34, w * 0.24], ["left", "left", "right"]
    )


def _dividas_table(debt_transactions: pd.DataFrame, content_width: float) -> Table:
    rows = []
    for _, row in debt_transactions.iterrows():
        data_str = pd.to_datetime(row["date"]).strftime("%d/%m/%Y")
        rows.append(
            [
                Paragraph(data_str, _STYLES["td_muted"]),
                Paragraph(_truncate(row["description"], 40), _STYLES["td"]),
                Paragraph(format_brl(abs(row["value"])), _STYLES["td"]),
            ]
        )
    w = content_width
    return _data_table(
        ["Data", "Descrição", "Valor"], rows, [w * 0.18, w * 0.56, w * 0.26], ["left", "left", "right"]
    )


def _evolucao_chart(monthly: pd.DataFrame, content_width: float) -> Drawing:
    recent = monthly.tail(12)
    months = [str(m).split("-")[-1] + "/" + str(m).split("-")[0][2:] for m in recent["month"]]
    receitas = [float(v) for v in recent["Receitas"]]
    despesas = [float(v) for v in recent["Despesas"]]

    height = 155
    d = Drawing(content_width, height)

    chart = VerticalBarChart()
    chart.x = 8
    chart.y = 24
    chart.width = content_width - 16
    chart.height = height - 44
    chart.data = [receitas, despesas]
    chart.categoryAxis.categoryNames = months
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.fillColor = MUTED
    chart.categoryAxis.strokeColor = BORDER
    chart.valueAxis.visible = False
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = RECEITA
    chart.bars[1].fillColor = DESPESA
    chart.bars.strokeColor = None
    # Largura/espaçamento reagem à quantidade de meses (12 vs 3) pra nunca
    # espremer ou esticar demais as barras.
    chart.barWidth = max(5, min(9, 90 // max(len(months), 1)))
    chart.groupSpacing = chart.barWidth * 1.6
    chart.barSpacing = 1.5
    d.add(chart)
    return d


def _diagnosticos_section(diagnostics: list[Diagnostic], content_width: float) -> list:
    story: list = []
    ordenados = sorted(diagnostics, key=lambda d: d.prioridade)
    if not ordenados:
        story.append(Paragraph("Nenhum diagnóstico relevante neste período.", _STYLES["empty"]))
        return story

    for d in ordenados:
        badge_color = _SEVERITY_COLOR[d.severidade]
        badge_style = ParagraphStyle(
            "badge_dyn", parent=_STYLES["diag_badge"], textColor=colors.white, backColor=badge_color
        )
        header = Table(
            [
                [
                    Paragraph(f" {_SEVERITY_LABEL[d.severidade]} ", badge_style),
                    Paragraph(d.titulo, _STYLES["diag_title"]),
                ]
            ],
            colWidths=[78, content_width - 78],
        )
        header.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 6),
                    ("LEFTPADDING", (1, 0), (1, 0), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        block = [
            header,
            Spacer(1, 5),
            Paragraph(unescape_currency(d.descricao), _STYLES["diag_body"]),
            Paragraph("Recomendação", _STYLES["diag_reco_label"]),
            Paragraph(unescape_currency(d.recomendacao), _STYLES["diag_body"]),
            Spacer(1, 14),
        ]
        story.append(KeepTogether(block))
    return story


def _draw_mark(canvas, x: float, y: float, size: float, badge: bool = True):
    """Desenha a marca do Sifra (barras ascendentes) direto no canvas —
    mesma geometria de frontend/src/app/icon.svg, sem precisar de uma
    dependência nova (svglib) só pra isso. `badge=False` desenha só as
    barras, sem o fundo em rounded-square (usado no motivo decorativo
    grande da capa, onde o fundo escuro já é o próprio painel)."""
    canvas.saveState()
    if badge:
        canvas.setFillColor(INK)
        canvas.roundRect(x, y, size, size, size * 0.22, fill=1, stroke=0)
    canvas.setFillColor(TEAL)
    bar_w = size * 0.1
    gap = size * 0.18
    heights = [0.22, 0.34, 0.46, 0.56]
    for i, h in enumerate(heights):
        bx = x + size * 0.18 + i * gap
        canvas.roundRect(bx, y + size * 0.2, bar_w, size * h, bar_w * 0.5, fill=1, stroke=0)
    canvas.restoreState()


def generate_pdf_report(
    period_label: str,
    summary: dict,
    by_cat: pd.DataFrame,
    by_merchant: pd.DataFrame,
    monthly: pd.DataFrame,
    diagnostics: list[Diagnostic],
    asset_positions: pd.DataFrame,
    debt_transactions: pd.DataFrame,
    patrimonio_total: float,
    nome_titular: str | None = None,
) -> bytes:
    buffer = BytesIO()
    content_width = A4[0] - 2 * _PAGE_MARGIN
    header_height = 30

    def _page_decoration(canvas, doc):
        canvas.saveState()
        # Faixa de destaque no topo — presença de marca em toda página, sem
        # depender só do cabeçalho.
        canvas.setFillColor(PRIMARY)
        canvas.rect(0, A4[1] - 3, A4[0], 3, fill=1, stroke=0)

        # Cabeçalho: marca + período, repetido em toda página (pedido do
        # Danilo — o relatório de referência que ele mandou tem isso).
        top_y = A4[1] - _PAGE_MARGIN + 2
        mark_size = 13
        _draw_mark(canvas, _PAGE_MARGIN, top_y - mark_size + 3, mark_size)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.setFillColor(INK)
        canvas.drawString(_PAGE_MARGIN + mark_size + 6, top_y - 8, "SIFRA")
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(A4[0] - _PAGE_MARGIN, top_y - 8, period_label)
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(_PAGE_MARGIN, top_y - mark_size - 2, A4[0] - _PAGE_MARGIN, top_y - mark_size - 2)

        # Rodapé
        y = _PAGE_MARGIN - 10
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.6)
        canvas.line(_PAGE_MARGIN, y, A4[0] - _PAGE_MARGIN, y)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        gerado_em = datetime.now().strftime("%d/%m/%Y")
        canvas.drawString(_PAGE_MARGIN, y - 12, f"Sifra — Inteligência Financeira Pessoal · gerado em {gerado_em}")
        canvas.drawRightString(A4[0] - _PAGE_MARGIN, y - 12, f"Página {doc.page}")
        canvas.restoreState()

    def _draw_cover(canvas, doc):
        """Capa em página própria — desenhada inteira no canvas (não flui
        por Platypus): é conteúdo fixo, então dá mais controle de
        composição do que lutar com Frame pra uma página só. Painel escuro
        assimétrico no topo (marca + período), motivo decorativo grande
        (as mesmas barras ascendentes do ícone, em baixa opacidade) e
        bastante espaço em branco embaixo — padrão de capa de relatório
        institucional: um elemento visual dominante, texto mínimo,
        respiro generoso, nunca a página inteira ocupada."""
        canvas.saveState()
        panel_h = A4[1] * 0.40
        panel_y = A4[1] - panel_h

        canvas.setFillColor(INK)
        canvas.rect(0, panel_y, A4[0], panel_h, fill=1, stroke=0)

        # Motivo decorativo: barras ascendentes grandes, em opacidade baixa,
        # ancoradas na quina inferior direita do painel — segundo foco
        # visual, assimétrico em relação à marca (canto superior esquerdo).
        canvas.saveState()
        canvas.setFillAlpha(0.16)
        _draw_mark(canvas, A4[0] - _PAGE_MARGIN - 150, panel_y - 40, 190, badge=False)
        canvas.restoreState()

        # Marca, canto superior esquerdo do painel.
        mark_size = 30
        mark_x = _PAGE_MARGIN
        mark_y = A4[1] - _PAGE_MARGIN - mark_size
        _draw_mark(canvas, mark_x, mark_y, mark_size)
        canvas.setFont("Helvetica-Bold", 19)
        canvas.setFillColor(colors.white)
        canvas.drawString(mark_x + mark_size + 10, mark_y + mark_size * 0.28, "SIFRA")

        # Período, canto superior direito do painel — equilibra a
        # composição sem competir com a marca.
        canvas.setFont("Helvetica", 9.5)
        canvas.setFillColor(TEAL)
        canvas.drawRightString(A4[0] - _PAGE_MARGIN, A4[1] - _PAGE_MARGIN - 4, period_label.upper())

        # Título, base do painel.
        canvas.setFont("Helvetica", 12)
        canvas.setFillColor(colors.HexColor("#c9ded9"))
        canvas.drawString(_PAGE_MARGIN, panel_y + 26, "Relatório financeiro")

        canvas.restoreState()

        # Abaixo do painel: quem é o titular, e só o número que mais
        # importa — o resto da página fica em branco de propósito.
        y = panel_y - 60
        if nome_titular:
            canvas.setFont("Helvetica-Bold", 13)
            canvas.setFillColor(INK)
            canvas.drawString(_PAGE_MARGIN, y, f"Preparado para {nome_titular}")
            y -= 46
        else:
            y -= 14

        canvas.setFont("Helvetica", 10.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(_PAGE_MARGIN, y, "Patrimônio total")
        canvas.setFont("Helvetica-Bold", 40)
        canvas.setFillColor(PRIMARY)
        canvas.drawString(_PAGE_MARGIN, y - 46, format_brl(patrimonio_total))

        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.6)
        gerado_em = datetime.now().strftime("%d/%m/%Y")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(_PAGE_MARGIN, _PAGE_MARGIN - 4, f"Sifra — Inteligência Financeira Pessoal · gerado em {gerado_em}")

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=_PAGE_MARGIN,
        rightMargin=_PAGE_MARGIN,
        topMargin=_PAGE_MARGIN + header_height,
        bottomMargin=_PAGE_MARGIN + 14,
        title=f"Relatório Sifra — {period_label}",
    )
    content_frame = Frame(
        _PAGE_MARGIN,
        _PAGE_MARGIN + 14,
        content_width,
        A4[1] - 2 * _PAGE_MARGIN - 14 - header_height,
        id="main",
    )
    # Capa não usa o frame pra nada (tudo desenhado direto em _draw_cover),
    # mas BaseDocTemplate exige ao menos um por PageTemplate.
    cover_frame = Frame(_PAGE_MARGIN, _PAGE_MARGIN, content_width, 10, id="cover")
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[cover_frame], onPage=_draw_cover),
            PageTemplate(id="content", frames=[content_frame], onPage=_page_decoration),
        ]
    )

    story: list = [NextPageTemplate("content"), PageBreak()]

    # Resumo do mês
    story.append(Paragraph("Resumo do mês", _STYLES["h1"]))
    story.append(_resumo_table(summary, content_width))

    # Gastos por categoria
    story.append(Paragraph("Gastos por categoria", _STYLES["h1"]))
    if by_cat.empty:
        story.append(Paragraph("Sem despesas registradas no período.", _STYLES["empty"]))
    else:
        story.append(_categoria_table(by_cat, content_width))

    # Maiores estabelecimentos
    story.append(Paragraph("Maiores estabelecimentos", _STYLES["h1"]))
    if by_merchant.empty:
        story.append(Paragraph("Sem dados de estabelecimento no período.", _STYLES["empty"]))
    else:
        story.append(_estabelecimentos_table(by_merchant, content_width))

    # Evolução mensal
    story.append(Paragraph("Evolução mensal", _STYLES["h1"]))
    if monthly.empty:
        story.append(Paragraph("Sem histórico suficiente ainda.", _STYLES["empty"]))
    else:
        legend = Table(
            [
                [
                    Paragraph("● Receitas", ParagraphStyle("lr", parent=_STYLES["stat_label"], textColor=RECEITA)),
                    Paragraph("● Despesas", ParagraphStyle("ld", parent=_STYLES["stat_label"], textColor=DESPESA)),
                ]
            ],
            colWidths=[80, 80],
        )
        legend.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
        story.append(legend)
        story.append(Spacer(1, 4))
        story.append(_evolucao_chart(monthly, content_width))

    # Patrimônio e investimentos
    story.append(Paragraph("Patrimônio e investimentos", _STYLES["h1"]))
    if asset_positions.empty:
        story.append(Paragraph("Nenhum ativo importado ainda.", _STYLES["empty"]))
    else:
        story.append(_patrimonio_table(asset_positions, content_width))

    # Dívidas
    story.append(Paragraph("Dívidas", _STYLES["h1"]))
    if debt_transactions.empty:
        story.append(Paragraph("Nenhuma transação categorizada como dívida no período.", _STYLES["empty"]))
    else:
        story.append(_dividas_table(debt_transactions, content_width))

    # Diagnósticos — página própria, lista completa
    story.append(PageBreak())
    story.append(Paragraph("Diagnósticos", _STYLES["h1"]))
    story += _diagnosticos_section(diagnostics, content_width)

    # Aviso legal
    story.append(_Rule(content_width))
    story.append(Paragraph("AVISO", _STYLES["disclaimer_title"]))
    story.append(Paragraph(_DISCLAIMER, _STYLES["disclaimer"]))

    doc.build(story)
    return buffer.getvalue()
