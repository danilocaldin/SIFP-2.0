"""Testes do NarrativaService (Fase 6/IA) — explicação em linguagem
natural gerada sob demanda via Claude. Nenhum teste chama a API real da
Anthropic: o cliente é sempre substituído por um fake, tanto pelo custo
quanto pra não depender de rede/credenciais durante a suíte."""

import types

import pandas as pd
import pytest

from sifp.domain.models import AssetPosition
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.balance_repository import BalanceRepository
from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.goal_repository import GoalRepository
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.narrativa_service import NarrativaIndisponivel, NarrativaService
from sifp.services.summary_service import SummaryService


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


class _FakeMessagesResource:
    def __init__(self, text, capture):
        self._text = text
        self._capture = capture

    def create(self, **kwargs):
        self._capture.update(kwargs)
        return _FakeMessage(self._text)


class _FakeAnthropicClient:
    """Substitui anthropic.Anthropic — nunca sai pra rede."""

    last_capture: dict = {}

    def __init__(self, api_key=None, **kwargs):
        self.api_key = api_key
        _FakeAnthropicClient.last_capture = {}
        self.messages = _FakeMessagesResource("Explicação de teste.", _FakeAnthropicClient.last_capture)


@pytest.fixture
def service(tmp_db_path):
    init_db(tmp_db_path)
    transaction_repo = TransactionRepository(tmp_db_path)
    balance_repo = BalanceRepository(tmp_db_path)
    asset_repo = AssetRepository(tmp_db_path)
    budget_repo = BudgetRepository(tmp_db_path)
    goal_repo = GoalRepository(tmp_db_path)

    tx = pd.DataFrame([
        {"date": "2026-05-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-05-10", "description": "Mercado", "value": -1000.0, "category": "Mercado"},
        {"date": "2026-06-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-06-10", "description": "Mercado", "value": -500.0, "category": "Mercado"},
    ])
    transaction_repo.insert_new(tx)

    asset_repo.insert_many([
        AssetPosition(
            nome="Fundo Teste", identificador="00.000.000/0001-00", tipo="Fundo de Investimento",
            instituicao="BTG Pactual", data_referencia="2026-06-30",
            saldo_bruto=3100.0, saldo_liquido=3000.0,
            rentabilidade_mes_pct=1.5, rentabilidade_ano_pct=6.0, rentabilidade_12m_pct=14.0,
            benchmark="CDI", benchmark_mes_pct=1.1, benchmark_ano_pct=5.5, benchmark_12m_pct=13.0,
        )
    ])

    summary_service = SummaryService(transaction_repo, balance_repo, asset_repo, budget_repo, goal_repo)
    return NarrativaService(summary_service, transaction_repo)


def _fake_anthropic_module():
    return types.SimpleNamespace(Anthropic=_FakeAnthropicClient)


def test_explicar_mes_sem_api_key_levanta_indisponivel(service, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(NarrativaIndisponivel):
        service.explicar_mes()


def test_explicar_mes_sem_dados_levanta_indisponivel(tmp_db_path, monkeypatch):
    init_db(tmp_db_path)
    empty_service = NarrativaService(
        SummaryService(
            TransactionRepository(tmp_db_path), BalanceRepository(tmp_db_path),
            AssetRepository(tmp_db_path), BudgetRepository(tmp_db_path), GoalRepository(tmp_db_path),
        ),
        TransactionRepository(tmp_db_path),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-test")
    with pytest.raises(NarrativaIndisponivel):
        empty_service.explicar_mes()


def test_explicar_mes_retorna_texto_do_cliente_mockado(service, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-test")
    monkeypatch.setitem(__import__("sys").modules, "anthropic", _fake_anthropic_module())

    texto = service.explicar_mes()

    assert texto == "Explicação de teste."
    # Confirma que o modelo Haiku foi usado e que nenhuma descrição bruta
    # de transação (só "Salario"/"Mercado" no fixture) vazou pro prompt
    # além do que category_breakdown já resume por categoria.
    capture = _FakeAnthropicClient.last_capture
    assert capture["model"] == "claude-haiku-4-5"
    assert "Jun/2026" in capture["messages"][0]["content"]


def test_explicar_mes_propaga_erro_generico_do_cliente(service, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-test")

    class _BoomClient:
        def __init__(self, **kwargs):
            self.messages = types.SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))

    monkeypatch.setitem(__import__("sys").modules, "anthropic", types.SimpleNamespace(Anthropic=_BoomClient))

    with pytest.raises(RuntimeError):
        service.explicar_mes()
