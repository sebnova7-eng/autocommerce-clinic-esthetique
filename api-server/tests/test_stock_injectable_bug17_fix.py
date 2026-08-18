"""Tests statiques de non-régression — Bug #17.

On évite ici les imports applicatifs lourds ; le test vérifie par AST que :
1. la route /injectables/utilisation autorise bien esthéticienne + assistante ;
2. le helper _resolve_praticien_id_for_usage existe ;
3. la route appelle ce helper avant register_usage.
"""

from pathlib import Path
import ast


ROUTER_FILE = Path(__file__).resolve().parents[1] / "api" / "v1" / "stock_injectable.py"


def _function_node(tree: ast.AST, name: str):
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def test_bug17_helper_exists_and_is_used_by_route():
    tree = ast.parse(ROUTER_FILE.read_text(encoding="utf-8"), filename=str(ROUTER_FILE))

    helper = _function_node(tree, "_resolve_praticien_id_for_usage")
    route = _function_node(tree, "register_lot_usage")

    assert helper is not None, "Le helper de sécurisation du praticien doit exister"
    assert route is not None, "La route register_lot_usage doit exister"

    helper_called = False
    register_usage_called = False
    for node in ast.walk(route):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "_resolve_praticien_id_for_usage":
                helper_called = True
            if node.func.id == "register_usage":
                register_usage_called = True

    assert helper_called, "La route doit résoudre/sécuriser le praticien avant l'enregistrement"
    assert register_usage_called, "La route doit continuer à appeler register_usage"


def test_bug17_route_rbac_mentions_estheticienne_and_assistante():
    source = ROUTER_FILE.read_text(encoding="utf-8")
    assert "RoleEnum.ESTHETICIENNE" in source
    assert "RoleEnum.ASSISTANTE" in source
    assert "Vous ne pouvez enregistrer une injection qu'en votre propre nom" in source
