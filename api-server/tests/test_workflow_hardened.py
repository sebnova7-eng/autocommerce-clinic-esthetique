"""
Tests de WorkflowEngineService v2 : idempotence, audit, retry, humain-dans-la-boucle.
"""

from __future__ import annotations

from services.workflow_engine import (
    WorkflowEngineService, _idempotency_key,
)


def test_idempotency_key_determinism():
    payload = {"a": 1, "b": "x"}
    k1 = _idempotency_key(1, 1, "send_email", payload)
    k2 = _idempotency_key(1, 1, "send_email", payload)
    assert k1 == k2
    k3 = _idempotency_key(1, 1, "send_email", {"a": 2, "b": "x"})
    assert k1 != k3


def test_auto_send_actions_set():
    auto = WorkflowEngineService.AUTO_SEND_ACTIONS
    assert "send_whatsapp" in auto
    assert "send_sms" in auto
    assert "send_email" in auto
    assert "create_appointment" not in auto


def test_workflow_engine_v2_methods_present():
    assert hasattr(WorkflowEngineService, "decide_next_branch")
    assert hasattr(WorkflowEngineService, "approve_drafted_action")
    assert hasattr(WorkflowEngineService, "_retry_with_backoff")
    assert hasattr(WorkflowEngineService, "_is_already_executed")


def test_awaiting_approval_in_enum():
    """Le statut AWAITING_APPROVAL doit exister (utilisé par approve_drafted_action)."""
    from models.workflow_engine import WorkflowExecutionStatus
    assert hasattr(WorkflowExecutionStatus, "AWAITING_APPROVAL")
    assert WorkflowExecutionStatus.AWAITING_APPROVAL.value == "awaiting_approval"


def test_audit_log_model_present():
    """Le modèle WorkflowAuditLog doit être créé (table d'audit)."""
    from models.workflow_engine import WorkflowAuditLog
    assert hasattr(WorkflowAuditLog, "__tablename__")
    assert WorkflowAuditLog.__tablename__ == "workflow_audit_logs"
