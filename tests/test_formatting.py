from sifp.services.formatting import formatar_mes


def test_formatar_mes():
    assert formatar_mes("2026-06") == "Jun/2026"
    assert formatar_mes("2025-12") == "Dez/2025"
    assert formatar_mes("2026-01") == "Jan/2026"
