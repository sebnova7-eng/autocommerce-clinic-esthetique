import importlib
import pkgutil

import api.v1


def test_all_routers_importable():
    for module in pkgutil.iter_modules(api.v1.__path__):
        importlib.import_module(f"api.v1.{module.name}")
