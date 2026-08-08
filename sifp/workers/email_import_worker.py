"""
sifp/workers/email_import_worker.py
--------------------------------------
Job agendado (Módulo 18 — importação automática por e-mail, SaaS only)
que lê uma caixa de e-mail dedicada, identifica de quem é cada extrato
encaminhado pelo endereço "+token" usado, e importa pelo MESMO
ImportService/PatrimonioService que o upload manual já usa — nenhuma
lógica de parsing nova, só um jeito novo do arquivo chegar até o sistema.

Roda uma vez por execução (não é um loop infinito): busca e-mails não
lidos, processa, marca como lidos, termina. O agendamento (a cada N
minutos) é responsabilidade do cron da Railway, não deste script.

Rodar manualmente com:
    python -m sifp.workers.email_import_worker
"""

from __future__ import annotations

import email
import imaplib
import io
import logging
import os
import re
from email.message import Message
from email.utils import parseaddr

import psycopg
from dotenv import load_dotenv

load_dotenv()

from sifp.api.shared import MAX_UPLOAD_SIZE_BYTES, categorization_service
from sifp.importers.btg_importer import BTGImporter
from sifp.importers.btg_investment_importer import BTGInvestmentImporter
from sifp.repositories.pg.asset_repository import AssetRepository
from sifp.repositories.pg.balance_repository import BalanceRepository
from sifp.repositories.pg.bound import ConnBound
from sifp.repositories.pg.connection import DATABASE_URL, scoped_transaction
from sifp.repositories.pg.transaction_repository import TransactionRepository
from sifp.services.import_service import ImportService
from sifp.services.patrimonio_service import PatrimonioService

logger = logging.getLogger(__name__)

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))

# Endereço usado pelo remetente aparece com o "+token" no header que o
# NOSSO servidor de recebimento grava (não o do remetente) — funciona
# tanto pra um encaminhamento manual (um clique) quanto pra uma regra de
# encaminhamento automático configurada no provedor do usuário, porque em
# ambos os casos é o servidor que recebe (nossa caixa) que registra o
# endereço de entrega de verdade.
_TOKEN_RE = re.compile(r"\+([a-zA-Z0-9_-]+)@")


def _extract_token(msg: Message) -> str | None:
    for header in ("Delivered-To", "X-Original-To", "To", "Cc"):
        for value in msg.get_all(header, []):
            m = _TOKEN_RE.search(value)
            if m:
                return m.group(1)
    return None


def _lookup_user_id(conn: psycopg.Connection, token: str) -> str | None:
    """Consulta direta, sem escopo de usuário (bypassa RLS de propósito —
    ver comentário em pg/schema.sql sobre import_aliases): é o único jeito
    de mapear "token" -> "de quem é" antes de sabermos quem é o usuário."""
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM import_aliases WHERE token = %s", (token,))
    row = cur.fetchone()
    return str(row[0]) if row else None


def _extract_sender(msg: Message) -> str:
    """E-mail de quem enviou (só o endereço, sem nome de exibição)."""
    _, addr = parseaddr(msg.get("From", ""))
    return addr.strip().lower()


