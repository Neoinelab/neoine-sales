"""경고 기준 API의 OpenAPI 계약: 경로·메서드·요청 필드·응답 필드."""

from typing import Any

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

URL = "/api/v1/alert-settings"


def _spec() -> dict[str, Any]:
    settings = make_settings("postgresql+asyncpg://user:pw@localhost:5432/none")
    return dict(create_app(settings=settings, use_cases=FakeUseCases()).openapi())


def _schema(spec: dict[str, Any], name: str) -> dict[str, Any]:
    return dict(spec["components"]["schemas"][name])


def test_the_path_offers_get_and_put_only() -> None:
    """경로는 GET과 PUT만 제공한다."""
    # when: OpenAPI 문서를 만든다
    methods = set(_spec()["paths"][URL])

    # then: get과 put뿐이다
    assert methods == {"get", "put"}


def test_the_request_has_one_integer_field_and_forbids_extras() -> None:
    """요청은 정수 필드 하나뿐이고 추가 필드를 금지한다."""
    # when: 요청 스키마를 읽는다
    schema = _schema(_spec(), "AlertSettingsRequest")

    # then: 필수 정수 stale_days 하나이고 추가 속성은 금지다
    assert set(schema["properties"]) == {"stale_days"}
    assert schema["properties"]["stale_days"]["type"] == "integer"
    assert schema["required"] == ["stale_days"]
    assert schema["additionalProperties"] is False


def test_the_response_has_the_value_the_time_and_the_saver() -> None:
    """응답은 값·저장 시각·저장한 사람을 담는다."""
    # when: 응답 스키마를 읽는다
    schema = _schema(_spec(), "AlertSettingsResponse")

    # then: 세 필드이고 stale_days는 정수다
    assert set(schema["properties"]) == {"stale_days", "updated_at", "updated_by"}
    assert schema["properties"]["stale_days"]["type"] == "integer"
