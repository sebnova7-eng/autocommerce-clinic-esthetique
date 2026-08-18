#!/usr/bin/env python3
"""Compatibilité locale : délègue vers api-server/bootstrap_admin.py.

Le script exécutable dans Docker est désormais `api-server/bootstrap_admin.py`.
Ce wrapper conserve l'ancien chemin pour les usages locaux existants.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_IMPL_PATH = Path(__file__).resolve().parent.parent / "api-server" / "bootstrap_admin.py"
_spec = importlib.util.spec_from_file_location("bootstrap_admin_impl", _IMPL_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Impossible de charger {_IMPL_PATH}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

bootstrap = _module.bootstrap
main = _module.main


if __name__ == "__main__":
    main()
