"""
Testes do BTGImporter — cobrem especificamente os dois bugs reais
encontrados durante o desenvolvimento (concatenação de NaN em vez de
string vazia escondendo linhas de Saldo Diário; extração do nome do
titular quebrando com NaN), para que não voltem a acontecer.
"""

import pytest

from sifp.importers.btg_importer import BTGImporter
from tests.conftest import FakeUploadedFile


@pytest.fixture
def importer():
    return BTGImporter()


def test_supports_extensions(importer):
    assert importer.supports("extrato.csv")
    assert importer.supports("extrato.xls")
    assert importer.supports("extrato.XLSX")
    assert not importer.supports("extrato.pdf")
    assert not importer.supports("")


def test_csv_happy_path(importer, sample_btg_csv_bytes):
    upload = FakeUploadedFile(sample_btg_csv_bytes, "extrato.csv")
    df, balances = importer.read(upload)

    assert len(df) == 4
    assert balances.empty
    assert list(df.columns) == ["date", "description", "value", "bank_category", "self_transfer"]
    assert not df["self_transfer"].any()  # sem account_holder_hint, não detecta

    # valores em formato BR convertidos corretamente
    row = df[df["description"] == "SUPERMERCADO PAO DE ACUCAR"].iloc[0]
    assert row["value"] == pytest.approx(-345.67)

    receita = df[df["description"].str.contains("PIX RECEBIDO")].iloc[0]
    assert receita["value"] == pytest.approx(2500.00)

    # mesmo formato de string do importador de Excel ("%Y-%m-%d %H:%M") —
    # ver comentário em btg_importer.py sobre por que os dois precisam
    # bater (misturar formatos diferentes na coluna date da tabela
    # transactions faz o pandas devolver NaT pro formato minoritário).
    assert all(len(d) == 16 and d[10] == " " for d in df["date"])


def test_csv_com_hint_detecta_self_transfer(importer):
    """Achado real de auditoria: o CSV "achatado" não tem bloco de
    metadados com o nome do titular (diferente do Excel), então nunca
    detectava transferência pra si mesmo. account_holder_hint (vindo de
    uma importação em Excel anterior, ver ImportService) resolve isso --
    inclusive ignorando acento/caixa, igual ao caminho do Excel."""
    content = (
        "Data;Descrição;Valor\n"
        "01/06/2026;PIX RECEBIDO JOAO SILVA;2500,00\n"
        "02/06/2026;joão da silva santos;-1000,00\n"
        "03/06/2026;UBER TRIP SAO PAULO;-28,50\n"
    ).encode("utf-8-sig")
    upload = FakeUploadedFile(content, "extrato.csv")

    df, _ = importer.read(upload, account_holder_hint="João da Silva Santos")

    self_transfers = df[df["self_transfer"]]
    assert len(self_transfers) == 1
    assert self_transfers.iloc[0]["description"] == "joão da silva santos"
    assert not df[df["description"] != "joão da silva santos"]["self_transfer"].any()


def test_csv_unsupported_columns_raises(importer):
    bad_csv = b"Col1,Col2\nfoo,bar\n"
    upload = FakeUploadedFile(bad_csv, "extrato.csv")
    with pytest.raises(ValueError):
        importer.read(upload)


def test_csv_datas_com_e_sem_horario_misturadas_nao_somem(importer):
    """Achado real de auditoria: pd.to_datetime infere o formato do
    PRIMEIRO valor da coluna e descarta (NaT) qualquer linha com formato
    diferente -- uma coluna real com "01/06/2026 14:30" (com horário) e
    "02/06/2026" (sem horário) misturados fazia a linha minoritária
    desaparecer da importação em silêncio."""
    content = (
        "Data;Descrição;Valor\n"
        "01/06/2026 14:30;PIX RECEBIDO JOAO SILVA;2500,00\n"
        "02/06/2026;SUPERMERCADO PAO DE ACUCAR;-345,67\n"
        "03/06/2026 09:00;UBER TRIP SAO PAULO;-28,50\n"
        "04/06/2026;NETFLIX.COM;-55,90\n"
    )
    upload = FakeUploadedFile(content.encode("utf-8-sig"), "extrato.csv")
    df, _ = importer.read(upload)
    assert len(df) == 4  # nenhuma linha descartada por formato de data diferente


def test_csv_muitas_datas_invalidas_levanta_erro_em_vez_de_importar_parcial(importer):
    content = (
        "Data;Descrição;Valor\n"
        "data-invalida;PIX RECEBIDO JOAO SILVA;2500,00\n"
        "tambem-invalida;SUPERMERCADO PAO DE ACUCAR;-345,67\n"
        "03/06/2026;UBER TRIP SAO PAULO;-28,50\n"
        "04/06/2026;NETFLIX.COM;-55,90\n"
    )
    upload = FakeUploadedFile(content.encode("utf-8-sig"), "extrato.csv")
    with pytest.raises(ValueError, match="linhas do CSV têm uma data"):
        importer.read(upload)


def test_xlsx_transaction_count_excludes_balance_snapshots(importer, sample_btg_xlsx_bytes):
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    df, balances = importer.read(upload)

    # 6 lançamentos reais na fixture (Amigao Brasil, Uber, Pix Maria,
    # Restaurante Almoco + 2 self-transfer), 3 "Saldo Diário"
    assert len(df) == 6
    assert len(balances) == 3
    assert not df["description"].str.contains("Saldo Di", case=False).any()


def test_xlsx_daily_balance_values(importer, sample_btg_xlsx_bytes):
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    _, balances = importer.read(upload)

    assert set(balances["balance"].round(2)) == {1223.40, 464.19, 442.40}


def test_xlsx_self_transfer_detection(importer, sample_btg_xlsx_bytes, client_name):
    """
    Regressão do caso real: transferência para o próprio titular (mesmo
    nome como contraparte) precisa ser marcada self_transfer=True, e uma
    transação para OUTRA pessoa não pode ser marcada.
    """
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    df, _ = importer.read(upload)

    self_transfers = df[df["self_transfer"]]
    assert len(self_transfers) == 2
    assert all(client_name in d for d in self_transfers["description"])

    pix_to_other = df[df["description"].str.contains("Maria Jose Vieira")]
    assert len(pix_to_other) == 1
    assert not pix_to_other.iloc[0]["self_transfer"]


def test_xlsx_bank_category_column_populated(importer, sample_btg_xlsx_bytes):
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    df, _ = importer.read(upload)

    uber_row = df[df["description"].str.contains("Uber")].iloc[0]
    assert uber_row["bank_category"] == "Transporte"


def test_xlsx_repeated_metadata_block_does_not_leak_into_transactions(importer, sample_btg_xlsx_bytes):
    """
    Regressão: o bloco de metadados que se repete no meio/fim do arquivo
    (Cliente:/CPF:/... e o cabeçalho da tabela de novo) não pode aparecer
    como uma "transação" fantasma.
    """
    upload = FakeUploadedFile(sample_btg_xlsx_bytes, "extrato.xlsx")
    df, _ = importer.read(upload)

    assert not df["description"].str.contains("Cliente", case=False).any()
    assert not df["description"].str.contains("CPF", case=False).any()


def test_unsupported_extension_raises(importer):
    upload = FakeUploadedFile(b"qualquer coisa", "extrato.pdf")
    with pytest.raises(ValueError):
        importer.read(upload)
