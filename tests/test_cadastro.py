"""Testes de sifp/api/shared.py::validar_cpf/validar_telefone e do DTO
CadastroIn (wizard de onboarding pós-convite, routes_saas.py). Testes de
integração da rota POST /perfil/cadastro contra Postgres real ficam fora
do escopo desta suíte (mesmo motivo já documentado em
test_routes_saas_auth.py -- exigem um Postgres real)."""

import pytest
from pydantic import ValidationError

from sifp.api.shared import validar_cpf, validar_telefone


def test_cpf_valido_com_pontuacao_normaliza_pra_so_digitos():
    assert validar_cpf(None, "111.444.777-35") == "11144477735"


def test_cpf_valido_sem_pontuacao():
    assert validar_cpf(None, "52998224725") == "52998224725"


def test_cpf_com_digito_verificador_errado_rejeitado():
    with pytest.raises(ValueError):
        validar_cpf(None, "111.444.777-36")


def test_cpf_todos_digitos_iguais_rejeitado():
    with pytest.raises(ValueError):
        validar_cpf(None, "111.111.111-11")


def test_cpf_com_tamanho_errado_rejeitado():
    with pytest.raises(ValueError):
        validar_cpf(None, "123")


def test_telefone_com_pontuacao_normaliza():
    assert validar_telefone(None, "(11) 98888-7777") == "11988887777"


def test_telefone_fixo_sem_nono_digito_aceito():
    assert validar_telefone(None, "1133334444") == "1133334444"


def test_telefone_invalido_rejeitado():
    with pytest.raises(ValueError):
        validar_telefone(None, "123")


def test_cadastro_in_aceita_dados_validos():
    from sifp.api.routes_saas import CadastroIn

    body = CadastroIn(
        cpf="111.444.777-35",
        data_nascimento="1990-05-20",
        pais="Brasil",
        estado="SP",
        cidade="São Paulo",
        termos_aceitos=True,
        marketing_consent=False,
    )
    assert body.cpf == "11144477735"


def test_cadastro_in_rejeita_cpf_invalido():
    from sifp.api.routes_saas import CadastroIn

    with pytest.raises(ValidationError):
        CadastroIn(
            cpf="111.111.111-11",
            data_nascimento="1990-05-20",
            pais="Brasil",
            estado="SP",
            cidade="São Paulo",
            termos_aceitos=True,
        )


def test_cadastro_in_rejeita_data_nascimento_invalida():
    from sifp.api.routes_saas import CadastroIn

    with pytest.raises(ValidationError):
        CadastroIn(
            cpf="111.444.777-35",
            data_nascimento="31/13/2026",
            pais="Brasil",
            estado="SP",
            cidade="São Paulo",
            termos_aceitos=True,
        )
