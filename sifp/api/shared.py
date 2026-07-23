"""
sifp/api/shared.py
--------------------
Estado de processo compartilhado entre a API single-tenant (main.py) e as
rotas multiusuário do SaaS (routes_saas.py) — existe só pra essas duas
partes não acabarem com DUAS instâncias separadas do mesmo singleton.

O caso concreto que isso evita: CategorizationService.train() atualiza
self.model em memória E grava em disco (categorizer_model.joblib). Se cada
módulo carregasse a própria instância, um retreino disparado por um
usuário do SaaS não apareceria pro Streamlit (ou vice-versa) até o
processo reiniciar — inconsistência silenciosa. Com uma instância só,
qualquer retreino (de qualquer origem) atualiza o mesmo objeto em memória
pros dois caminhos.

O modelo de categorização em si é deliberadamente global (não por
usuário/tenant) — é sugestão de categoria, não dado financeiro sensível
(ver memória project_sifp_multiuser_scaling).
"""

import io

from fastapi import UploadFile

from sifp.intelligence.categorization import CategorizationService

categorization_service = CategorizationService.load()


def as_file_like(file: UploadFile) -> io.BytesIO:
    """Importers/ImportService esperam um arquivo com `.name` (mesma
    interface do UploadedFile do Streamlit) pra decidir o parser pela
    extensão — UploadFile.file (SpooledTemporaryFile) não garante isso."""
    file_like = io.BytesIO(file.file.read())
    file_like.name = file.filename or ""
    return file_like


def transactions_payload(df) -> list[dict]:
    """Sanitiza tipos numpy (bool_/float64) que o encoder JSON do FastAPI
    não serializa nativamente, antes de devolver linhas de transação."""
    records = df.to_dict("records")
    for r in records:
        r["value"] = float(r["value"])
        r["self_transfer"] = bool(r["self_transfer"])
    return records
