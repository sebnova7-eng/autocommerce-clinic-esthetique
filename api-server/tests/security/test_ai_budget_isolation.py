from types import SimpleNamespace

import pytest

from core.llm_budget import (
    LLMBudgetExceeded,
    clear_memory_budgets,
    reserve_budget,
)


def _settings(**overrides):
    values = dict(
        env="test",
        clinic_id=None,
        is_internal_single_clinic=False,
        redis_url="",
        llm_max_requests_per_user_day=100,
        llm_daily_token_budget=1000,
        llm_monthly_token_budget=5000,
        llm_max_requests_per_clinic_day=1,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def reset_budget_memory():
    clear_memory_budgets()
    yield
    clear_memory_budgets()


@pytest.mark.asyncio
async def test_clinic_a_limit_does_not_consume_clinic_b_budget():
    settings = _settings(llm_max_requests_per_clinic_day=1)

    await reserve_budget(settings, "clinic:10:user:1", 100, clinic_id=10)
    with pytest.raises(LLMBudgetExceeded):
        await reserve_budget(settings, "clinic:10:user:2", 100, clinic_id=10)

    # Clinic B has its own counter and remains operational.
    await reserve_budget(settings, "clinic:20:user:3", 100, clinic_id=20)


@pytest.mark.asyncio
async def test_explicit_server_clinic_wins_over_subject_text():
    settings = _settings(llm_max_requests_per_clinic_day=1)

    # The explicit value is supplied by the authenticated backend context.
    await reserve_budget(settings, "clinic:999:user:1", 100, clinic_id=10)
    await reserve_budget(settings, "clinic:999:user:2", 100, clinic_id=20)

    with pytest.raises(LLMBudgetExceeded):
        await reserve_budget(settings, "clinic:999:user:3", 100, clinic_id=10)


@pytest.mark.asyncio
async def test_production_without_authenticated_tenant_fails_closed():
    from middleware.clinic_context import clinic_id_var

    settings = _settings(env="production", clinic_id=None)
    token = clinic_id_var.set(None)
    try:
        with pytest.raises(LLMBudgetExceeded, match="Contexte clinique absent"):
            await reserve_budget(settings, "global", 100)
    finally:
        clinic_id_var.reset(token)


@pytest.mark.asyncio
async def test_concurrent_requests_cannot_both_pass_clinic_limit():
    settings = _settings(llm_max_requests_per_clinic_day=1)

    results = await __import__("asyncio").gather(
        reserve_budget(settings, "clinic:10:user:1", 100, clinic_id=10),
        reserve_budget(settings, "clinic:10:user:2", 100, clinic_id=10),
        return_exceptions=True,
    )

    assert sum(isinstance(result, LLMBudgetExceeded) for result in results) == 1
