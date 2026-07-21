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


def test_normalize_unknown_merchant_falls_back_to_title_case(normalizer):
    assert normalizer.normalize("Pix enviado - Maria Jose Vieira") == "Maria Jose Vieira"


def test_normalize_batch_matches_normalize(normalizer):
    descriptions = pd.Series(["UBER TRIP", "IFOOD*1", "Lançamento XYZ"])
    result = normalizer.normalize_batch(descriptions)
    assert list(result) == ["Uber", "iFood", "Lançamento Xyz"]
