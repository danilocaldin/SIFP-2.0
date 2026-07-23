"""
sifp/repositories/pg/bound.py
--------------------------------
Adaptador que faz os repositories Postgres (que exigem `conn` explícita em
todo método — ver connection.py) parecerem, pro resto do sistema, com os
repositories SQLite de sempre (`repo.get_all()`, sem parâmetro de conexão).

Por quê: TODA a camada de services (sifp/services/*.py) já espera essa
interface sem conexão — foi assim que o Streamlit sempre usou. Reescrever
cada service pra passar `conn` explicitamente em toda chamada duplicaria
lógica de negócio só por causa de um detalhe de infraestrutura. Em vez
disso, cada request do SaaS cria um ConnBound por repository (ver
sifp/api/routes_saas.py) e passa esses objetos pros MESMOS construtores de
service que a API single-tenant já usa — nenhuma linha de services/ muda.

Puramente mecânico: encaminha qualquer chamada de método, injetando `conn`
como primeiro argumento. Nenhuma lógica própria.
"""

from __future__ import annotations

from typing import Any


class ConnBound:
    def __init__(self, repo: Any, conn: Any):
        self._repo = repo
        self._conn = conn

    def __getattr__(self, name: str):
        attr = getattr(self._repo, name)
        if not callable(attr):
            return attr

        def bound_method(*args, **kwargs):
            return attr(self._conn, *args, **kwargs)

        return bound_method
