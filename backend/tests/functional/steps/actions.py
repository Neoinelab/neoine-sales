"""Action feature의 step(P2): Deal 상세의 등록·수정·삭제·검색, 이력, 스냅숏.

Given은 공개 API로 사전 상태를 만든다. 수행 시각은 요청 본문이 아니라 서버 시계라서
(`tests/support/functional_clock.py`), 등록하기 전에 `api.clock`을 전진시킨다. 여러 사용자가
나오는 시나리오는 사용자마다 로그인 세션(`Session`)을 따로 들고 요청한다(`steps/users.py`).
When은 HTTP API 하나, Then은 응답과 다시 조회한 결과만 본다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.deals import DEALS, given_clock_at, given_deal, given_sales_owner
from tests.functional.steps.users import (
    Session,
    given_signed_in_session,
    id_of,
    log_in,
    when_request_as,
)

if TYPE_CHECKING:
    from datetime import datetime

    from httpx import Response

    from tests.functional.conftest import Api

ACTIONS: Final = "/api/v1/deal-actions"
GAP_SECONDS: Final = 60  # 동작 사이에 시계를 전진시켜 수행 시각을 구분한다

ACTION_OR_NEXT_REQUIRED: Final = "진행사항 또는 Next Action을 입력하세요."
DUE_DATE_REQUIRED: Final = "Due Date를 입력하세요."
DUE_WITHOUT_NEXT: Final = "Next Action 없이 Due Date를 입력할 수 없습니다."
EDIT_FORBIDDEN: Final = "본인 Action 또는 admin만 수정할 수 있습니다."
DELETE_FORBIDDEN: Final = "본인 Action 또는 admin만 삭제할 수 있습니다."
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
NOT_FOUND: Final = "Action을 찾을 수 없습니다."
REVERSED_ACTED: Final = "수행일 범위의 시작은 끝보다 늦을 수 없습니다."
REVERSED_DUE: Final = "Due Date 범위의 시작은 끝보다 늦을 수 없습니다."
SUMMARY: Final = "미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15)"
SUMMARY_WITH_MEMO: Final = f"{SUMMARY} / Memo: 요구사항 정리"
ACTION_KEYS: Final = {
    "id",
    "deal_code",
    "action_type",
    "action",
    "next_action",
    "due_date",
    "next_action_status",
    "next_action_closed_at",
    "memo",
    "acted_at",
    "actor",
    "status_key",
    "forecast_key",
    "created_at",
    "updated_at",
}


def actions_url(code: str) -> str:
    return f"{DEALS}/{code}/actions"


def action_body(**overrides: object) -> dict[str, Any]:
    """Action 등록·수정 본문(수행 시각·담당자는 서버가 정하므로 없다). None인 값은 null로 보낸다.

    Next Action이 비어 있으면 Due Date는 기본으로 null이다(Due만 보내려면 `due_date=`를 준다).

    action_type은 선택 객체다. 기본은 `{"name": "미팅"}`이고, 문자열을 주면 그 이름 객체로, dict를
    주면(`{"id": ...}` 등) 그대로 보낸다. 잘못된 형식은 `when_*_with_body`로 직접 보낸다.
    """
    values: dict[str, Any] = {
        "action_type": {"name": "미팅"},
        "action": "킥오프 미팅",
        "next_action": "요구사항 문서 전달",
        "due_date": "2027-01-15",
        "memo": "요구사항 정리",
    }
    body = {**values, **overrides}
    if "due_date" not in overrides and not str(body["next_action"] or "").strip():
        body["due_date"] = None  # Next Action이 없으면 Due Date도 보내지 않는다
    if isinstance(body["action_type"], str):
        body["action_type"] = {"name": body["action_type"]}
    return body


# --- Given ---


async def given_deal_with_a_sales_owner(api: Api, **overrides: object) -> dict[str, Any]:
    """영업 담당자가 Owner인 Deal(admin 로그인 상태에서 부른다. 끝나도 admin 상태다)."""
    return await given_deal(api, owner_user_id=await given_sales_owner(api), **overrides)


async def given_action(api: Api, code: str, **overrides: object) -> dict[str, Any]:
    """지금 로그인한 사용자가 Action을 남겨 두었다(시계가 전진한다). 응답 본문을 돌려준다."""
    api.clock.advance(GAP_SECONDS)
    response = await api.post(actions_url(code), json=action_body(**overrides))
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


async def given_action_by(
    api: Api, session: Session, code: str, **overrides: object
) -> dict[str, Any]:
    """주어진 세션의 사용자가 Action을 남겨 두었다(시계가 전진한다)."""
    api.clock.advance(GAP_SECONDS)
    response = await when_request_as(
        api, session, "POST", actions_url(code), json=action_body(**overrides)
    )
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


async def given_searchable_actions(api: Api) -> tuple[str, str]:
    """kim·park(sales)이 한 Deal에 Action 세 건을 남겨 두었다. (Deal code, park의 user id).

    오래된 순서: kim "킥오프"(미팅, Due 04-10) -> park "견적 발송"(이메일, Due 04-01) ->
    park "킥오프 2"(미팅, Due 04-10). 끝나면 admin(root)이 로그인 상태다.
    """
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    code = str(deal["code"])
    await given_action_by(
        api,
        kim,
        code,
        action="킥오프",
        action_type="미팅",
        memo="일정 협의",
        next_action="요구사항",
        due_date="2027-04-10",
    )
    await given_action_by(
        api,
        park,
        code,
        action="견적 발송",
        action_type="이메일",
        memo="100% 할인",
        next_action="회신 확인",
        due_date="2027-04-01",
    )
    await given_action_by(
        api,
        park,
        code,
        action="킥오프 2",
        action_type="미팅",
        memo="",
        next_action="계약서 초안",
        due_date="2027-04-10",
    )
    return code, await id_of(api, "park")


async def given_many_actions(api: Api, code: str, count: int) -> None:
    """지금 로그인한 사용자가 Action을 count건 남겨 두었다(진행사항은 "활동 NN")."""
    for number in range(count):
        await given_action(api, code, action=f"활동 {number:02d}")


async def given_action_at(
    api: Api, code: str, moment: datetime, **overrides: object
) -> dict[str, Any]:
    """서버 시계를 moment로 맞춘 뒤 지금 로그인한 사용자가 Action을 남겨 두었다."""
    await given_clock_at(api, moment)
    response = await api.post(actions_url(code), json=action_body(**overrides))
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


async def given_action_at_as(
    api: Api, code: str, moment: datetime, *, login_id: str, **overrides: object
) -> dict[str, Any]:
    """given_action_at과 같되, 시계가 8시간 넘게 움직이면 세션이 만료되므로 다시 로그인한다."""
    await given_clock_at(api, moment)
    await log_in(api, login_id)
    return await given_action_at(api, code, moment, **overrides)


# --- When (HTTP API 하나) ---


async def when_register_action(api: Api, code: str, **overrides: object) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.post(actions_url(code), json=action_body(**overrides))


async def when_register_action_with_body(api: Api, code: str, body: object) -> Response:
    """본문을 가공 없이 보낸다(서버가 채우는 필드·모르는 필드를 보내는 시나리오)."""
    api.clock.advance(GAP_SECONDS)
    return await api.post(actions_url(code), json=body)


async def when_update_action(api: Api, action_id: str, **overrides: object) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.put(f"{ACTIONS}/{action_id}", json=action_body(**overrides))


async def when_update_action_with_body(api: Api, action_id: str, body: object) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.put(f"{ACTIONS}/{action_id}", json=body)


async def when_update_action_as(
    api: Api, session: Session, action_id: str, **overrides: object
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await when_request_as(
        api, session, "PUT", f"{ACTIONS}/{action_id}", json=action_body(**overrides)
    )


async def when_delete_action(api: Api, action_id: str) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.delete(f"{ACTIONS}/{action_id}")


async def when_delete_action_as(api: Api, session: Session, action_id: str) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await when_request_as(api, session, "DELETE", f"{ACTIONS}/{action_id}")


async def when_get_action(api: Api, action_id: str) -> Response:
    return await api.get(f"{ACTIONS}/{action_id}")


async def when_list_actions(api: Api, code: str, **params: str | int) -> Response:
    return await api.get(actions_url(code), params=dict(params))


async def when_search_all_actions(api: Api, **params: str | int) -> Response:
    """폐지된 전역 검색 경로."""
    return await api.get(ACTIONS, params=dict(params))
