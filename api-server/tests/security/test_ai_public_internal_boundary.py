from api.v1 import public_gateway_router, private_router


def _original_routers(router):
    return [
        original
        for included in router.routes
        if (original := getattr(included, "original_router", None)) is not None
    ]


def test_medical_ai_routes_are_not_mounted_on_public_gateway():
    public_prefixes = {getattr(child, "prefix", "") for child in _original_routers(public_gateway_router)}
    private_prefixes = {getattr(child, "prefix", "") for child in _original_routers(private_router)}

    assert "/scribe-ia" not in public_prefixes
    assert "/simulation-ia" not in public_prefixes
    assert "/scribe-ia" in private_prefixes
    assert "/simulation-ia" in private_prefixes


def test_medical_ai_routes_have_role_dependencies():
    sensitive_routes = []
    for child in _original_routers(private_router):
        if getattr(child, "prefix", "") in {"/scribe-ia", "/simulation-ia"}:
            sensitive_routes.extend(child.routes)

    assert sensitive_routes
    for route in sensitive_routes:
        assert getattr(route, "dependant", None) is not None
        assert route.dependant.dependencies
        dependency_names = {
            getattr(dependency.call, "__name__", "")
            for dependency in route.dependant.dependencies
        }
        assert "role_checker" in dependency_names