def _remetente_confiavel(conn: psycopg.Connection, token: str) -> str | None:
    cur = conn.cursor()
    cur.execute("SELECT remetente_confiavel FROM import_aliases WHERE token = %s", (token,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def _registrar_remetente_confiavel(conn: psycopg.Connection, token: str, remetente: str) -> None:
    conn.cursor().execute(
        "UPDATE import_aliases SET remetente_confiavel = %s WHERE token = %s", (remetente, token)
    )
    conn.commit()


def _extract_attachments(msg: Message) -> list[tuple[str, bytes]]:
    """Achado real de auditoria: nenhum limite de tamanho de anexo --
    um anexo gigante (ou uma zip-bomb) era decodificado inteiro pra
    memória, mesmo risco já corrigido pro upload manual (ver
    validar_tamanho_upload em sifp/api/shared.py). Mesmo limite aqui."""
    attachments = []
    for part in msg.walk():
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        if len(payload) > MAX_UPLOAD_SIZE_BYTES:
            limite_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            logger.warning(
                "Anexo '%s' ignorado: %d bytes acima do limite de %dMB.",
                filename, len(payload), limite_mb,
            )
            continue
        attachments.append((filename, payload))
    return attachments


def _import_for_user(user_id: str, filename: str, raw: bytes) -> str:
    file_like = io.BytesIO(raw)
    file_like.name = filename

    with scoped_transaction(user_id) as conn:
        if BTGInvestmentImporter().supports(filename):
            asset_repo = ConnBound(AssetRepository(), conn)
            patrimonio_service = PatrimonioService(asset_repo, BTGInvestmentImporter())
            n = patrimonio_service.import_pdf(file_like)
            return f"{n} posição(ões) de investimento importada(s)"

        if BTGImporter().supports(filename):
            transaction_repo = ConnBound(TransactionRepository(), conn)
            balance_repo = ConnBound(BalanceRepository(), conn)
            import_service = ImportService(
                importers=[BTGImporter()],
                categorization=categorization_service,
                transaction_repo=transaction_repo,
                balance_repo=balance_repo,
            )
            summary = import_service.import_and_persist(file_like)
            return f"{summary['inseridas']} transação(ões) inserida(s)"

    return "arquivo não reconhecido (ignorado)"


def run() -> None:
    if not DATABASE_URL:
        logger.error("SUPABASE_DB_URL não configurada — abortando.")
        return

    imap_user = os.environ.get("IMAP_USER")
    imap_password = os.environ.get("IMAP_APP_PASSWORD")
    if not imap_user or not imap_password:
        logger.error("IMAP_USER/IMAP_APP_PASSWORD não configuradas — abortando.")
        return

    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    imap.login(imap_user, imap_password)
    imap.select("INBOX")

    status, data = imap.search(None, "UNSEEN")
    if status != "OK":
        logger.error("Falha ao buscar e-mails não lidos.")
        imap.logout()
        return

    ids = data[0].split()
    logger.info("%d e-mail(s) não lido(s) encontrado(s).", len(ids))

    lookup_conn = psycopg.connect(DATABASE_URL)
    try:
        for msg_id in ids:
            status, msg_data = imap.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            label = msg_id.decode()

            token = _extract_token(msg)
            if not token:
                logger.warning("[%s] sem token identificável — ignorado.", label)
                imap.store(msg_id, "+FLAGS", "\\Seen")
                continue

            user_id = _lookup_user_id(lookup_conn, token)
            if not user_id:
                logger.warning("[%s] token '%s' não corresponde a nenhum usuário — ignorado.", label, token)
                imap.store(msg_id, "+FLAGS", "\\Seen")
                continue

            remetente = _extract_sender(msg)
            confiavel = _remetente_confiavel(lookup_conn, token)
            if confiavel is None:
                # Primeiro e-mail que chega nesse alias -- "confiar no
                # primeiro uso": registra esse remetente como o único
                # aceito daqui pra frente pra esse token.
                if remetente:
                    _registrar_remetente_confiavel(lookup_conn, token, remetente)
                    logger.info(
                        "[%s] usuário %s: remetente '%s' registrado como confiável pra esse alias.",
                        label, user_id, remetente,
                    )
            elif remetente != confiavel:
                logger.warning(
                    "[%s] usuário %s: remetente '%s' não é o remetente confiável ('%s') "
                    "desse alias — ignorado por segurança.",
                    label, user_id, remetente, confiavel,
                )
                imap.store(msg_id, "+FLAGS", "\\Seen")
                continue

            attachments = _extract_attachments(msg)
            if not attachments:
                logger.warning("[%s] token '%s' reconhecido, mas sem anexo — ignorado.", label, token)
                imap.store(msg_id, "+FLAGS", "\\Seen")
                continue

            for filename, raw in attachments:
                try:
                    resultado = _import_for_user(user_id, filename, raw)
                    logger.info("[%s] usuário %s: %s -> %s", label, user_id, filename, resultado)
                except Exception:
                    logger.exception("[%s] usuário %s: erro ao importar '%s'", label, user_id, filename)

            imap.store(msg_id, "+FLAGS", "\\Seen")
    finally:
        lookup_conn.close()
        imap.logout()


if __name__ == "__main__":
    # Sem isso, logger.info() não vai pra lugar nenhum: sem handler
    # configurado, o Python só emite WARNING+ por padrão (o "handler de
    # último recurso"), e esse worker roda como processo standalone
    # (cron da Railway), não dentro do Uvicorn -- não herda config de
    # logging de mais ninguém.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
