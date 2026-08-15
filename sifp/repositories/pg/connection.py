"""
sifp/repositories/pg/connection.py
-----------------------------------
Conexão Postgres (Supabase) para o SaaS multiusuário. NÃO confundir com
sifp/repositories/connection.py (SQLite) — aquele continua servindo só o
Streamlit pessoal do Danilo, intocado; este aqui é usado exclusivamente
por sifp/api/main.py a partir da migração multiusuário.

O ponto central — scoped_transaction(user_id): abre uma conexão nova,
inicia uma transação explícita e, ANTES de qualquer query de repository
rodar, troca a role da sessão pra "authenticated" e seta o claim "sub" via
set_config. É isso que faz a Row Level Security (ver pg/schema.sql)
realmente filtrar por usuário — sem esse passo a conexão continua logada
como o dono das tabelas, que por padrão no Postgres NÃO é afetado por RLS.

Os dois comandos usam LOCAL (SET LOCAL / set_config(..., is_local=true)),
nunca a forma sem LOCAL — a conexão passa pelo "transaction pooler" do
Supabase (Supavisor em modo transação), que pode reaproveitar a mesma
conexão física de rede para requests de OUTRO usuário assim que a
transação atual termina. Um SET sem LOCAL vazaria a role/claim pra essa
próxima requisição — exatamente o tipo de vazamento entre clientes que
todo esse desenho existe pra evitar. Com LOCAL, o valor não sobrevive além
do COMMIT/ROLLBACK da transação atual.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Iterator

import pandas as pd
import psycopg
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("SUPABASE_DB_URL", "")

# Antes disto, cada request abria uma conexão TCP+TLS+auth NOVA contra o
# Supavisor -- handshake inteiro a cada troca de mês no dashboard, e sem
# nenhum teto: sob uso concorrente (ex: vários usuários no /chat ao mesmo
# tempo, que segura a conexão aberta durante a chamada à Anthropic -- ver
# routes_saas.py) o número de conexões físicas crescia sem limite até
# estourar o do projeto Supabase, derrubando TODAS as rotas com 500, não
# só as de IA. O pool é criado só na primeira vez que uma conexão é
# pedida (nunca no import do módulo) -- os testes importam este módulo
# sem SUPABASE_DB_URL configurada, e abrir o pool eager quebraria a
# suíte inteira tentando conectar em uma URL vazia.
_pool: ConnectionPool | None = None


def _desligar_prepared_statements(conn: psycopg.Connection) -> None:
    """Achado real de auditoria (recurso de assessor, Fase 3): o Supavisor
    (transaction pooler do Supabase) pode trocar a conexão física de rede
    por baixo de uma mesma conexão lógica do pool a qualquer momento entre
    checkouts. psycopg3 prepara automaticamente no servidor qualquer
    statement repetido 5+ vezes (`prepare_threshold`, default 5) -- como
    TODA `scoped_transaction()` roda exatamente os mesmos dois comandos
    ("SET LOCAL role authenticated" + o set_config), isso sempre acontece
    cedo. Quando o Supavisor troca a conexão física, o statement "_pg3_0"
    preparado na física antiga não existe (ou já existe outro com o mesmo
    nome de outra sessão) na física nova -> InvalidSqlStatementName /
    DuplicatePreparedStatement, aleatório e intermitente. Isso sempre foi
    um risco latente (qualquer request já abria uma scoped_transaction),
    mas só ficou fácil de reproduzir quando o recurso de assessor passou a
    abrir DUAS conexões por requisição (uma pra checar o vínculo, outra
    pro cliente) em auth.py::get_db, dobrando a velocidade de atingir o
    threshold. Desligar o preparo automático (recomendação oficial do
    Supabase pra qualquer pooler em modo transação) resolve na raiz."""
    conn.prepare_threshold = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1,
            max_size=10,
            max_idle=300,  # segundos -- Supavisor já fecha conexões ociosas por conta própria
            configure=_desligar_prepared_statements,
            open=True,
        )
    return _pool


def read_sql_query(
    conn: psycopg.Connection,
    query: str,
    params: tuple | None = None,
    parse_dates: list[str] | None = None,
) -> pd.DataFrame:
    """Substitui `pd.read_sql_query(query, conn, parse_dates=...)` para
    conexões psycopg3 -- mesma assinatura relevante, drop-in.

    Achado real de auditoria: pandas não reconhece `psycopg.Connection`
    como um dos backends que sabe tratar de verdade (não é
    `sqlite3.Connection`, nem SQLAlchemy, nem ADBC) -- cai num fallback
    que emite `UserWarning` ("Other DBAPI2 objects are not tested") e
    envolve a conexão com tratamento de erro pensado pra `sqlite3.Error`,
    que não captura nenhuma falha real do Postgres (deadlock, timeout,
    erro de sintaxe passam direto sem o rollback/wrap que o pandas
    tentaria fazer). Buscar via cursor nativo do psycopg evita esse
    caminho por inteiro, sem precisar adotar SQLAlchemy só pra isso."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        columns = [desc.name for desc in cur.description] if cur.description else []
    df = pd.DataFrame(rows, columns=columns)
    for col in parse_dates or []:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


@contextmanager
def scoped_transaction(user_id: str) -> Iterator[psycopg.Connection]:
    """Uma conexão (emprestada do pool) + transação únicas para um
    request inteiro, já autenticada como `user_id`. Todo repository deve
    receber essa `conn` (nunca abrir a própria) e nunca chamar
    commit()/close() nela — quem entra no `with` é dono do ciclo de vida:
    commita no fim se não houve exceção, faz rollback se houve, sempre
    devolve a conexão pro pool (nunca fecha de verdade)."""
    with _get_pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL role authenticated")
                cur.execute(
                    "SELECT set_config('request.jwt.claims', %s, true)",
                    (json.dumps({"sub": user_id, "role": "authenticated"}),),
                )
            yield conn
