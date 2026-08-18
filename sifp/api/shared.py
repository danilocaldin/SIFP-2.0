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
import re
from datetime import datetime

from fastapi import HTTPException, UploadFile

from sifp.domain.categories import CATEGORIAS_PADRAO
from sifp.intelligence.categorization import CategorizationService

categorization_service = CategorizationService.load()

# Achado real de auditoria: nenhuma rota de upload checava tamanho —
# só a extensão do nome do arquivo. Um XLSX/PDF gigante (ou uma
# zip-bomb) era lido inteiro pra memória e podia derrubar o processo
# pra todos os clientes. 25MB é bem acima do maior extrato/PDF real de
# investimento visto em uso (esses ficam na casa de poucos MB).
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024


def validar_tamanho_upload(file: UploadFile) -> None:
    """Rejeita ANTES de ler o arquivo pra memória (as_file_like) ou
    passá-lo pro importer/pandas. `file.size` já reflete o tamanho real
    nesse ponto — o Starlette termina de bufferizar o multipart inteiro
    antes de chamar a rota, então isso não evita o upload em si, mas
    evita o segundo (e mais caro) carregamento inteiro em memória."""
    if file.size is not None and file.size > MAX_UPLOAD_SIZE_BYTES:
        limite_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413, detail=f"Arquivo muito grande. O limite é {limite_mb}MB."
        )


# Achado real de auditoria: /chat reenvia a conversa inteira a cada
# chamada (design stateless, sem sessão/histórico no servidor) sem
# nenhum cap de quantidade de mensagens nem de tamanho de conteúdo --
# um payload arbitrariamente grande é reprocessado e reenviado pra
# Anthropic a cada chamada, faturado direto na chave do Danilo.
MAX_CHAT_MENSAGENS = 60
MAX_CHAT_CONTEUDO_CHARS = 4000


def validar_mensagens_chat(cls, mensagens: list) -> list:
    """Validator reutilizável (Pydantic v2) pro campo `mensagens` de
    ChatIn, em main.py e routes_saas.py."""
    if len(mensagens) > MAX_CHAT_MENSAGENS:
        raise ValueError(f"Muitas mensagens na conversa (máximo {MAX_CHAT_MENSAGENS}).")
    for m in mensagens:
        if len(m.content) > MAX_CHAT_CONTEUDO_CHARS:
            raise ValueError(f"Mensagem muito longa (máximo {MAX_CHAT_CONTEUDO_CHARS} caracteres).")
    return mensagens


def validar_categoria(cls, v: str) -> str:
    """Validator reutilizável (Pydantic v2, `field_validator("...")(validar_categoria)`)
    pros DTOs que recebem uma categoria como texto livre (LimiteIn,
    DespesaFixaIn, RevisaoLoteIn, RevisaoUpdate, em main.py e
    routes_saas.py). Achado real de auditoria: sem essa checagem, uma
    categoria digitada errada (via chamada direta à API, não pela UI)
    ficava salva e quebrava qualquer agrupamento/breakdown por
    categoria — no app pessoal (main.py, ainda retreina) também virava
    rótulo permanente de treino do modelo de ML; no SaaS (routes_saas.py)
    esse segundo risco não existe mais desde que o retreino automático
    foi desligado (ver módulo shared.py acima), mas a validação continua
    necessária pelo primeiro motivo."""
    if v not in CATEGORIAS_PADRAO:
        raise ValueError(
            f"Categoria inválida. Use uma das categorias existentes: {', '.join(CATEGORIAS_PADRAO)}."
        )
    return v


def validar_data_iso(cls, v: str) -> str:
    """Validator reutilizável (Pydantic v2) pro campo `prazo` de GoalIn (em
    main.py e routes_saas.py). Achado real de auditoria: sem essa checagem,
    um prazo vazio ou mal formatado (ex: "" ou "31/13/2026", digitado via
    chamada direta à API) ficava salvo sem erro nenhum — e só quebrava
    depois, em /projecoes, onde pd.to_datetime(prazo) levanta DateParseError
    (texto não-data) ou vira NaT (string vazia), e NaT.strftime(...) levanta
    ValueError. Como não existe rota pra editar prazo/nome de uma meta já
    criada, isso derrubava /projecoes (e o gráfico de patrimônio) pra conta
    inteira até alguém identificar e apagar a meta problemática. Validar na
    criação rejeita com 400 amigável em vez de quebrar semanas depois."""
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except (ValueError, TypeError) as e:
        raise ValueError('Prazo inválido. Use o formato "AAAA-MM-DD".') from e
    return v


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_email(cls, v: str) -> str:
    """Validator reutilizável (Pydantic v2) pro campo `email` de
    ConviteAssessorIn (routes_saas.py, recurso de assessor). Normaliza pra
    minúsculo (e-mail não é case-sensitive na prática, e client_email
    precisa bater exatamente com o claim do JWT na hora de reivindicar o
    convite — ver advisor_link_repository.py::claim_pending) e rejeita
    formato claramente inválido antes de gravar."""
    v = v.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("E-mail inválido.")
    return v


def _digitos_verificadores_cpf(cpf: str) -> tuple[int, int]:
    """Algoritmo padrão de CPF (módulo 11) -- calcula os dois dígitos
    verificadores a partir dos 9 primeiros dígitos."""

    def _digito(base: str, pesos: range) -> int:
        soma = sum(int(d) * p for d, p in zip(base, pesos))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    primeiro = _digito(cpf[:9], range(10, 1, -1))
    segundo = _digito(cpf[:9] + str(primeiro), range(11, 1, -1))
    return primeiro, segundo


def validar_cpf(cls, v: str) -> str:
    """Validator reutilizável (Pydantic v2) pro campo `cpf` de CadastroIn
    (routes_saas.py, wizard de cadastro). Confere o dígito verificador de
    verdade (módulo 11), não só o formato -- um CPF com formato correto
    mas dígito errado (erro de digitação comum) ficaria salvo sem aviso
    nenhum, e o índice único de CPF (schema.sql) não pega esse tipo de
    erro, só duplicata exata."""
    digitos = re.sub(r"\D", "", v)
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        raise ValueError("CPF inválido.")
    primeiro, segundo = _digitos_verificadores_cpf(digitos)
    if digitos[9] != str(primeiro) or digitos[10] != str(segundo):
        raise ValueError("CPF inválido.")
    return digitos


_TELEFONE_RE = re.compile(r"^\d{2}9?\d{8}$")


def validar_telefone(cls, v: str) -> str:
    """Validator reutilizável (Pydantic v2) pro campo `telefone` de
    CadastroIn. Aceita qualquer pontuação (parênteses, espaço, traço) na
    entrada e normaliza pra só dígitos -- DDD (2) + 8 ou 9 dígitos."""
    digitos = re.sub(r"\D", "", v)
    if not _TELEFONE_RE.match(digitos):
        raise ValueError("Telefone inválido. Use o formato (DDD) 9XXXX-XXXX.")
    return digitos


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
