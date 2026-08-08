"""
Testes do CategorizationService — cobrem a ordem de precedência das
cinco camadas e a regressão do bug de acentuação nas regras de
palavra-chave (uma regra sem acento não batia com texto acentuado real
do BTG, ex: "TRANSFERENCIA" vs "Transferência").
"""

import pandas as pd
import pytest

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO, SELF_TRANSFER_CATEGORY
from sifp.domain.models import CategorySource
from sifp.importers.br_format_utils import normalize_description_key
from sifp.intelligence.categorization import CategorizationService, apply_keyword_rules, is_pix_or_transfer


@pytest.fixture
def service():
    return CategorizationService(model=None)


def test_keyword_rule_matches_accented_real_world_text():
    # "Transferência" (acentuado) precisa bater com a regra "TRANSFERENCIA" (sem acento)
    assert apply_keyword_rules("Pix enviado - Maria Jose Vieira") == "Transferências"
    assert apply_keyword_rules("Compra no débito autorizada - Uber") == "Transporte"


def test_no_rule_match_returns_none():
    assert apply_keyword_rules("Lançamento totalmente desconhecido XYZ") is None


def test_keyword_rule_respeita_limite_de_palavra_amil_dentro_de_familia():
    # "AMIL" (Saúde) não pode casar dentro de "FAMILIA"
    assert apply_keyword_rules("Pix enviado - Familia Silva") != "Saúde"
    assert apply_keyword_rules("Compra no débito autorizada - Amil Saude") == "Saúde"


def test_keyword_rule_respeita_limite_de_palavra_metro_dentro_de_metropole():
    # "METRO" (Transporte) não pode casar dentro de "METROPOLE OTICAS"
    assert apply_keyword_rules("Compra no débito autorizada - Metropole Oticas") != "Transporte"
    assert apply_keyword_rules("Compra no débito autorizada - Metro Sp") == "Transporte"


def test_keyword_rule_respeita_limite_de_palavra_curso_dentro_de_concurso_recursos():
    # "CURSO" (Educação) não pode casar dentro de "CONCURSO" ou "RECURSOS"
    assert apply_keyword_rules("Compra no débito autorizada - Concurso Publico Edital") != "Educação"
    assert apply_keyword_rules("Pix enviado - Recursos Humanos Ltda") != "Educação"
    assert apply_keyword_rules("Compra no débito autorizada - Curso Ingles") == "Educação"


def test_keyword_rule_termo_mais_especifico_vence_mercado_livre_vs_mercado():
    # "MERCADO LIVRE" (Compras) precisa vencer "MERCADO" (Mercado) --
    # mesmo "Mercado" vindo antes no dicionário, o termo mais específico
    # (mais longo) é o que decide.
    assert apply_keyword_rules("Compra no débito autorizada - Mercado Livre*Camiseta") == "Compras"
    assert apply_keyword_rules("Compra no débito autorizada - Mercado Sao Jose") == "Mercado"


def test_precedence_keyword_rule_beats_bank_category(service):
    result = service.predict("Compra no débito autorizada - Uber", bank_category="Outra Categoria")
    assert result.category == "Transporte"
    assert result.source == CategorySource.KEYWORD_RULE


def test_precedence_bank_category_used_when_no_rule_matches(service):
    result = service.predict("Estabelecimento Sem Regra Nenhuma", bank_category="Cuidados Pessoais")
    assert result.category == "Cuidados Pessoais"
    assert result.source == CategorySource.BANK_CATEGORY


def test_precedence_self_transfer_beats_keyword_and_bank_category(service):
    result = service.predict(
        "Transferência enviada - Fulano De Tal",
        bank_category="Transferência",
        self_transfer=True,
    )
    assert result.category == SELF_TRANSFER_CATEGORY
    assert result.source == CategorySource.SELF_TRANSFER


def test_precedence_learned_stable_beats_everything(service):
    """Usuário sempre confirmou um Netflix específico como 'Lazer' — deve
    vencer até a regra padrão do sistema (que diria 'Assinaturas')."""
    descricao = "Compra no débito autorizada - Netflix"
    learned_map = {
        normalize_description_key(descricao): {
            "category": "Lazer", "variable": False, "history": [("Lazer", 3)],
        }
    }
    result = service.predict(descricao, bank_category=None, learned_map=learned_map)
    assert result.category == "Lazer"
    assert result.source == CategorySource.LEARNED_STABLE


