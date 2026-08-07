"""Teste de regressão: o modelo de categorização (sifp/api/shared.py) é
uma ÚNICA instância de processo, compartilhada por TODOS os clientes do
SaaS. routes_saas.py::_refresh_model() precisa NUNCA chamar
categorization_service.train() com dados de um tenant — isso
sobrescreveria o modelo global usado nas sugestões de todos os outros
clientes, e o vetorizador guarda n-gramas literais de descrições reais
(dado pessoal de terceiro). Achado real de auditoria, confirmado por 3
investigações independentes."""

from dotenv import load_dotenv

load_dotenv()

from sifp.api import routes_saas
from sifp.api import shared as shared_module


def test_refresh_model_nunca_chama_train(monkeypatch):
    chamou_train = {"sim": False}

    def _train_espiao(self, training_df):
        chamou_train["sim"] = True
        return "não devia ter treinado"

    monkeypatch.setattr(type(shared_module.categorization_service), "train", _train_espiao)

    resultado = routes_saas._refresh_model({})

    assert chamou_train["sim"] is False
    assert "desligado" in resultado.lower()


def test_refresh_model_nao_le_dados_do_tenant():
    class RepoQueExplode:
        def get_training_data(self):
            raise AssertionError("_refresh_model não devia nem ler os dados de treino do tenant")

    resultado = routes_saas._refresh_model({"transaction_repo": RepoQueExplode()})
    assert isinstance(resultado, str)
