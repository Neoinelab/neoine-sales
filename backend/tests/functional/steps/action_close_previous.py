"""이전 Next Action 종료 feature의 step: Action 등록 요청에 이전 Action id를 싣는다.

When은 `POST /api/v1/deals/{code}/actions` 하나다. Then은 응답과 다시 조회한 Action·History·Deal만
본다. 사용자 구분과 시계는 `steps/actions.py`와 같다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.actions import (
    GAP_SECONDS,
    SUMMARY_WITH_MEMO,
    action_body,
    actions_url,
    when_list_actions,
)
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deals import history_rows, when_list_history
from tests.functional.steps.next_action_status import OPEN_BEFORE
from tests.functional.steps.users import Session, when_request_as

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

FIELD: Final = "close_previous_next_action_id"
CHANGED: Final = "이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요."
STATUS_FORBIDDEN: Final = "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."
CLOSED_ROW: Final = ("action", "Next Action", OPEN_BEFORE, "종료(수행)")
CREATED_ROW: Final = ("action", "Action", "", f"등록: {SUMMARY_WITH_MEMO}")


def closing_body(previous_id: object, **overrides: object) -> dict[str, Any]:
    return {**action_body(**overrides), FIELD: previous_id}


# --- When (HTTP API 하나) ---


async def when_register_closing(
    api: Api, code: str, previous_id: object, **overrides: object
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.post(actions_url(code), json=closing_body(previous_id, **overrides))


async def when_register_closing_as(
    api: Api, session: Session, code: str, previous_id: object, **overrides: object
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await when_request_as(
        api, session, "POST", actions_url(code), json=closing_body(previous_id, **overrides)
    )


async def when_register_with_body(api: Api, code: str, body: object) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.post(actions_url(code), json=body)


# --- Then ---


async def actions_of(api: Api, code: str) -> list[dict[str, Any]]:
    response = await when_list_actions(api, code, limit=200)
    then_status_is(response, 200)
    return list(response.json()["items"])


async def then_action_count_is(api: Api, code: str, count: int) -> None:
    assert len(await actions_of(api, code)) == count


async def then_previous_is_open(api: Api, code: str, previous_id: object) -> None:
    """이전 Action의 Next Action이 Open이고 종료 시각이 없다."""
    found = next(a for a in await actions_of(api, code) if a["id"] == previous_id)
    assert found["next_action_status"] == "open", found
    assert found["next_action_closed_at"] is None, found


async def then_previous_is_done_at(
    api: Api, code: str, previous_id: object, created: dict[str, Any]
) -> None:
    """이전 Action이 종료(수행)이고 종료 시각이 새 Action의 수행 일시와 같으며 Memo는 그대로다."""
    from tests.functional.steps.action_checks import same_instant  # noqa: PLC0415

    found = next(a for a in await actions_of(api, code) if a["id"] == previous_id)
    assert found["next_action_status"] == "done", found
    assert same_instant(found["next_action_closed_at"], created["acted_at"]), (found, created)
    assert found["memo"] == "요구사항 정리", found


async def then_history_tail_is(
    api: Api, code: str, expected: list[tuple[str, str, str, str]]
) -> None:
    """등록 이력 뒤 이력의 끝부분이 expected와 순서까지 같다(오래된 순서)."""
    rows = history_rows(await when_list_history(api, code))
    assert rows[-len(expected) :] == expected, rows
