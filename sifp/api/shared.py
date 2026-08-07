"""
sifp/api/shared.py
--------------------
Estado de processo compartilhado entre a API single-tenant (main.py) e as
rotas multiusuário do SaaS (routes_saas.py) — existe só pra essas duas
partes não acabarem com DUAS instâncias separadas do mesmo singleton.

O caso concreto que isso evita: CategorizationService.train() atualiza
self.model em memória E grava em disco (categorizer_model.joblib). Se cada
módulo carregasse a própria instância, um retreino disparado pelo app
pessoal não apareceria em routes_saas.py (ou vice-versa) até o processo
reiniciar — inconsistência silenciosa.

O modelo é global (não por usuário/tenant) por design, mas isso só é
seguro no app pessoal (single-tenant, um usuário só). No SaaS,
routes_saas.py::_refresh_model() está deliberadamente DESLIGADO (não
chama .train()) — treinar esse modelo único com dados de um cliente
sobrescreveria o modelo global usado nas sugestões de todos os outros, e
o vetorizador TF-IDF guarda n-gramas literais de descrições reais (nome
de contraparte de Pix, por exemplo), que é dado pessoal de terceiro. Um
modelo por tenant é o caminho de médio prazo; até lá, as camadas 0-3 de
categorização (memória por descrição, self-transfer, palavra-chave,
categoria do banco) são por usuário via RLS e cobrem a maior parte dos
casos sem precisar do ML.
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
