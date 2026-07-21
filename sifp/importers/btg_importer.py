"""
importers/btg_importer.py
--------------------------
BTGImporter: lê extratos do BTG Pactual em CSV, XLS ou XLSX e devolve
dados normalizados (Módulo 1 + 2). Lógica portada de parser.py (já
validada em produção contra extratos reais) — nenhuma regra de negócio
mudou nesta migração, só a organização em classe + interface comum.

O layout exato do extrato do BTG varia por canal de exportação. Dois
formatos são suportados:

1) CSV "achatado" (uma linha = um cabeçalho, colunas Data/Descrição/Valor).

2) XLS/XLSX do extrato de conta corrente baixado pelo internet banking:
   várias linhas de metadados (Cliente/CPF/Agência/Conta/Saldo) antes da
   tabela, esse bloco de metadados SE REPETE a cada "página" do extrato,
   colunas úteis intercaladas com colunas em branco, e uma coluna extra
   "Categoria" com a categorização que o próprio BTG já sugere. Há também
   linhas de "Saldo Diário" (saldo do dia, não é uma transação) e
   transferências do titular para si mesmo (ex: para uma conta
   investimento), detectadas comparando a "contraparte" com o nome do
   titular extraído do cabeçalho do extrato.
"""

import io

import pandas as pd

from sifp.importers.base import StatementImporter
from sifp.importers.br_format_utils import (
    find_column,
    normalize_col,
    parse_brl_date,
    parse_brl_number,
    strip_accents,
)

# Possíveis nomes de coluna (em minúsculo, sem acento) para cada campo
COLUMN_ALIASES = {
    "date": ["data e hora", "data", "data lancamento", "data lançamento",
              "dt lancamento", "data mov"],
    "description": [
        "descricao",
        "descrição",
        "historico",
        "histórico",
        "lancamento",
        "lançamento",
        "detalhe",
        "nome",
    ],
    "value": ["valor", "valor (r$)", "valor r$", "montante"],
    "bank_category": ["categoria"],
    "transaction_type": ["transacao", "transação", "tipo de transacao", "natureza"],
}

# Descrições que na verdade são snapshots de saldo (não transações reais)
# e devem ser descartadas do extrato em Excel.
NON_TRANSACTION_DESCRIPTIONS = {"saldo diario", "saldo diário", "saldo do dia"}

EXCEL_HEADER_SCAN_ROWS = 30

SUPPORTED_EXTENSIONS = {"csv", "xls", "xlsx"}


class BTGImporter(StatementImporter):
    institution_name = "BTG Pactual"

    def supports(self, filename: str) -> bool:
        return _get_extension_from_name(filename) in SUPPORTED_EXTENSIONS

    def read(self, uploaded_file) -> tuple[pd.DataFrame, pd.DataFrame]:
        ext = _get_extension_from_name(getattr(uploaded_file, "name", ""))
        if ext in ("xls", "xlsx"):
            return _read_btg_excel(uploaded_file, ext)
        if ext == "csv":
            return _read_btg_csv(uploaded_file)
        raise ValueError(
            f"Formato de arquivo não suportado ('.{ext}'). Envie um CSV, XLS ou XLSX."
        )


def _get_extension_from_name(name: str) -> str:
    name = name or ""
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _find_account_holder_name(df_raw: pd.DataFrame, label_col_idx: int) -> str | None:
    """
    Procura a linha "Cliente: <nome>" no bloco de metadados do extrato
    (a mesma coluna onde fica o rótulo "Data e hora" também tem "Cliente:",
    "CPF:", "Agência:" etc. — o valor fica sempre na coluna seguinte).
    Usado para detectar transferências que o titular faz para si mesmo.
    """
    if label_col_idx + 1 >= df_raw.shape[1]:
        return None
    labels = df_raw.iloc[:, label_col_idx].fillna("").astype(str)
    mask = labels.apply(lambda s: "cliente" in strip_accents(s).strip().lower())
    matches = labels[mask]
    if matches.empty:
        return None
    row_idx = matches.index[0]
    name = df_raw.iloc[row_idx, label_col_idx + 1]
    if pd.isna(name) or not str(name).strip():
        return None
    return str(name).strip()


