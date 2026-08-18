"""Vérifie qu'Alembic ne possède qu'un seul head actif.

Correctif Bug #14 : l'audit signalait un risque de dérive multi-head.
Ce script échoue explicitement si plusieurs migrations terminales sont
présentes, afin de bloquer la régression en CI/CD avant déploiement.
"""

from __future__ import annotations

import ast
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _extract_assignment(tree: ast.AST, name: str):
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == name:
                    return ast.literal_eval(node.value)
    return None


def compute_heads() -> tuple[set[str], dict[str, set[str]]]:
    revisions: set[str] = set()
    children: dict[str, set[str]] = {}

    for path in VERSIONS_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = _extract_assignment(tree, "revision")
        down_revision = _extract_assignment(tree, "down_revision")
        if not revision:
            continue
        revisions.add(revision)
        down_values = []
        if isinstance(down_revision, tuple):
            down_values = [value for value in down_revision if value]
        elif down_revision:
            down_values = [down_revision]
        for parent in down_values:
            children.setdefault(parent, set()).add(revision)

    heads = {rev for rev in revisions if rev not in children}
    return heads, children


if __name__ == "__main__":
    heads, _ = compute_heads()
    if len(heads) != 1:
        raise SystemExit(f"ERREUR: Alembic doit avoir 1 seul head, trouvé(s): {sorted(heads)}")
    print(f"OK: head unique Alembic = {next(iter(heads))}")
