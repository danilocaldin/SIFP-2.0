"""
Testes de BudgetRepository e GoalRepository (Módulo 13/14).
"""

import pytest

from sifp.repositories.budget_repository import BudgetRepository
from sifp.repositories.connection import init_db
from sifp.repositories.goal_repository import GoalRepository


@pytest.fixture
def budget_repo(tmp_db_path):
    init_db(tmp_db_path)
    return BudgetRepository(tmp_db_path)


@pytest.fixture
def goal_repo(tmp_db_path):
    init_db(tmp_db_path)
    return GoalRepository(tmp_db_path)


def test_set_and_get_limit(budget_repo):
    budget_repo.set_limit("Lazer", 300.0)
    budget_repo.set_limit("Mercado", 1200.0)

    limits = budget_repo.get_limits_dict()
    assert limits == {"Lazer": 300.0, "Mercado": 1200.0}


def test_set_limit_overwrites_previous_value(budget_repo):
    budget_repo.set_limit("Lazer", 300.0)
    budget_repo.set_limit("Lazer", 500.0)

    limits = budget_repo.get_limits_dict()
    assert limits == {"Lazer": 500.0}


def test_remove_limit(budget_repo):
    budget_repo.set_limit("Lazer", 300.0)
    budget_repo.remove_limit("Lazer")

    assert budget_repo.get_limits_dict() == {}


def test_goal_create_and_progress(goal_repo):
    goal_id = goal_repo.create("Reserva de emergência", valor_necessario=15000.0, prazo="2026-12-31")
    goal_repo.update_progress(goal_id, 3000.0)

    goals = goal_repo.get_all()
    assert len(goals) == 1
    row = goals.iloc[0]
    assert row["nome"] == "Reserva de emergência"
    assert row["valor_acumulado"] == pytest.approx(3000.0)
    assert row["valor_necessario"] == pytest.approx(15000.0)


def test_goal_delete(goal_repo):
    goal_id = goal_repo.create("Viagem", valor_necessario=5000.0, prazo="2026-12-31")
    goal_repo.delete(goal_id)
    assert goal_repo.get_all().empty


def test_multiple_goals_ordered_by_prazo(goal_repo):
    goal_repo.create("Meta B", valor_necessario=1000.0, prazo="2027-06-01")
    goal_repo.create("Meta A", valor_necessario=1000.0, prazo="2026-08-01")

    goals = goal_repo.get_all()
    assert list(goals["nome"]) == ["Meta A", "Meta B"]
