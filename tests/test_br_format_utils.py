"""
Testes de sifp/importers/br_format_utils.py::parse_brl_number.

Cobre uma varredura de segurança que achou 3 bugs reais de corrupção
silenciosa de valores monetários: valor redondo sem decimais perdendo
3 ordens de grandeza, débito sem decimais virando positivo, e negativo
entre parênteses virando zero.
"""

import pytest

from sifp.importers.br_format_utils import parse_brl_number


@pytest.mark.parametrize(
    "raw, esperado",
    [
        # Casos que já funcionavam -- não deixar a correção quebrar isso.
        ("1.234,56", 1234.56),
        ("R$ 1.234,56", 1234.56),
        ("-45,00", -45.0),
        ("45,00 D", -45.0),
        ("45,00 C", 45.0),
        ("0,00", 0.0),
        # Bug 1: valor redondo em milhar sem decimais perdia 3 ordens de
        # grandeza ("1.500" -> 1.5, porque float() lia o ponto como decimal).
        ("1.500", 1500.0),
        ("12.345.678", 12345678.0),
        ("R$ 2.000", 2000.0),
        # Bug 2: débito sem decimais não caía no sinal negativo (a
        # detecção de "D" exigia vírgula presente na string).
        ("500 D", -500.0),
        ("1.500 D", -1500.0),
        # Achado real de auditoria (3ª varredura): "D" colado ao valor sem
        # espaço não tinha fronteira de palavra (\b) entre o último dígito
        # e o "D", então a regex \bD\b não casava e o débito virava
        # positivo silenciosamente.
        ("45,00D", -45.0),
        ("500D", -500.0),
        ("1.234,56D", -1234.56),
        ("45,00C", 45.0),
        # Bug 3: negativo entre parênteses (convenção contábil) virava
        # 0.0 silenciosamente (float() não aceita parênteses).
        ("(150,00)", -150.0),
        ("(1.500,00)", -1500.0),
        ("(500)", -500.0),
        # Números já numéricos (vindos de célula do Excel) passam direto.
        (1500, 1500.0),
        (1234.56, 1234.56),
        (-45.0, -45.0),
    ],
)
def test_parse_brl_number(raw, esperado):
    assert parse_brl_number(raw) == pytest.approx(esperado)


def test_parse_brl_number_valor_vazio_ou_invalido_retorna_zero():
    assert parse_brl_number("") == 0.0
    assert parse_brl_number(None) == 0.0
    assert parse_brl_number(float("nan")) == 0.0
