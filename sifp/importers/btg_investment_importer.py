"""
importers/btg_investment_importer.py
--------------------------------------
Lê o extrato da Conta Investimento do BTG (PDF) e devolve a posição
patrimonial (Módulo 6): um AssetPosition por fundo/ativo.

Não implementa StatementImporter (Módulo 1) — é um formato de saída
diferente (posição patrimonial num instante, não uma tabela de
transações de fluxo de caixa).

Peculiaridade deste PDF: a letra "a" minúscula em posição FINAL de
palavra some na extração de texto (bug de fonte/CMap do gerador do
relatório — "Conta" vira "Cont", "Data" vira "Dat", "Carteira" vira
"Carteir"; "Saldo"/"Aplicação"/"Classe" saem intactos porque não
terminam em "a"). Por isso o parser NUNCA compara contra nomes de
coluna ou rótulo — só contra âncoras que sobrevivem: "CNPJ:" (maiúsculo
+ ":"), datas, números, e a contagem de colunas numéricas por linha
(a linha de Posição tem 8 números após a data; a de Detalhamento/compra
tem 7 — isso já basta para diferenciar as duas sem precisar ler rótulo
nenhum).
"""

import io
import re

import pdfplumber

from sifp.domain.models import AssetPosition

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{2}$")
_BR_NUM_RE = re.compile(r"^-?\d+(\.\d{3})*,\d{2,}$|^-$")
_FUND_CNPJ_RE = re.compile(r"([A-Za-z0-9À-ÿ .]+?)\s*-\s*Classe\s+CNPJ:\s*([\d./\-]+)")
_PERIOD_RE = re.compile(r"Per.odo de (\d{2}/\d{2}/\d{2}).*?(\d{2}/\d{2}/\d{2})")


def _parse_brl_number(token: str) -> float | None:
    if token is None or token == "-":
        return None
    return float(token.replace(".", "").replace(",", "."))


def _to_iso_date(date_br: str) -> str:
    dia, mes, ano = date_br.split("/")
    ano_completo = f"20{ano}" if len(ano) == 2 else ano
    return f"{ano_completo}-{mes}-{dia}"


def _find_rentabilidade(lines: list[str], fund_name: str):
    """Procura a linha da tabela de Rentabilidade para este fundo:
    '<nome do fundo> <benchmark> <6 percentuais>' na ordem Fundo Mês /
    Benchmark Mês / Fundo Ano / Benchmark Ano / Fundo 12m / Benchmark 12m.
    Retorna um dict com os 6 valores + nome do benchmark, ou None se não
    achar (a rentabilidade é um "nice to have" — a posição em si não
    depende dela). Guardar TAMBÉM os números do benchmark (não só o nome)
    é o que permite comparar "fundo rendeu X% acima/abaixo do CDI" depois,
    em vez de só saber que o benchmark se chama CDI."""
    for line in lines:
        if not line.startswith(fund_name):
            continue
        tokens = line[len(fund_name):].strip().split()
        nums = [t for t in tokens if _BR_NUM_RE.match(t) and t != "-"]
        if len(nums) != 6:
            continue
        benchmark_tokens = [t for t in tokens if t not in nums]
        benchmark_nome = " ".join(benchmark_tokens) or None
        fundo_mes, bench_mes, fundo_ano, bench_ano, fundo_12m, bench_12m = (
            _parse_brl_number(n) for n in nums
        )
        return {
            "fundo_mes": fundo_mes, "fundo_ano": fundo_ano, "fundo_12m": fundo_12m,
            "benchmark_mes": bench_mes, "benchmark_ano": bench_ano, "benchmark_12m": bench_12m,
            "benchmark_nome": benchmark_nome,
        }
    return None


def parse_positions_from_text(full_text: str, source_file: str = "") -> list[AssetPosition]:
    """Núcleo do parser, separado da leitura do PDF em si para poder ser
    testado com texto sintético (sem precisar gerar um PDF de verdade)."""
    lines = full_text.split("\n")
    positions: list[AssetPosition] = []
    seen: set[tuple[str, str]] = set()

    for i, line in enumerate(lines):
        if "CNPJ:" not in line:
            continue
        fund_match = _FUND_CNPJ_RE.search(line)
        if not fund_match:
            continue
        fund_name = fund_match.group(1).strip()
        cnpj = fund_match.group(2).strip()

        # a linha de POSIÇÃO (não a de Detalhamento/compra) é a que tem
        # 8 números após a data -- procura nas próximas linhas
        position_row = None
        for j in range(i + 1, min(i + 4, len(lines))):
            tokens = lines[j].split()
            if not tokens or not _DATE_RE.match(tokens[0]):
                continue
            nums = [t for t in tokens[1:] if _BR_NUM_RE.match(t)]
            if len(nums) == 8:
                position_row = (tokens[0], nums)
                break

        key = (fund_name, cnpj)
        if position_row is None or key in seen:
            continue
        seen.add(key)

        data_ref_str, nums = position_row
        # ordem das 8 colunas: SaldoLiquidoAnterior, Quantidade, Cotacao,
        # SaldoBruto, ProvisaoIR, ProvisaoIOF, SaldoLiquido, VariacaoNominal
        quantidade = _parse_brl_number(nums[1])
        cotacao = _parse_brl_number(nums[2])
        saldo_bruto = _parse_brl_number(nums[3]) or 0.0
        saldo_liquido = _parse_brl_number(nums[6]) or 0.0

        rentab = _find_rentabilidade(lines, fund_name)

        positions.append(
            AssetPosition(
                nome=fund_name,
                identificador=cnpj,
                tipo="Fundo de Investimento",
                instituicao="BTG Pactual",
                data_referencia=_to_iso_date(data_ref_str),
                quantidade=quantidade,
                cotacao=cotacao,
                saldo_bruto=saldo_bruto,
                saldo_liquido=saldo_liquido,
                rentabilidade_mes_pct=rentab["fundo_mes"] if rentab else None,
                rentabilidade_ano_pct=rentab["fundo_ano"] if rentab else None,
                rentabilidade_12m_pct=rentab["fundo_12m"] if rentab else None,
                benchmark=rentab["benchmark_nome"] if rentab else None,
                benchmark_mes_pct=rentab["benchmark_mes"] if rentab else None,
                benchmark_ano_pct=rentab["benchmark_ano"] if rentab else None,
                benchmark_12m_pct=rentab["benchmark_12m"] if rentab else None,
                source_file=source_file,
            )
        )

    return positions


class BTGInvestmentImporter:
    institution_name = "BTG Pactual"

    def supports(self, filename: str) -> bool:
        return (filename or "").lower().endswith(".pdf")

    def read(self, uploaded_file) -> list[AssetPosition]:
        raw_bytes = uploaded_file.read()
        try:
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            raise ValueError(
                "Não foi possível ler o PDF. Verifique se o arquivo não está "
                "corrompido e se é um extrato de conta investimento do BTG."
            )

        if not full_text.strip():
            raise ValueError(
                "O PDF não trouxe texto legível (pode ser uma imagem escaneada, "
                "sem camada de texto)."
            )

        positions = parse_positions_from_text(
            full_text, source_file=getattr(uploaded_file, "name", "")
        )

        if not positions:
            raise ValueError(
                "Não foi possível identificar nenhuma posição de fundo no PDF. "
                "O layout pode ser diferente do extrato de conta investimento "
                "padrão do BTG — envie um exemplo para ajustarmos o parser."
            )

        return positions
