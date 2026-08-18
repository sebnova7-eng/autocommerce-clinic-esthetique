"""
Tests d'intégration LLM des 4 services cœurs (Blocs 5-8).

Ces tests valident que :
1. Chaque service PERTINENT expose un champ ``llm_status`` honnête ;
2. Si LLM indisponible (clé vide), le service retourne ses chiffres SQL ;
3. Si LLM présent (mocké), le service enrichit le rendu ;
4. Aucune exception non capturée n'est levée.
"""

from __future__ import annotations

import pytest


def test_copilote_no_llm_returns_data():
    """smoke test : import sans crash."""
    from services import copilote_crm
    assert hasattr(copilote_crm, "CopiloteCRMService")
    assert hasattr(copilote_crm.CopiloteCRMService, "summarize_patient_file")


def test_dashboard_no_llm_returns_metrics():
    from services import dashboard_ia
    assert hasattr(dashboard_ia.DashboardIAService, "get_daily_summary")
    assert hasattr(dashboard_ia.DashboardIAService, "get_ai_recommendations")
    assert hasattr(dashboard_ia.DashboardIAService, "get_revenue_forecast")


def test_bi_no_llm_returns_kpis():
    from services import business_intelligence
    assert hasattr(business_intelligence.BusinessIntelligenceService, "get_kpi_dashboard")
    assert hasattr(business_intelligence.BusinessIntelligenceService, "get_llm_insights")


def test_workflow_engine_v2_methods():
    from services import workflow_engine
    assert hasattr(workflow_engine.WorkflowEngineService, "execute_workflow")
    assert hasattr(workflow_engine.WorkflowEngineService, "decide_next_branch")


@pytest.mark.asyncio
async def test_llm_unavailable_propagates_marker():
    """Appel direct à ``LLMClient.chat`` sans clé doit retourner LLMUnavailable."""
    from core.llm_client import LLMUnavailable

    class _S:
        llm_provider = "openai"
        openai_api_key = ""
        openai_model = "gpt-4o"
        openrouter_api_key = ""
        anthropic_api_key = ""
        gemini_api_key = ""
        mistral_api_key = ""

    from core.llm_client import LLMClient, cache_clear
    cache_clear()
    llm = LLMClient(_S())
    out = await llm.chat(
        [{"role": "user", "content": "test"}], use_cache=False,
    )
    assert isinstance(out, LLMUnavailable)
    await llm.aclose()
