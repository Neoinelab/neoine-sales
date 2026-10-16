"""NextActionResponse 계약(P2 R1 Minor 1): due_date는 필수이며 null이 될 수 없다."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.web.schemas.deal_response import NextActionResponse
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


def _is_nullable(prop: dict[str, Any]) -> bool:
    return prop.get("type") == "null" or any(
        option.get("type") == "null" for option in prop.get("anyOf", [])
    )


def test_response_with_a_date_serializes_it() -> None:
    response = NextActionResponse(text="계약서 검토", due_date=date(2026, 2, 5))

    assert response.model_dump(mode="json") == {"text": "계약서 검토", "due_date": "2026-02-05"}


def test_response_rejects_a_null_due_date() -> None:
    with pytest.raises(ValidationError):
        NextActionResponse(text="계약서 검토", due_date=None)


def test_response_rejects_a_missing_due_date() -> None:
    with pytest.raises(ValidationError):
        NextActionResponse.model_validate({"text": "계약서 검토"})


def test_openapi_marks_due_date_required_and_not_nullable() -> None:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    schema = app.openapi()["components"]["schemas"]["NextActionResponse"]

    assert "due_date" in schema["required"]
    assert not _is_nullable(schema["properties"]["due_date"])
