"""
Testes do BTGInvestmentImporter. Usam texto SINTÉTICO (não o PDF real do
usuário) que reproduz fielmente a peculiaridade de extração descoberta
no desenvolvimento: pdfplumber "engole" a letra "a" minúscula quando ela
é o ÚLTIMO caractere de uma palavra (bug de fonte do gerador do
relatório) — por isso "Data"/"Conta"/"Carteira" saem quebrados no texto
sintético abaixo, exatamente como no arquivo real, e o parser precisa
funcionar mesmo assim.
"""

import pytest

from sifp.importers.btg_investment_importer import parse_positions_from_text

# Texto sintético no mesmo formato do extrato real (nome/CNPJ fictícios),
# incluindo a linha de Detalhamento (7 números) que o parser deve
# IGNORAR em favor da linha de Posição (8 números).
SAMPLE_TEXT = """Extrato d  Cont  Investimento
Per�odo de 01/06/26   30/06/26
Fundo de Investimento - Posi��o - Portf�lio de fundos
Saldo
Quantidade Cota��o Saldo Provis�o Provis�o Saldo Varia��o
Dat  Refer�nci  L�quido R$ 1
de Cotas Atual R$ Bruto R$ de IR R$ de IOF R$ L�quido R$ Nominal R$
31/05/26
Fundo Exemplo XP - Classe CNPJ: 11.111.111/0001-11
30/06/26 500,00 100,00000000 5,50000000 550,00 1,00 2,00 547,00 47,00
Total em fundos 550,00 1,00 2,00 547,00 47,00
Fundo de Investimento - Detalhamento - Fundo Exemplo XP - Classe CNPJ: 11.111.111/0001-11
Dat  Compr  Quantidade de Cotas Cota��o Compr  R$ Valor de Compr  Ajustado R$ 1 Saldo Bruto R$ Provis�o de IR R$ Provis�o de IOF R$ 2 Saldo L�quido R$ 3
15/06/26 100,00000000 5,00000000 500,00 550,00 1,00 2,00 547,00
Total 100,00000000 550,00 1,00 2,00 547,00
Fundo de Investimento - Rentabilidade
Fundo Benchmark 1 Fundo M�s % 2 Benchmark M�s % Fundo Ano % 3 Benchmark Ano % Fundo 12 meses % 4 Benchmark 12 meses %
Fundo Exemplo XP CDI 0,95 1,12 5,50 6,85 12,30 14,78
"""


def test_parses_single_fund_position():
    positions = parse_positions_from_text(SAMPLE_TEXT, source_file="teste.pdf")
    assert len(positions) == 1

    p = positions[0]
    assert p.nome == "Fundo Exemplo XP"
    assert p.identificador == "11.111.111/0001-11"
    assert p.tipo == "Fundo de Investimento"
    assert p.data_referencia == "2026-06-30"
    assert p.quantidade == pytest.approx(100.0)
    assert p.cotacao == pytest.approx(5.5)
    assert p.saldo_bruto == pytest.approx(550.0)
    assert p.saldo_liquido == pytest.approx(547.0)


def test_ignores_detalhamento_row_uses_posicao_row():
    """A linha de Detalhamento (7 números, cotação de compra 5,00) não
    pode ser confundida com a linha de Posição (8 números, cotação atual 5,50)."""
    positions = parse_positions_from_text(SAMPLE_TEXT)
    assert positions[0].cotacao == pytest.approx(5.5)  # não 5.00 (preço de compra)


def test_parses_rentabilidade():
    positions = parse_positions_from_text(SAMPLE_TEXT)
    p = positions[0]
    assert p.benchmark == "CDI"
    assert p.rentabilidade_mes_pct == pytest.approx(0.95)
    assert p.rentabilidade_ano_pct == pytest.approx(5.50)
    assert p.rentabilidade_12m_pct == pytest.approx(12.30)


def test_parses_benchmark_numeric_returns():
    """Regressão: o parser guardava só o NOME do benchmark ('CDI'), sem os
    valores numéricos — impossibilitando comparar fundo vs benchmark."""
    positions = parse_positions_from_text(SAMPLE_TEXT)
    p = positions[0]
    assert p.benchmark_mes_pct == pytest.approx(1.12)
    assert p.benchmark_ano_pct == pytest.approx(6.85)
    assert p.benchmark_12m_pct == pytest.approx(14.78)


def test_no_fund_found_returns_empty_list():
    assert parse_positions_from_text("texto sem nenhum fundo aqui") == []


def test_multiple_funds_all_parsed():
    text = SAMPLE_TEXT + (
        "\nOutro Fundo Renda Fixa - Classe CNPJ: 22.222.222/0001-22\n"
        "30/06/26 1000,00 50,00000000 20,00000000 1000,00 0,50 1,50 998,00 -2,00\n"
    )
    positions = parse_positions_from_text(text)
    names = {p.nome for p in positions}
    assert names == {"Fundo Exemplo XP", "Outro Fundo Renda Fixa"}


def test_deduplicates_same_fund_appearing_twice():
    # SAMPLE_TEXT já tem o mesmo fundo citado 2x (Posição + Detalhamento);
    # só deve gerar 1 AssetPosition.
    positions = parse_positions_from_text(SAMPLE_TEXT)
    assert len(positions) == 1
