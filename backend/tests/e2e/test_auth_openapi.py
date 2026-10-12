"""인증 API의 OpenAPI 계약(AUTH-7·8·9): 경로·메서드·config 필드, 응답에 비밀번호 필드 없음."""

from typing import TYPE_CHECKING, Any

from app.main import create_app
from tests.e2e.conftest import make_settings

if TYPE_CHECKING:
    from tests.fakes.use_cases import FakeUseCases


def _spec(use_cases: FakeUseCases) -> dict[str, Any]:
    return create_app(settings=make_settings(), use_cases=use_cases).openapi()


def _response_schema_names(spec: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for item in spec["paths"].values():
        for operation in item.values():
            for response in operation.get("responses", {}).values():
                ref = response.get("content", {}).get("application/json", {}).get("schema", {})
                if "$ref" in ref:
                    names.add(ref["$ref"].rsplit("/", 1)[-1])
    return names


def _property_names(spec: dict[str, Any], schema: str, seen: set[str] | None = None) -> set[str]:
    seen = seen if seen is not None else set()
    if schema in seen:
        return set()
    seen.add(schema)
    properties = spec["components"]["schemas"][schema].get("properties", {})
    names = set(properties)
    for prop in properties.values():
        refs = [prop.get("$ref"), prop.get("items", {}).get("$ref")]
        refs += [option.get("$ref") for option in prop.get("anyOf", [])]
        for ref in filter(None, refs):
            names |= _property_names(spec, ref.rsplit("/", 1)[-1], seen)
    return names


def test_auth_routes_have_the_new_methods_and_no_oidc_routes(use_cases: FakeUseCases) -> None:
    paths = _spec(use_cases)["paths"]

    assert set(paths["/api/v1/auth/login"]) == {"post"}
    assert set(paths["/api/v1/auth/setup"]) == {"post"}
    assert set(paths["/api/v1/auth/setup/directory"]) == {"put"}
    assert "/api/v1/auth/callback" not in paths


def test_auth_config_schema_has_exactly_the_four_flags(use_cases: FakeUseCases) -> None:
    schema = _spec(use_cases)["components"]["schemas"]["AuthConfigResponse"]

    assert set(schema["properties"]) == {
        "dev_login",
        "directory_login",
        "needs_directory_setup",
        "needs_admin_setup",
    }


def test_no_response_schema_contains_a_password_field(use_cases: FakeUseCases) -> None:
    spec = _spec(use_cases)

    for name in _response_schema_names(spec):
        leaked = {p for p in _property_names(spec, name) if "password" in p.lower()}
        assert not leaked, f"{name} 응답에 비밀번호 필드가 있다: {leaked}"


def test_password_request_fields_are_masked_secrets(use_cases: FakeUseCases) -> None:
    schemas = _spec(use_cases)["components"]["schemas"]

    for name in ("LoginRequest", "SetupAdminRequest"):
        password = schemas[name]["properties"]["password"]
        assert password.get("format") == "password"
        assert password.get("writeOnly") is True
