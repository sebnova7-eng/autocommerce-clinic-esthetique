"""Contrôles de non-régression de la surface RBAC sensible."""
from pathlib import Path


def _route(path: str, name: str):
    module = __import__(path, fromlist=["router"])
    return next(r for r in module.router.routes if r.name == name)


def _dependency_names(route):
    return {getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies}


def test_copilote_sensitive_routes_use_role_guard():
    module = __import__("api.v1.copilote_crm", fromlist=["router"])
    routes = {
        r.path: r for r in module.router.routes
        if "/patient/" in r.path
    }
    assert routes
    for route in routes.values():
        assert "role_checker" in _dependency_names(route)


def test_business_intelligence_routes_use_role_guard():
    module = __import__("api.v1.business_intelligence", fromlist=["router"])
    for route in module.router.routes:
        assert "role_checker" in _dependency_names(route)


def test_insights_ignores_client_clinic_id():
    source = Path("api/v1/bi_insights.py").read_text()
    assert 'clinic_id=current_user["clinic_id"]' in source
    assert "clinic_id=payload.clinic_id" not in source


def test_omnicanal_mutations_propagate_server_clinic_id():
    source = Path("api/v1/omnicanal.py").read_text()
    assert 'clinic_id=current_user["clinic_id"]' in source
    assert "Conversation.clinic_id == current_user[\"clinic_id\"]" in source