# ---------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------
def _read_btg_csv(uploaded_file) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_bytes = uploaded_file.read()

    text = None
    for encoding in ["utf-8-sig", "latin1", "cp1252"]:
        try:
            text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Não foi possível decodificar o arquivo. Verifique o encoding.")

    first_line = text.splitlines()[0] if text.splitlines() else ""
    sep = ";" if first_line.count(";") >= first_line.count(",") else ","

    df_raw = pd.read_csv(io.StringIO(text), sep=sep, engine="python", skip_blank_lines=True)

    df = _try_map_columns_from_headers(df_raw)
    if df is None:
        for skip in range(1, 6):
            try:
                df_retry = pd.read_csv(
                    io.StringIO(text), sep=sep, engine="python", skiprows=skip
                )
                df = _try_map_columns_from_headers(df_retry)
                if df is not None:
                    break
            except Exception:
                continue

    if df is None:
        raise ValueError(
            "Não foi possível identificar as colunas de Data, Descrição e Valor "
            "no arquivo. Verifique se o CSV exportado do BTG Pactual contém "
            "essas informações."
        )

    df["date"] = parse_brl_date(df["date"])
    df["value"] = df["value"].apply(parse_brl_number)
    df["description"] = df["description"].astype(str).str.strip()
    if "bank_category" not in df.columns:
        df["bank_category"] = ""
    else:
        df["bank_category"] = df["bank_category"].fillna("").astype(str).str.strip()

    df = df.dropna(subset=["date"])
    df = df[df["description"] != ""]
    df = df[df["description"].str.lower() != "nan"]

    # Mesmo formato de string do importador de Excel ("%Y-%m-%d %H:%M") —
    # a coluna date da tabela transactions é TEXT sem tipo fixo, e o
    # pandas infere o formato de data a partir da maioria das linhas ao
    # ler de volta (parse_dates=["date"] em get_all()); se os dois
    # importadores gravassem formatos diferentes, misturar CSV com Excel
    # faria as datas do formato minoritário virarem NaT silenciosamente.
    df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M")
    df["self_transfer"] = False
    df = df[["date", "description", "value", "bank_category", "self_transfer"]].reset_index(drop=True)
    empty_balances = pd.DataFrame(columns=["date", "balance"])
    return df, empty_balances


def _try_map_columns_from_headers(df_raw: pd.DataFrame):
    columns_normalized = [normalize_col(c) for c in df_raw.columns]

    idx_date = find_column(columns_normalized, COLUMN_ALIASES["date"])
    idx_desc = find_column(columns_normalized, COLUMN_ALIASES["description"])
    idx_value = find_column(columns_normalized, COLUMN_ALIASES["value"])

    if idx_date is None or idx_desc is None or idx_value is None:
        return None

    idx_cat = find_column(columns_normalized, COLUMN_ALIASES["bank_category"])

    out = pd.DataFrame(
        {
            "date": df_raw.iloc[:, idx_date],
            "description": df_raw.iloc[:, idx_desc],
            "value": df_raw.iloc[:, idx_value],
        }
    )
    if idx_cat is not None:
        out["bank_category"] = df_raw.iloc[:, idx_cat]
    return out


