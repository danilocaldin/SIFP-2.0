"""Testes do ChatService (Fase 6/IA) — perguntas livres via tool use.
Nenhum teste chama a API real da Anthropic: o cliente é sempre um fake.
As tools em si (funções decoradas com @beta_tool) são testadas chamando-as
diretamente — o decorator não faz rede, só anota metadata, então a função
continua chamável como uma função Python normal."""

import json
import types

import pandas as pd
import pytest

from sifp.domain.models import AssetPosition
from sifp.repositories.asset_repository import AssetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.transaction_repository import TransactionRepository
from sifp.services.chat_service import ChatIndisponivel, ChatService


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


class _FakeToolRunner:
    def __init__(self, text):
        self._text = text

    def __iter__(self):
        yield _FakeMessage(self._text)


class _FakeBetaMessages:
    def __init__(self, text, capture):
        self._text = text
        self._capture = capture

    def tool_runner(self, **kwargs):
        self._capture.update(kwargs)
        return _FakeToolRunner(self._text)


class _FakeBeta:
    def __init__(self, text, capture):
        self.messages = _FakeBetaMessages(text, capture)


class _FakeAnthropicClient:
    last_capture: dict = {}

    def __init__(self, api_key=None, **kwargs):
        self.api_key = api_key
        _FakeAnthropicClient.last_capture = {}
        self.beta = _FakeBeta("Resposta de teste.", _FakeAnthropicClient.last_capture)


@pytest.fixture
def service(tmp_db_path):
    init_db(tmp_db_path)
    transaction_repo = TransactionRepository(tmp_db_path)
    asset_repo = AssetRepository(tmp_db_path)

    tx = pd.DataFrame([
        {"date": "2026-05-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-05-10", "description": "Uber Trip", "value": -35.0, "category": "Transporte"},
        {"date": "2026-06-05", "description": "Salario", "value": 5000.0, "category": "Salário/Receita"},
        {"date": "2026-06-10", "description": "Uber Trip", "value": -42.0, "category": "Transporte"},
        {"date": "2026-06-15", "description": "Mercado Extra", "value": -300.0, "category": "Mercado"},
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

    return ChatService(transaction_repo, asset_repo)


def _tool(service, all_tx, nome):
    """Devolve a tool já embrulhada para decodificar o JSON que ela
    retorna — o Tool Runner exige que toda tool devolva string (ou lista
    de content blocks), nunca um dict/list Python cru, então as tools
    reais fazem json.dumps() internamente."""
    tools = service._montar_tools(all_tx)
    tool = next(t for t in tools if t.name == nome)
    return lambda *args, **kwargs: json.loads(tool(*args, **kwargs))


def test_responder_sem_api_key_levanta_indisponivel(service, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ChatIndisponivel):
        service.responder([{"role": "user", "content": "oi"}])


def test_responder_sem_dados_levanta_indisponivel(tmp_db_path, monkeypatch):
    init_db(tmp_db_path)
    empty_service = ChatService(TransactionRepository(tmp_db_path), AssetRepository(tmp_db_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-test")
    with pytest.raises(ChatIndisponivel):
        empty_service.responder([{"role": "user", "content": "oi"}])


def test_responder_retorna_texto_do_cliente_mockado(service, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-test")
    fake_module = types.SimpleNamespace(Anthropic=_FakeAnthropicClient, beta_tool=lambda fn: fn)
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_module)

    resposta = service.responder([{"role": "user", "content": "quanto gastei com uber?"}])

    assert resposta == "Resposta de teste."
    capture = _FakeAnthropicClient.last_capture
    assert capture["model"] == "claude-haiku-4-5"
    assert len(capture["tools"]) == 4
    assert capture["messages"] == [{"role": "user", "content": "quanto gastei com uber?"}]


def test_tool_buscar_transacoes_filtra_por_descricao(service):
    all_tx = service._dados_base()
    tool = _tool(service, all_tx, "buscar_transacoes")

    resultado = tool(descricao_contem="uber")

    assert resultado["quantidade"] == 2
    assert resultado["total_despesas"] == pytest.approx(77.0)
    assert len(resultado["transacoes_exemplo_mais_recentes"]) == 2
    # A viagem de junho (R$42) é maior que a de maio (R$35) -- confirma
    # que maior_despesa é calculado sobre TODO o filtro, não uma amostra.
    assert resultado["maior_despesa"]["valor"] == pytest.approx(-42.0)


def test_tool_buscar_transacoes_filtra_por_categoria_e_periodo(service):
    all_tx = service._dados_base()
    tool = _tool(service, all_tx, "buscar_transacoes")

    resultado = tool(categoria="Transporte", mes_inicio="2026-06", mes_fim="2026-06")

    assert resultado["quantidade"] == 1
    assert resultado["total_despesas"] == pytest.approx(42.0)


def test_tool_buscar_transacoes_maior_despesa_nao_e_limitada_pela_amostra(service):
    """Reproduz o bug real encontrado em produção: com mais transações do
    que o teto de exemplos, o maior gasto do período tem que continuar
    correto mesmo que ele não esteja entre as N mais recentes."""
    all_tx = service._dados_base()
    # Volume grande de transações pequenas e recentes, mais uma antiga cara.
    extras = [
        {"date": "2026-06-20", "description": f"Cafe {i}", "value": -5.0, "category": "Alimentação"}
        for i in range(20)
    ]
    extras.append({"date": "2026-05-01", "description": "Conserto do carro", "value": -900.0, "category": "Transporte"})
    df_extra = pd.DataFrame(extras)
    df_extra["date"] = pd.to_datetime(df_extra["date"])
    df_extra["month"] = df_extra["date"].dt.to_period("M").astype(str)
    all_tx_completo = pd.concat([all_tx, df_extra], ignore_index=True)

    tool = _tool(service, all_tx_completo, "buscar_transacoes")
    resultado = tool()

    assert resultado["maior_despesa"]["valor"] == pytest.approx(-900.0)
    assert resultado["maior_despesa"]["descricao"] == "Conserto do carro"


def test_tool_buscar_transacoes_sem_resultado(service):
    all_tx = service._dados_base()
    tool = _tool(service, all_tx, "buscar_transacoes")

    resultado = tool(descricao_contem="descricao que nao existe nunca")

    assert resultado == {
        "quantidade": 0, "total_despesas": 0.0, "total_receitas": 0.0,
        "maior_despesa": None, "maior_receita": None, "transacoes_exemplo_mais_recentes": [],
    }


def test_tool_resumo_periodo(service):
    all_tx = service._dados_base()
    tool = _tool(service, all_tx, "resumo_periodo")

    resultado = tool(mes_inicio="2026-06", mes_fim="2026-06")

    assert resultado["has_data"] is True
    assert resultado["receitas"] == pytest.approx(5000.0)
    assert resultado["despesas"] == pytest.approx(342.0)
    categorias = {c["categoria"] for c in resultado["por_categoria"]}
    assert categorias == {"Transporte", "Mercado"}


def test_tool_patrimonio_atual(service):
    all_tx = service._dados_base()
    tool = _tool(service, all_tx, "patrimonio_atual")

    resultado = tool()

    assert resultado["has_data"] is True
    assert resultado["patrimonio_total"] == pytest.approx(3000.0)
    assert resultado["ativos"][0]["nome"] == "Fundo Teste"


def test_tool_listar_categorias(service):
    all_tx = service._dados_base()
    tool = _tool(service, all_tx, "listar_categorias")

    resultado = tool()

    assert "Mercado" in resultado
    assert "Transporte" in resultado
