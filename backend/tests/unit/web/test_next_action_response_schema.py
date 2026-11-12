"""NextActionResponse 계약: due_date는 필수이며 null이 될 수 없다."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.deal_action.next_action_status import NextActionStatus
from app.main import create_app
from app.web.schemas.deal_response import NextActionResponse
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


def _is_nullable(prop: dict[str, Any]) -> bool:
    return prop.get("type") == "null" or any(
        option.get("type") == "null" for option in prop.get("anyOf", [])
    )


def test_response_with_a_date_serializes_it() -> None:
    """기한이 날짜인 응답은 ISO 문자열로 직렬화된다."""
    # given: 기한이 날짜인 Next Action 응답
    response = NextActionResponse(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.DONE
    )

    # when: JSON 모드로 직렬화한다
    dumped = response.model_dump(mode="json")
    # then: 기한이 ISO 날짜 문자열이고 상태는 done이다
    assert dumped == {
        "text": "계약서 검토",
        "due_date": "2026-02-05",
        "status": "done",
    }


def test_response_rejects_a_null_due_date() -> None:
    """기한이 null인 응답은 만들 수 없다."""
    # when·then: due_date=None으로 만들면 검증 오류가 난다
    with pytest.raises(ValidationError):
        NextActionResponse(text="계약서 검토", due_date=None, status="open")


def test_response_rejects_a_missing_due_date() -> None:
    """기한이 없는 응답은 만들 수 없다."""
    # when·then: due_date 없이 검증하면 검증 오류가 난다
    with pytest.raises(ValidationError):
        NextActionResponse.model_validate({"text": "계약서 검토", "status": "open"})


def test_openapi_marks_due_date_required_and_not_nullable() -> None:
    """OpenAPI는 due_date를 필수이고 null 불가로 표시한다."""
    # given: Fake 유스케이스로 만든 앱
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    # when: OpenAPI 스키마를 만든다
    schema = app.openapi()["components"]["schemas"]["NextActionResponse"]

    # then: due_date가 필수이고 null이 될 수 없다
    assert "due_date" in schema["required"]
    assert not _is_nullable(schema["properties"]["due_date"])


def test_response_requires_a_status_from_the_three_values() -> None:
    """상태가 없거나 세 값 밖이면 응답을 만들 수 없다."""
    # when·then: 상태 없이 검증하면 검증 오류가 난다
    with pytest.raises(ValidationError):
        NextActionResponse.model_validate({"text": "a", "due_date": "2026-02-05"})
    # when·then: 세 값 밖의 상태로 검증하면 검증 오류가 난다
    with pytest.raises(ValidationError):
        NextActionResponse.model_validate({"text": "a", "due_date": "2026-02-05", "status": "x"})


def test_openapi_marks_status_required_with_the_three_values() -> None:
    """OpenAPI는 상태를 필수이고 open·done·not_done 세 값으로 표시한다."""
    # given: Fake 유스케이스로 만든 앱
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    # when: OpenAPI 스키마를 만든다
    schemas = app.openapi()["components"]["schemas"]

    # then: 상태가 필수이고 enum이 세 값이다
    assert "status" in schemas["NextActionResponse"]["required"]
    assert schemas["NextActionStatus"]["enum"] == ["open", "done", "not_done"]