# ---------------------------------------------------------------------
# XLS / XLSX
# ---------------------------------------------------------------------
def _read_btg_excel(uploaded_file, ext: str = "xls") -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_bytes = uploaded_file.read()
    engine = "xlrd" if ext == "xls" else "openpyxl"

    try:
        df_raw = pd.read_excel(
            io.BytesIO(raw_bytes), sheet_name=0, header=None, engine=engine
        )
    except Exception:
        # Alguns bancos exportam ".xls" que na verdade é uma tabela HTML.
        try:
            tables = pd.read_html(io.BytesIO(raw_bytes))
            df_raw = tables[0]
            df_raw.columns = range(df_raw.shape[1])
        except Exception:
            raise ValueError(
                "Não foi possível abrir o arquivo Excel. Verifique se ele não "
                "está corrompido e se a extensão (.xls/.xlsx) corresponde ao "
                "formato real do arquivo."
            )

    header_info = _find_excel_header(df_raw)
    if header_info is None:
        raise ValueError(
            "Não foi possível localizar a linha de cabeçalho (Data, Descrição, "
            "Valor) no arquivo Excel. O layout pode ter mudado — envie um "
            "exemplo para ajustarmos o parser."
        )
    header_row, cols = header_info
    account_holder_name = _find_account_holder_name(df_raw, cols["date"])

    body = df_raw.iloc[header_row + 1:].reset_index(drop=True)

    date_raw = body.iloc[:, cols["date"]]
    desc_raw = body.iloc[:, cols["description"]]
    value_raw = body.iloc[:, cols["value"]]
    trans_type_raw = (
        body.iloc[:, cols["transaction_type"]] if cols.get("transaction_type") is not None else None
    )
    bank_cat_raw = (
        body.iloc[:, cols["bank_category"]] if cols.get("bank_category") is not None else None
    )

    date_parsed = parse_brl_date(date_raw)

    # Uma linha só é uma transação de verdade se a coluna de data contiver
    # uma data válida. Isso filtra de uma vez só: blocos de metadados
    # repetidos, linhas em branco e o rodapé, sem depender de padrões de
    # texto frágeis.
    valid_mask = date_parsed.notna()

    description = desc_raw.fillna("").astype(str).str.strip()
    if trans_type_raw is not None:
        # fillna("") ANTES do astype(str) é essencial: células vazias do Excel
        # chegam aqui como float NaN, e concatenar string com NaN propaga NaN
        # em vez de virar string vazia, fazendo com que linhas de "Saldo
        # Diário" (que não têm Transação) escapassem do filtro abaixo.
        trans_type = trans_type_raw.fillna("").astype(str).str.strip()
        trans_type = trans_type.where(~trans_type.str.lower().isin(["nan", "none"]), "")
        combined_desc = (trans_type + " - " + description).str.strip(" -")
        combined_desc = combined_desc.where(trans_type != "", description)
    else:
        combined_desc = description

    # Transferência para você mesmo (ex: para uma conta investimento e de
    # volta): o BTG registra essas com o próprio nome do titular como
    # "contraparte" na coluna Descrição.
    if account_holder_name:
        holder_norm = strip_accents(account_holder_name).strip().lower()
        desc_only_norm = description.apply(lambda d: strip_accents(str(d)).strip().lower())
        is_self_transfer = desc_only_norm == holder_norm
    else:
        is_self_transfer = pd.Series(False, index=description.index)

    out = pd.DataFrame(
        {
            "date": date_parsed,
            "description": combined_desc,
            "value": value_raw.apply(parse_brl_number),
            "bank_category": (
                bank_cat_raw.astype(str).str.strip() if bank_cat_raw is not None else ""
            ),
            "self_transfer": is_self_transfer,
        }
    )
    out = out[valid_mask].reset_index(drop=True)

    # Separa snapshots de saldo diário (não são transações) do restante.
    desc_norm = out["description"].apply(lambda d: strip_accents(str(d)).strip().lower())
    is_balance_snapshot = desc_norm.isin(NON_TRANSACTION_DESCRIPTIONS)

    balances = out[is_balance_snapshot][["date", "value"]].rename(columns={"value": "balance"})
    balances = balances.sort_values("date").reset_index(drop=True)
    balances["date"] = balances["date"].dt.strftime("%Y-%m-%d %H:%M")

    out = out[~is_balance_snapshot].reset_index(drop=True)

    out["bank_category"] = out["bank_category"].replace("nan", "")
    out["date"] = out["date"].dt.strftime("%Y-%m-%d %H:%M")

    if out.empty:
        raise ValueError(
            "O arquivo foi lido, mas nenhuma transação válida foi encontrada "
            "após remover cabeçalhos repetidos e linhas de saldo diário."
        )

    return out[["date", "description", "value", "bank_category", "self_transfer"]], balances


def _find_excel_header(df_raw: pd.DataFrame):
    n_rows = min(EXCEL_HEADER_SCAN_ROWS, len(df_raw))
    for row_idx in range(n_rows):
        row_values = [normalize_col(v) for v in df_raw.iloc[row_idx].tolist()]

        idx_date = find_column(row_values, COLUMN_ALIASES["date"])
        idx_desc = find_column(row_values, COLUMN_ALIASES["description"])
        idx_value = find_column(row_values, COLUMN_ALIASES["value"])

        if idx_date is None or idx_desc is None or idx_value is None:
            continue

        return row_idx, {
            "date": idx_date,
            "description": idx_desc,
            "value": idx_value,
            "bank_category": find_column(row_values, COLUMN_ALIASES["bank_category"]),
            "transaction_type": find_column(row_values, COLUMN_ALIASES["transaction_type"]),
        }
    return None
