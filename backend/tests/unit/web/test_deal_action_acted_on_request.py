"""Action 등록·수정 요청의 선택 필드 acted_on(수행일)."""

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


def _update(**extra: object) -> DealActionUpdateRequest:
    return DealActionUpdateRequest(**{**BODY, **extra})


def test_the_update_request_maps_acted_on_to_the_update_input() -> None:
    """수정 요청의 acted_on 날짜가 수정 입력으로 넘어간다.

    테스트 코드: AC-054, AC-118
    """
    # when: acted_on을 실은 수정 요청을 입력으로 바꾼다
    data = _update(acted_on="2026-11-10").to_input()

    # then: 입력의 acted_on이 그 날짜이고 내용은 content에 담긴다
    assert data.acted_on == date(2026, 11, 10)
    assert data.content.action == "킥오프 미팅"


@pytest.mark.parametrize("extra", [{}, {"acted_on": None}], ids=["omitted", "null"])
def test_missing_or_null_acted_on_on_update_reaches_the_input_as_none(
    extra: dict[str, object],
) -> None:
    """수정 요청에서 acted_on이 없거나 null이면 수행일 유지(None)다.

    테스트 코드: AC-103, AC-120
    """
    # when: acted_on 없이 / null로 만든 수정 요청을 입력으로 바꾼다
    data = _update(**extra).to_input()
    # then: 입력의 acted_on은 없음이다
    assert data.acted_on is None


@pytest.mark.parametrize(
    "bad",
    [
        "2026-13-01",
        "2026-02-30",
        "2026-11-10T10:00:00+09:00",
        "2026-11-10T00:00:00",
        20261110,
        "",
        True,
    ],
)
def test_update_acted_on_that_is_not_a_plain_calendar_date_is_rejected(bad: object) -> None:
    """달력 날짜가 아니거나 시각이 붙거나 숫자인 수정 acted_on은 검증 오류다.

    테스트 코드: AC-124
    """
    # given: 올바른 acted_on은 받는다
    assert _update(acted_on="2026-11-10").acted_on == date(2026, 11, 10)
    # when·then: 잘못된 acted_on을 주면 검증 오류다
    with pytest.raises(ValidationError):
        _update(acted_on=bad)


@pytest.mark.parametrize(
    "forbidden",
    [
        {"acted_at": "2026-11-10T23:59:59+09:00"},
        {"close_previous_next_action_id": 5},
        {"status_change": {"change": {"field": "status_key", "value": "best"}}},
        {"actor_user_id": 1},
    ],
    ids=["acted_at", "close_previous", "status_change", "actor"],
)
def test_the_update_request_still_rejects_other_server_or_sync_fields(
    forbidden: dict[str, object],
) -> None:
    """수정 요청은 acted_on을 받아도 수행 시각·동반 변경·서버 필드는 계속 거부한다.

    테스트 코드: AC-054
    """
    # given: acted_on을 함께 실은 수정 요청은 받는다
    assert _update(acted_on="2026-11-10").acted_on == date(2026, 11, 10)
    # when·then: 그 위에 거부 대상 필드를 얹으면 검증 오류다
    with pytest.raises(ValidationError):
        _update(acted_on="2026-11-10", **forbidden)


def test_openapi_documents_an_optional_nullable_date_on_create_and_update() -> None:
    """OpenAPI는 등록·수정 요청 모두에 선택·null 허용 날짜 acted_on을 문서화한다.

    테스트 코드: AC-070, AC-104
    """
    # when: OpenAPI 문서를 만든다
    schemas = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()["components"]["schemas"]
    create = schemas["DealActionCreateRequest"]
    update = schemas["DealActionUpdateRequest"]

    # then: 두 요청 모두 date 형식이고 null을 허용하며 필수가 아니다
    for request in (create, update):
        options = request["properties"]["acted_on"]["anyOf"]
        assert {"type": "string", "format": "date"} in options
        assert {"type": "null"} in options
        assert "acted_on" not in request.get("required", [])
    # then: 두 요청 모두 acted_at이 없다
    assert "acted_at" not in create["properties"]
    assert "acted_at" not in update["properties"]
