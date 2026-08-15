"""
sifp/services/supabase_admin_service.py
------------------------------------------
Integração com a Admin API do Supabase Auth -- usada exclusivamente pelo
recurso de assessor (Fase 4, `routes_saas.py::convidar_cliente`): quando
um assessor convida um e-mail que ainda NÃO é usuário do Sifra, alguém
precisa criar a conta e mandar o convite por e-mail -- sem isso, o
convite fica pendente pra sempre (client_id nunca é reivindicado, porque
ninguém nunca loga com esse e-mail).

Pra e-mails que JÁ são usuários Sifra, isso é um no-op silencioso -- o
vínculo em `advisor_links` já foi salvo antes desta chamada (ver
AdvisorLinkRepository.convidar) e o mecanismo de "claim on login"
(claim_pending) já cobre esse caso sozinho, sem precisar da Admin API.
Por isso essa função é chamada como efeito colateral best-effort, DEPOIS
do vínculo já estar gravado -- uma falha aqui (rede, SMTP não
configurado, etc.) nunca deve derrubar a rota de convite.

`POST /auth/v1/invite` (não `/admin/invite`, que não existe -- confirmado
rodando contra a API real desta sessão, não assumido de memória de
treinamento) cria o usuário no estado "convidado" e dispara o e-mail de
convite padrão do Supabase (mesmo fluxo que já é tratado no
`/auth/confirm` do frontend). O segredo `service_role` nunca deve sair
do backend -- não logar, não devolver em resposta de API.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

__all__ = ["convidar_conta_nova"]


def convidar_conta_nova(email: str) -> None:
    """Best-effort: nunca levanta exceção. `email_exists` (422) é o
    caminho esperado pra quem já é usuário Sifra -- o vínculo pendente em
    advisor_links não depende deste resultado, então não é tratado como
    falha. Qualquer outro erro (chave ausente, rede, resposta
    inesperada) é logado como aviso, não propagado."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.warning(
            "SUPABASE_SERVICE_ROLE_KEY não configurada -- convite de conta nova não enviado (%s).", email
        )
        return

    try:
        resp = httpx.post(
            f"{SUPABASE_URL}/auth/v1/invite",
            json={"email": email},
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            },
            timeout=10.0,
        )
    except httpx.HTTPError:
        logger.exception("Falha de rede ao chamar a Admin API do Supabase pra convidar %s.", email)
        return

    if resp.status_code == 200:
        return

    try:
        corpo = resp.json()
    except ValueError:
        corpo = {}
    if resp.status_code == 422 and corpo.get("error_code") == "email_exists":
        return

    logger.warning(
        "Admin API do Supabase devolveu %s ao tentar convidar %s: %s", resp.status_code, email, resp.text
    )
