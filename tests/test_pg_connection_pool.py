"""Testes de sifp/repositories/pg/connection.py — o pool de conexão
Postgres criado pra corrigir um achado real de auditoria (sem pool, cada
request abria uma conexão TCP+TLS+auth nova, e sob uso concorrente do
/chat ou /narrativa — que seguravam a conexão aberta durante a chamada ao
LLM — o número de conexões físicas crescia sem limite até estourar o do
projeto Supabase). Nenhum teste aqui toca um Postgres real: o
ConnectionPool em si é substituído por um dublê."""

import json

import pytest

from sifp.repositories.pg import connection as connection_module


@pytest.fixture(autouse=True)
def _reset_pool_singleton():
    """O pool é um singleton de módulo -- sem resetar entre testes, o
    primeiro teste que criar um pool falso "vazaria" pros seguintes."""
    connection_module._pool = None
    yield
    connection_module._pool = None


class _FakeCursor:
    def __init__(self, executed):
        self._executed = executed

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._executed.append((sql, params))


class _FakeTransactionCtx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self):
        self.executed = []

    def cursor(self):
        return _FakeCursor(self.executed)

    def transaction(self):
        return _FakeTransactionCtx()


class _FakeConnCtx:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, *exc):
        return False


class _FakePool:
    """Substitui psycopg_pool.ConnectionPool inteiro -- registra quantas
    vezes foi instanciado e devolve sempre a MESMA conexão falsa, pra
    provar que scoped_transaction() pede a conexão ao pool em vez de
    abrir uma nova a cada chamada."""

    instancias_criadas = 0

    def __init__(self, conninfo, **kwargs):
        _FakePool.instancias_criadas += 1
        self.conninfo = conninfo
        self.kwargs = kwargs
        self.conn = _FakeConn()

    def connection(self):
        return _FakeConnCtx(self.conn)


def test_get_pool_e_um_singleton_criado_so_na_primeira_chamada(monkeypatch):
    monkeypatch.setattr(connection_module, "ConnectionPool", _FakePool)
    _FakePool.instancias_criadas = 0

    pool1 = connection_module._get_pool()
    pool2 = connection_module._get_pool()

    assert pool1 is pool2
    assert _FakePool.instancias_criadas == 1


def test_scoped_transaction_pega_conexao_do_pool_em_vez_de_abrir_nova(monkeypatch):
    monkeypatch.setattr(connection_module, "ConnectionPool", _FakePool)

    with connection_module.scoped_transaction("user-123") as conn:
        assert isinstance(conn, _FakeConn)

    # SET LOCAL role + set_config do claim -- os dois comandos que fazem a
    # RLS de fato filtrar por usuário (ver docstring do módulo).
    sqls = [sql for sql, _ in conn.executed]
    assert any("SET LOCAL role authenticated" in s for s in sqls)
    assert any("set_config" in s for s in sqls)
    claims_call = next(p for sql, p in conn.executed if p is not None)
    assert json.loads(claims_call[0])["sub"] == "user-123"


def test_scoped_transaction_reusa_o_mesmo_pool_em_chamadas_diferentes(monkeypatch):
    monkeypatch.setattr(connection_module, "ConnectionPool", _FakePool)
    _FakePool.instancias_criadas = 0

    with connection_module.scoped_transaction("user-a"):
        pass
    with connection_module.scoped_transaction("user-b"):
        pass

    assert _FakePool.instancias_criadas == 1  # um pool só, reaproveitado


def test_modulo_importa_sem_abrir_pool_nem_conectar(monkeypatch):
    """Os testes da suíte importam sifp.api.main (que importa este módulo
    transitivamente) sem SUPABASE_DB_URL configurada -- o pool não pode
    ser criado no import, só no primeiro uso real."""
    assert connection_module._pool is None


# ---------------------------------------------------------------------
# read_sql_query -- achado real de auditoria (3ª varredura): pandas não
# reconhece psycopg.Connection como backend suportado, caindo num
# fallback pensado pra sqlite3.Error que não trata erros reais de
# Postgres. read_sql_query busca via cursor nativo, sem depender desse
# caminho do pandas.
# ---------------------------------------------------------------------
class _Coluna:
    """Imita o objeto Column que psycopg3 devolve em cursor.description
    (tem .name, diferente da tupla 7-upla do DB-API 2.0 clássico)."""

    def __init__(self, name):
        self.name = name


class _FakeCursorComResultado:
    def __init__(self, rows, columns, executed):
        self._rows = rows
        self.description = [_Coluna(c) for c in columns]
        self._executed = executed

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._executed.append((sql, params))

    def fetchall(self):
        return self._rows


class _FakeConnComResultado:
    def __init__(self, rows, columns):
        self.executed = []
        self._rows = rows
        self._columns = columns

    def cursor(self):
        return _FakeCursorComResultado(self._rows, self._columns, self.executed)


def test_read_sql_query_monta_dataframe_a_partir_do_cursor():
    conn = _FakeConnComResultado(
        rows=[("Mercado", -100.0), ("Salário", 5000.0)],
        columns=["description", "value"],
    )
    df = connection_module.read_sql_query(conn, "SELECT description, value FROM transactions")

    assert list(df.columns) == ["description", "value"]
    assert len(df) == 2
    assert df.iloc[0]["description"] == "Mercado"
    assert conn.executed == [("SELECT description, value FROM transactions", None)]


def test_read_sql_query_passa_params_pro_cursor():
    conn = _FakeConnComResultado(rows=[], columns=["description", "category"])
    connection_module.read_sql_query(
        conn, "SELECT description, category FROM transactions WHERE category != %s", params=("X",)
    )
    assert conn.executed[0][1] == ("X",)


def test_read_sql_query_vazio_devolve_dataframe_vazio_sem_erro():
    conn = _FakeConnComResultado(rows=[], columns=[])
    df = connection_module.read_sql_query(conn, "SELECT 1 WHERE false")
    assert df.empty


def test_read_sql_query_parse_dates_converte_coluna_pra_datetime():
    import pandas as pd

    conn = _FakeConnComResultado(rows=[("2026-06-15", 100.0)], columns=["date", "value"])
    df = connection_module.read_sql_query(
        conn, "SELECT date, value FROM daily_balances", parse_dates=["date"]
    )
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
