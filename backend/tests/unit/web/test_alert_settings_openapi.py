"""경고 기준 API의 OpenAPI 계약(P3 AC-05~07): 경로·메서드·요청 필드·응답 필드."""

from typing import Any

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

URL = "/api/v1/alert-settings"


def _spec() -> dict[str, Any]:
    settings = make_settings("postgresql+asyncpg://user:pw@localhost:5432/none")
    return dict(create_app(settings=settings, use_cases=FakeUseCases()).openapi())


def _schema(spec: dict[str, Any], name: str) -> dict[str, Any]:
    return dict(spec["components"]["schemas"][name])


def test_the_path_offers_get_and_put_only() -> None:
    assert set(_spec()["paths"][URL]) == {"get", "put"}


def test_the_request_has_one_integer_field_and_forbids_extras() -> None:
    schema = _schema(_spec(), "AlertSettingsRequest")

    assert set(schema["properties"]) == {"stale_days"}
    assert schema["properties"]["stale_days"]["type"] == "integer"
    assert schema["required"] == ["stale_days"]
    assert schema["additionalProperties"] is False


def test_the_response_has_the_value_the_time_and_the_saver() -> None:
    schema = _schema(_spec(), "AlertSettingsResponse")

    assert set(schema["properties"]) == {"stale_days", "updated_at", "updated_by"}
    assert schema["properties"]["stale_days"]["type"] == "integer"
