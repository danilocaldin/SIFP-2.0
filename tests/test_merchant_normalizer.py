"""
Testes do MerchantNormalizer (Módulo 4). Inclui a regressão do falso
positivo real: "99 Pay" sendo confundido com um código numérico de ruído
e virando só "Pay".
"""

import pandas as pd
import pytest

from sifp.intelligence.merchant_normalizer import MerchantNormalizer


@pytest.fixture
def normalizer():
    return MerchantNormalizer()


@pytest.mark.parametrize(
    "description,expected",
    [
        ("Compra no débito autorizada - Uber", "Uber"),
        ("UBER TRIP", "Uber"),
        ("UBER*123", "Uber"),
        ("Compra no débito autorizada - iFood", "iFood"),
        ("IFOOD*12345", "iFood"),
        ("IFOOD MERCADO", "iFood"),
        ("NETFLIX.COM", "Netflix"),
        ("AMAZON.COM.BR", "Amazon"),
        ("Compra no débito autorizada - 99 Pay", "99 Pay"),  # regressão: não é código de ruído
        ("Compra no débito autorizada - 48 493 311 Francis", "Francis"),  # código de doc real (8 dígitos)
    ],
)
def test_normalize_known_cases(normalizer, description, expected):
    assert normalizer.normalize(description) == expected


def test_normalize_empty_description_returns_placeholder(normalizer):
    assert normalizer.normalize("") == "Desconhecido"
    assert normalizer.normalize(None) == "Desconhecido"


@pytest.mark.parametrize(
    "description,expected",
    [
        # Achado real de auditoria: o match por alias era substring solta
        # (mesmo bug já corrigido em apply_keyword_rules, escapou aqui) --
        # "UBER" dentro de "UBERABA"/"UBERLANDIA" virava "Uber".
        ("Compra no débito autorizada - Posto Uberaba", "Posto Uberaba"),
        ("Compra no débito autorizada - Supermercado Uberlandia", "Supermercado Uberlandia"),
    ],
)
def test_normalize_nao_casa_alias_dentro_de_outra_palavra(normalizer, description, expected):
    assert normalizer.normalize(description) == expected


def test_normalize_corta_no_primeiro_separador_nao_no_ultimo(normalizer):
    """Achado real de auditoria: com múltiplos " - " na descrição, cortar
    no ÚLTIMO (rsplit) perdia parte do nome da contraparte quando ela
    mesma contém um "-" (ex: nome da loja + filial)."""
    resultado = normalizer.normalize("Compra no débito autorizada - Loja XYZ - Filial 2")
    assert resultado == "Loja Xyz - Filial 2"


def test_normalize_unknown_merchant_falls_back_to_title_case(normalizer):
    assert normalizer.normalize("Pix enviado - Maria Jose Vieira") == "Maria Jose Vieira"


def test_normalize_batch_matches_normalize(normalizer):
    descriptions = pd.Series(["UBER TRIP", "IFOOD*1", "Lançamento XYZ"])
    result = normalizer.normalize_batch(descriptions)
    assert list(result) == ["Uber", "iFood", "Lançamento Xyz"]


def test_normalize_alias_mais_especifico_vence_mesmo_fora_de_ordem(normalizer, monkeypatch):
    """Melhoria viável da 3ª varredura: antes, o PRIMEIRO alias que
    casasse na ordem de inserção do dicionário vencia -- funcionava hoje
    só porque "AMAZON PRIME" está escrito antes de "AMAZON" no
    dicionário real, mas não era garantido pela lógica. Reordena o
    dicionário de propósito (o curto primeiro) e confirma que o mais
    específico ainda vence, igual a apply_keyword_rules já garante pra
    categorização."""
    import sifp.intelligence.merchant_normalizer as mod

    aliases_fora_de_ordem = {
        "AMAZON": "Amazon",
        "AMAZON PRIME": "Amazon Prime",
    }
    monkeypatch.setattr(mod, "MERCHANT_ALIASES", aliases_fora_de_ordem)

    assert normalizer.normalize("AMAZON PRIME VIDEO") == "Amazon Prime"
    assert normalizer.normalize("AMAZON.COM.BR") == "Amazon"
