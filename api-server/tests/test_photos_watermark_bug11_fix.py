from pathlib import Path
import ast


PHOTOS_CLINIC = Path(__file__).resolve().parents[1] / "services" / "photos_clinic.py"


def _function_node(tree: ast.AST, name: str):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def test_signed_watermark_helpers_exist():
    tree = ast.parse(PHOTOS_CLINIC.read_text(encoding="utf-8"), filename=str(PHOTOS_CLINIC))
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "_save_signed_jpeg" in names
    assert "_verify_signed_watermark" in names
    assert "_build_watermark_signature_payload" in names


def test_signed_jpeg_uses_embedded_comment_metadata():
    tree = ast.parse(PHOTOS_CLINIC.read_text(encoding="utf-8"), filename=str(PHOTOS_CLINIC))
    func = _function_node(tree, "_save_signed_jpeg")
    assert func is not None

    found_comment_kw = False
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "comment":
                    found_comment_kw = True
    assert found_comment_kw, "Le JPEG signé doit embarquer un commentaire de signature"