def test_precedence_learned_stable_ignora_diferenca_de_acento_e_caixa(service):
    """Achado real de auditoria: a mesma contraparte formatada diferente
    entre extratos ("Compra ... Netflix" vs "COMPRA ... NETFLIX") tinha
    que continuar reconhecendo a categoria já confirmada."""
    learned_map = {
        normalize_description_key("Compra no débito autorizada - Netflix"): {
            "category": "Lazer", "variable": False, "history": [("Lazer", 3)],
        }
    }
    result = service.predict(
        "COMPRA NO DEBITO AUTORIZADA - NETFLIX", bank_category=None, learned_map=learned_map
    )
    assert result.category == "Lazer"
    assert result.source == CategorySource.LEARNED_STABLE


def test_precedence_learned_variable_forces_review(service):
    """Descrição com histórico de categorias diferentes -> sempre
    'Não categorizado', mesmo que uma regra bateria."""
    descricao = "Pix enviado - Maria Jose Vieira"
    learned_map = {
        normalize_description_key(descricao): {
            "category": None, "variable": True, "history": [("Moradia", 2), ("Lazer", 1)],
        }
    }
    result = service.predict(descricao, bank_category=None, learned_map=learned_map)
    assert result.category == CATEGORIA_NAO_CATEGORIZADO
    assert result.confidence == 0.0
    assert result.source == CategorySource.LEARNED_VARIABLE


def test_no_signal_falls_back_to_nao_categorizado(service):
    result = service.predict("Lançamento nunca visto antes XPTO")
    assert result.category == CATEGORIA_NAO_CATEGORIZADO
    assert result.source == CategorySource.NONE


def test_predict_batch_matches_predict_row_by_row(service):
    descriptions = pd.Series(["Compra no débito autorizada - Uber", "Lançamento XPTO"])
    result = service.predict_batch(descriptions)
    assert list(result["category"]) == ["Transporte", CATEGORIA_NAO_CATEGORIZADO]
    assert list(result["category_source"]) == ["keyword_rule", "none"]


def test_train_with_too_few_samples_does_not_produce_model(service):
    training_df = pd.DataFrame({
        "description": ["a", "b"], "category": ["Mercado", "Transporte"],
    })
    msg = service.train(training_df)
    assert "Poucos dados" in msg
    assert service.model is None


def test_train_with_enough_samples_produces_usable_model(service, tmp_path):
    service.model_path = tmp_path / "model.joblib"
    # "Academia" e "Consultorio"/"Clinica" (genérico) não têm regra de
    # palavra-chave cadastrada, então um acerto aqui só pode vir do ML —
    # ao contrário de "Padaria", que já é coberto por KEYWORD_RULES e
    # mascararia se o ML está funcionando de verdade.
    training_df = pd.DataFrame({
        "description": [
            "Academia Smart Fit", "Academia Bluefit", "Academia Bodytech", "Academia Vida Ativa",
            "Loja De Roupas Zara", "Loja Renner Shopping", "C And A Vestuario", "Loja Riachuelo",
        ],
        "category": [
            "Saúde", "Saúde", "Saúde", "Saúde",
            "Compras", "Compras", "Compras", "Compras",
        ],
    })
    msg = service.train(training_df)
    assert "treinado" in msg
    assert service.model is not None
    assert service.model_path.exists()

    # generaliza para uma academia nunca vista
    result = service.predict("Academia Power Fit Ltda")
    assert result.category == "Saúde"
    assert result.source == CategorySource.ML_MODEL


@pytest.mark.parametrize(
    "description,expected",
    [
        ("Pix enviado - Maria Jose Vieira", True),
        ("Pix recebido - Joao Silva", True),
        ("Transferência enviada - Danilo Aparecido Caldin", True),
        ("Transferência recebida - Danilo Aparecido Caldin", True),
        ("Compra no débito autorizada - Uber", False),
        ("Compra no débito autorizada - Marceloaloisio", False),
        ("Pagamento de boleto - Concessionaria", False),
        ("Distribuição de dividendos - Fundo X", False),
        ("", False),
    ],
)
def test_is_pix_or_transfer(description, expected):
    assert is_pix_or_transfer(description) is expected
