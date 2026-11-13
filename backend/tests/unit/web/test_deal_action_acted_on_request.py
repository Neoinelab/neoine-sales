"""Action 등록 요청의 선택 필드 acted_on(수행일). 수정 요청에는 없다."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.web.schemas.deal_action import DealActionCreateRequest, DealActionUpdateRequest
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
BODY: dict[str, Any] = {
    "action_type": {"name": "미팅"},
    "action": "킥오프 미팅",
    "next_action": "요구사항 문서 전달",
    "due_date": "2026-03-10",
    "memo": "",
}


def _create(**extra: object) -> DealActionCreateRequest:
    return DealActionCreateRequest(**{**BODY, **extra})


def test_acted_on_maps_to_the_input_date() -> None:
    """acted_on 날짜가 입력으로 넘어간다.

    테스트 코드: AC-092
    """
    # when: acted_on을 실은 등록 요청을 입력으로 바꾼다
    data = _create(acted_on="2026-11-10").to_input()
    # then: 입력의 acted_on이 그 날짜다
    assert data.acted_on == date(2026, 11, 10)


@pytest.mark.parametrize("extra", [{}, {"acted_on": None}], ids=["omitted", "null"])
def test_missing_or_null_acted_on_reaches_the_input_as_none(extra: dict[str, object]) -> None:
    """acted_on이 없거나 null이면 지정 없음(None)이다.

    테스트 코드: AC-091
    """
    # when: acted_on 없이 / null로 만든 등록 요청을 입력으로 바꾼다
    data = _create(**extra).to_input()
    # then: 입력의 acted_on은 없음이다
    assert data.acted_on is None


@pytest.mark.parametrize(
    "bad",
    ["2026-13-01", "2026-11-10T10:00:00+09:00", 20261110, "내일", "", True],
)
def test_acted_on_that_is_not_a_plain_calendar_date_is_rejected(bad: object) -> None:
    """달력 날짜가 아니거나 시각이 붙거나 숫자인 acted_on은 검증 오류다.

    테스트 코드: AC-095
    """
    # given: 올바른 acted_on은 받는다
    assert _create(acted_on="2026-11-10").acted_on == date(2026, 11, 10)
    # when·then: 잘못된 acted_on을 주면 검증 오류다
    with pytest.raises(ValidationError):
        _create(acted_on=bad)


@pytest.mark.parametrize("bad", ["2026-11-10T00:00:00", "2026-02-30"])
def test_acted_on_with_midnight_time_or_nonexistent_date_is_rejected(bad: str) -> None:
    """자정 시각이 붙은 문자열이나 없는 날짜의 acted_on은 검증 오류다.

    테스트 코드: AC-095
    """
    # given: 올바른 acted_on은 받는다
    assert _create(acted_on="2026-11-10").acted_on == date(2026, 11, 10)
    # when·then: 시각이 붙었거나 달력에 없는 날짜를 주면 검증 오류다
    with pytest.raises(ValidationError):
        _create(acted_on=bad)


def test_acted_at_is_still_rejected_on_create() -> None:
    """수행 시점은 acted_on으로만 고르고 acted_at은 계속 거부한다.

    테스트 코드: AC-095
    """
    # when·then: acted_at을 넣으면 검증 오류다
    with pytest.raises(ValidationError):
        _create(acted_at="2026-11-10T23:59:59+09:00")


def test_the_update_request_does_not_accept_acted_on() -> None:
    """수정 요청은 acted_on을 받지 않는다(수행 일시는 수정할 수 없음).

    테스트 코드: AC-054, AC-103
    """
    # given: 같은 값을 등록 요청은 받는다
    assert _create(acted_on="2026-11-10").acted_on == date(2026, 11, 10)
    # when·then: 수정 요청에 acted_on을 넣으면 검증 오류다
    with pytest.raises(ValidationError):
        DealActionUpdateRequest(**{**BODY, "acted_on": "2026-11-10"})


def test_openapi_documents_an_optional_nullable_date_on_create_only() -> None:
    """OpenAPI는 등록 요청에만 선택·null 허용 날짜 acted_on을 문서화한다.

    테스트 코드: AC-070, AC-104
    """
    # when: OpenAPI 문서를 만든다
    schemas = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()["components"]["schemas"]
    create = schemas["DealActionCreateRequest"]
    update = schemas["DealActionUpdateRequest"]

    # then: 등록 요청에 date 형식이고 null을 허용하며 필수가 아니다
    prop = create["properties"]["acted_on"]
    options = prop["anyOf"]
    assert {"type": "string", "format": "date"} in options
    assert {"type": "null"} in options
    assert "acted_on" not in create.get("required", [])
    # then: 수정 요청에는 없고 두 요청 모두 acted_at이 없다
    assert "acted_on" not in update["properties"]
    assert "acted_at" not in create["properties"]
    assert "acted_at" not in update["properties"]
