from sifp.services.formatting import (
    format_brl,
    format_brl_md,
    format_brl_number,
    formatar_mes,
    unescape_currency,
)


def test_formatar_mes():
    assert formatar_mes("2026-06") == "Jun/2026"
    assert formatar_mes("2025-12") == "Dez/2025"
    assert formatar_mes("2026-01") == "Jan/2026"


def test_format_brl_number_thousands_and_decimal_separators():
    assert format_brl_number(3006.49) == "3.006,49"
    assert format_brl_number(1234567.8) == "1.234.567,80"
    assert format_brl_number(9.5) == "9,50"
    assert format_brl_number(0) == "0,00"


def test_format_brl_number_negative():
    assert format_brl_number(-1776.68) == "-1.776,68"


def test_format_brl_adds_prefix():
    assert format_brl(3006.49) == "R$ 3.006,49"


def test_format_brl_md_escapes_dollar_sign():
    assert format_brl_md(3006.49) == "R\\$ 3.006,49"


def test_format_brl_md_roundtrips_with_unescape_currency():
    valor = format_brl_md(15304.81)
    assert unescape_currency(valor) == format_brl(15304.81)
