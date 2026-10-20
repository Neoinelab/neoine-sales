"""Next Action 상태 feature의 step: 종료·되돌리기 요청과 상태·Memo·종료 시각 확인.

When은 `PUT /api/v1/deal-actions/{id}/next-action-status` 하나이고, Then은 응답과 다시 조회한
Action만 본다. 사용자 구분과 시계는 `steps/actions.py`와 같다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.actions import (
    ACTIONS,
    GAP_SECONDS,
    given_action,
    given_action_by,
    when_get_action,
)
from tests.functional.steps.common import then_status_is
from tests.functional.steps.users import Session, when_request_as

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

STATUS_FORBIDDEN: Final = "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."
NO_NEXT_ACTION: Final = "Next Action이 없는 Action은 상태를 바꿀 수 없습니다."
HISTORY_TARGET: Final = "Next Action"
OPEN_BEFORE: Final = "요구사항 문서 전달 (Due 2027-01-15) · Open"


def status_url(action_id: str) -> str:
    return f"{ACTIONS}/{action_id}/next-action-status"


def status_body(status: str, memo: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"status": status}
    if memo is not None:
        body["memo"] = memo
    return body


# --- Given ---


async def given_next_only_action(api: Api, code: str, **overrides: object) -> dict[str, Any]:
    """Next Action만 있는 Action(진행사항 없음)을 지금 로그인한 사용자가 남겨 두었다."""
    return await given_action(api, code, action="", **overrides)


async def given_progress_only_action(api: Api, code: str, **overrides: object) -> dict[str, Any]:
    """진행사항만 있는 Action(Next Action 없음)을 지금 로그인한 사용자가 남겨 두었다."""
    return await given_action(api, code, next_action="", **overrides)


async def given_progress_only_action_by(
    api: Api, session: Session, code: str, **overrides: object
) -> dict[str, Any]:
    return await given_action_by(api, session, code, next_action="", **overrides)


async def given_status_changed(
    api: Api, action_id: str, status: str, memo: str | None = None
) -> dict[str, Any]:
    """지금 로그인한 사용자가 Next Action 상태를 바꿔 두었다. 응답 본문을 돌려준다."""
    response = await when_change_status(api, action_id, status, memo)
    assert response.status_code == 200, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


# --- When (HTTP API 하나) ---


async def when_change_status(
    api: Api, action_id: str, status: str, memo: str | None = None
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.put(status_url(action_id), json=status_body(status, memo))


async def when_change_status_as(
    api: Api, session: Session, action_id: str, status: str, memo: str | None = None
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await when_request_as(
        api, session, "PUT", status_url(action_id), json=status_body(status, memo)
    )


async def when_change_status_with_body(api: Api, action_id: str, body: object) -> Response:
    """본문을 가공 없이 보낸다(잘못된 status 값·모르는 필드 시나리오)."""
    api.clock.advance(GAP_SECONDS)
    return await api.put(status_url(action_id), json=body)


# --- Then ---


def then_status_response_is(
    response: Response, status: str, *, closed: bool, memo: str | None = None
) -> None:
    """200이고 응답의 상태가 status, 종료 시각은 종료 상태일 때만 있다(서버 시계의 지금)."""
    then_status_is(response, 200)
    body = response.json()
    assert body["next_action_status"] == status, body
    assert (body["next_action_closed_at"] is not None) is closed, body
    if memo is not None:
        assert body["memo"] == memo, body


async def then_action_status_is(
    api: Api, action_id: str, status: str | None, *, memo: str | None = None
) -> None:
    """다시 조회한 Action의 상태가 status(없으면 None)이고, 주어졌다면 Memo도 같다."""
    response = await when_get_action(api, action_id)
    then_status_is(response, 200)
    body = response.json()
    assert body["next_action_status"] == status, body
    assert (body["next_action_closed_at"] is not None) is (status in ("done", "not_done")), body
    if memo is not None:
        assert body["memo"] == memo, body
