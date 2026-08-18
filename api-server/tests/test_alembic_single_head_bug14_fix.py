from pathlib import Path
import ast


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


def test_alembic_has_a_single_head_after_bloc_fixes():
    revisions = set()
    children = {}

    for path in VERSIONS_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = _extract_assignment(tree, "revision")
        down_revision = _extract_assignment(tree, "down_revision")
        if not revision:
            continue
        revisions.add(revision)
        if isinstance(down_revision, tuple):
            parents = [value for value in down_revision if value]
        elif down_revision:
            parents = [down_revision]
        else:
            parents = []
        for parent in parents:
            children.setdefault(parent, set()).add(revision)

    heads = {rev for rev in revisions if rev not in children}
    assert len(heads) == 1, f"Alembic doit rester single-head, trouvé: {sorted(heads)}"
