"""Testes de sifp/api/shared.py — helpers compartilhados entre main.py e
routes_saas.py."""

import pytest
from fastapi import HTTPException

from sifp.api.shared import MAX_UPLOAD_SIZE_BYTES, validar_tamanho_upload


class _FakeUploadFile:
    def __init__(self, size):
        self.size = size


def test_validar_tamanho_upload_aceita_arquivo_dentro_do_limite():
    validar_tamanho_upload(_FakeUploadFile(MAX_UPLOAD_SIZE_BYTES))  # não levanta


def test_validar_tamanho_upload_rejeita_arquivo_acima_do_limite():
    """Achado real de auditoria: nenhuma rota de upload checava tamanho,
    só a extensão do nome do arquivo -- um arquivo gigante era lido
    inteiro pra memória antes de qualquer validação."""
    with pytest.raises(HTTPException) as exc_info:
        validar_tamanho_upload(_FakeUploadFile(MAX_UPLOAD_SIZE_BYTES + 1))
    assert exc_info.value.status_code == 413


def test_validar_tamanho_upload_sem_size_conhecido_nao_bloqueia():
    """Alguns servidores ASGI podem não expor .size -- sem informação,
    não há como bloquear aqui (o importer ainda valida o conteúdo)."""
    validar_tamanho_upload(_FakeUploadFile(None))  # não levanta
