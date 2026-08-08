"""
sifp/api/rate_limit.py
------------------------
Rate limiting simples por usuário, em memória de processo -- primeiro
corte pra limitar o gasto de /chat, /narrativa, upload e PDF por conta.

Melhoria viável da 3ª varredura: nada limitava essas rotas, e com o
SaaS onboardando clientes reais (não só o uso pessoal do Danilo), isso
é gasto direto e ilimitado na chave da Anthropic por conta autenticada
(/chat, /narrativa) e trabalho de CPU/banco sem teto (upload, geração
de PDF).

Em memória de propósito: sem dependência nova pra instalar, sem
backend compartilhado pra configurar. Limitação conhecida: não é
distribuído -- não sobrevive reinício do processo, e não é
compartilhado entre múltiplas réplicas se o serviço um dia escalar
horizontalmente. Suficiente pro volume atual; revisitar com um backend
compartilhado (Redis, ou uma tabela no próprio Postgres) se isso virar
gargalo real.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Depends, HTTPException

from sifp.api.auth import get_current_user_id

_hits: dict[str, deque[float]] = defaultdict(deque)


def _checar_limite(chave: str, max_chamadas: int, janela_segundos: float) -> None:
    agora = time.monotonic()
    hits = _hits[chave]
    while hits and agora - hits[0] > janela_segundos:
        hits.popleft()
    if len(hits) >= max_chamadas:
        raise HTTPException(
            status_code=429,
            detail="Muitas requisições em pouco tempo. Aguarde um instante e tente de novo.",
        )
    hits.append(agora)


def rate_limiter(prefixo: str, max_chamadas: int, janela_segundos: float) -> Callable[..., None]:
    """Fábrica de dependency do FastAPI, uma por rota/limite. Uso:

        @router.post("/chat", dependencies=[Depends(rate_limiter("chat", 20, 60))])

    Cada usuário tem seu próprio contador (chave = f"{prefixo}:{user_id}"),
    então o limite de uma conta nunca afeta outra."""

    def _dependency(user_id: str = Depends(get_current_user_id)) -> None:
        _checar_limite(f"{prefixo}:{user_id}", max_chamadas, janela_segundos)

    return _dependency
