"""Tests des prompts versionnés (v1.1.0 patch IA)."""

from __future__ import annotations

import pytest

from core.prompt_templates import (
    get, CATALOG, DASHBOARD_NARRATION, WORKFLOW_DECISION,
    COPILOTE_SUMMARY, BI_INSIGHTS,
)


def test_catalog_contains_all_blocks():
    expected_keys = {
        "dashboard.narration", "workflow.decision",
        "copilote.summary", "copilote.whatsapp_draft", "bi.insights",
    }
    assert expected_keys <= set(CATALOG.keys())


def test_get_unknown_key_raises():
    with pytest.raises(KeyError):
        get("inexistant.prompt")


def test_versions_are_positive():
    for t in CATALOG.values():
        assert isinstance(t.version, int)
        assert t.version >= 1


def test_render_format():
    msgs = COPILOTE_SUMMARY.render(
        patient_json="{}",
        dossiers_json="{}",
        rdvs_json="{}",
        factures_json="{}",
        photos_json="{}",
    )
    assert isinstance(msgs, list)
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "Patient :" in msgs[1]["content"]


def test_jsonmode_on_narration_bi_workflow():
    assert DASHBOARD_NARRATION.json_mode is True
    assert BI_INSIGHTS.json_mode is True
    assert WORKFLOW_DECISION.json_mode is True


def test_jsonmode_off_summary():
    assert COPILOTE_SUMMARY.json_mode is False
