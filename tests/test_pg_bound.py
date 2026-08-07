"""Testes de sifp/repositories/pg/bound.py — o adaptador ConnBound que
injeta `conn` como primeiro argumento em toda chamada de método, pra que
os repositories Postgres (que exigem `conn` explícita) sejam usados pela
camada de services exatamente como os repositories SQLite (sem `conn`).
Não precisa de Postgres real: um repo/conn falsos bastam pra provar o
mecanismo de encaminhamento em si."""

import pytest

from sifp.repositories.pg.bound import ConnBound


class FakeConn:
    """Só precisa ser um objeto identificável (comparado por identidade)."""


class FakeRepo:
    def get_all(self, conn, *, limit=None):
        return {"conn": conn, "limit": limit}

    def insert(self, conn, valor):
        return {"conn": conn, "valor": valor}

    @property
    def nome_tabela(self):
        return "transactions"


def test_conn_bound_injeta_conn_como_primeiro_argumento_posicional():
    conn = FakeConn()
    bound = ConnBound(FakeRepo(), conn)
    resultado = bound.insert("valor-qualquer")
    assert resultado == {"conn": conn, "valor": "valor-qualquer"}


def test_conn_bound_injeta_conn_preservando_kwargs():
    conn = FakeConn()
    bound = ConnBound(FakeRepo(), conn)
    resultado = bound.get_all(limit=10)
    assert resultado == {"conn": conn, "limit": 10}


def test_conn_bound_usa_a_mesma_conn_em_chamadas_diferentes():
    conn = FakeConn()
    bound = ConnBound(FakeRepo(), conn)
    r1 = bound.get_all()
    r2 = bound.insert("x")
    assert r1["conn"] is conn
    assert r2["conn"] is conn


def test_conn_bound_repassa_atributo_nao_chamavel_sem_injetar_conn():
    # uma property/atributo simples não é método -- não faz sentido (nem
    # é possível) injetar conn nele, então deve passar direto.
    bound = ConnBound(FakeRepo(), FakeConn())
    assert bound.nome_tabela == "transactions"


def test_conn_bound_propaga_atributo_inexistente():
    bound = ConnBound(FakeRepo(), FakeConn())
    with pytest.raises(AttributeError):
        bound.metodo_que_nao_existe()
