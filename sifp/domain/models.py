"""
domain/models.py
-----------------
Modelos de domínio do SIFP: os contratos de dados que atravessam as
camadas (importers -> intelligence -> services -> repositories -> UI).

Escolha deliberada: o PROCESSAMENTO em lote (parsing de extrato, aplicação
de regras de categorização, cálculo de indicadores) continua vetorizado em
pandas DataFrame/Series — é o jeito certo de processar milhares de linhas
em Python, e reescrever isso como loop de objetos por linha só pioraria
performance e legibilidade sem ganho real. Os dataclasses abaixo servem
como o CONTRATO (nomes de campo, tipos, categorias/fontes possíveis) usado
nas bordas: um resultado de categorização de UMA transação, um registro
para inserção unitária, etc.
"""

from dataclasses import dataclass
from enum import Enum


class CategorySource(str, Enum):
    """De onde veio a categoria sugerida — usado para explicar ao usuário
    ('Situação' na tela de Revisão) por que o sistema sugeriu algo, em vez
    de inferir isso indiretamente a partir do valor de confidence."""

    LEARNED_STABLE = "learned_stable"       # você sempre confirmou a mesma categoria pra essa descrição
    LEARNED_VARIABLE = "learned_variable"   # você já confirmou categorias diferentes -> força revisão
    SELF_TRANSFER = "self_transfer"         # transferência para você mesmo (detecção estrutural)
    KEYWORD_RULE = "keyword_rule"           # bateu uma regra de palavra-chave
    BANK_CATEGORY = "bank_category"         # categoria que o próprio banco sugeriu
    ML_MODEL = "ml_model"                   # modelo de machine learning
    HUMAN = "human"                         # usuário definiu manualmente na tela de Revisão
    NONE = "none"                           # nada bateu


@dataclass(frozen=True)
class CategorySuggestion:
    category: str
    confidence: float
    source: CategorySource


@dataclass(frozen=True)
class Transaction:
    """Uma movimentação financeira já normalizada (Módulo 2)."""

    date: str  # "YYYY-MM-DD" ou "YYYY-MM-DD HH:MM"
    description: str
    value: float
    bank_category: str = ""
    self_transfer: bool = False
    merchant: str = ""
    category: str = "Não categorizado"
    confidence: float = 0.0
    category_source: CategorySource = CategorySource.NONE
    source_file: str = ""
    institution: str = "BTG Pactual"


@dataclass(frozen=True)
class DailyBalance:
    date: str
    balance: float
    source_file: str = ""


@dataclass(frozen=True)
class AssetPosition:
    """Posição de um ativo (Módulo 6) numa data de referência — ex: o
    saldo de um fundo de investimento ao final do mês, extraído do
    extrato da conta investimento. Snapshot, não uma transação: várias
    posições do mesmo ativo em datas diferentes formam o histórico
    mensal (Módulo 8)."""

    nome: str                          # ex: "BTG CDB Plus FIRF CrPr"
    identificador: str                 # ex: CNPJ do fundo — chave de dedup entre snapshots
    tipo: str                          # ex: "Fundo de Investimento"
    instituicao: str
    data_referencia: str               # "YYYY-MM-DD"
    quantidade: float | None = None
    cotacao: float | None = None
    saldo_bruto: float = 0.0
    saldo_liquido: float = 0.0
    rentabilidade_mes_pct: float | None = None
    rentabilidade_ano_pct: float | None = None
    rentabilidade_12m_pct: float | None = None
    benchmark: str | None = None
    # Retorno do PRÓPRIO benchmark (ex: CDI) no mesmo período — sem isso
    # não dá pra comparar "o fundo rendeu X% acima/abaixo do benchmark",
    # só sabíamos o nome dele.
    benchmark_mes_pct: float | None = None
    benchmark_ano_pct: float | None = None
    benchmark_12m_pct: float | None = None
    source_file: str = ""


class DiagnosticSeverity(str, Enum):
    """Ordem crescente de gravidade — usada tanto para exibição (badge)
    quanto para ordenar por prioridade (mais grave primeiro)."""

    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


_SEVERITY_ORDER = {
    DiagnosticSeverity.CRITICA: 0,
    DiagnosticSeverity.ALTA: 1,
    DiagnosticSeverity.MEDIA: 2,
    DiagnosticSeverity.BAIXA: 3,
}


@dataclass(frozen=True)
class Diagnostic:
    """
    Um diagnóstico automático (Módulo 10): não é só um número, é uma
    LEITURA sobre um número — por isso carrega explicação e recomendação
    junto, não só o dado bruto (que já está nos indicadores do Módulo 9).

    Desenhado para ser a mesma "moeda" que futuros alertas de orçamento
    estourado e progresso de metas (Fase 3) vão usar — em vez de cada
    módulo novo inventar seu próprio formato de alerta.
    """

    codigo: str                     # identificador estável da regra, ex: "saldo_negativo_recorrente"
    titulo: str
    severidade: DiagnosticSeverity
    descricao: str                  # o que foi encontrado, com os números reais
    explicacao: str                 # por que isso importa
    recomendacao: str               # o que fazer a respeito
    impacto_financeiro: float | None = None  # R$, quando fizer sentido quantificar

    @property
    def prioridade(self) -> int:
        """Menor = mais prioritário. Usado só para ordenação (não é um
        campo persistido — é derivado da severidade)."""
        return _SEVERITY_ORDER[self.severidade]


@dataclass(frozen=True)
class Budget:
    """Limite de gasto mensal por categoria (Módulo 13). Uma linha por
    categoria — categoria sem linha aqui simplesmente não tem limite
    definido e não é monitorada."""

    category: str
    limite_mensal: float


@dataclass(frozen=True)
class Goal:
    """Meta financeira (Módulo 14) — reserva de emergência, viagem,
    entrada de imóvel etc. valor_acumulado é atualizado manualmente pelo
    usuário por enquanto (uma vinculação automática com o patrimônio é
    uma evolução possível, não necessária pro v1)."""

    id: int | None  # None antes de persistir; a repository preenche ao inserir
    nome: str
    valor_necessario: float
    valor_acumulado: float
    prazo: str  # "YYYY-MM-DD"

    @property
    def progresso_pct(self) -> float:
        if self.valor_necessario <= 0:
            return 0.0
        return min(self.valor_acumulado / self.valor_necessario * 100, 100.0)
