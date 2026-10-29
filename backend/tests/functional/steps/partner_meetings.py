"""파트너 Activity feature의 step: 미팅 기록의 일괄 입력·목록·검색·수정·삭제와 Deal 선택지.

Given은 공개 API로 사전 상태를 만든다. 파트너 연락처는 Deal 등록의 `partner`로 함께 만들고(admin이
로그인한 상태에서 호출, 끝나도 admin 상태), 미팅은 지금 로그인한 사용자 또는 주어진 세션의 사용자가
남긴다. When은 HTTP API 하나, Then은 응답과 다시 조회한 결과만 본다.
공통 Then은 `steps/common.py`다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.common import then_status_is
from tests.functional.steps.deals import DEALS, given_sales_owner, partner_draft
from tests.functional.steps.forecast import given_forecast_deal
from tests.functional.steps.users import Session, when_request_as

if TYPE_CHECKING:
    from collections.abc import Sequence

    from httpx import Response

    from tests.functional.conftest import Api

MEETINGS: Final = "/api/v1/partner-meetings"
DEAL_OPTIONS: Final = f"{MEETINGS}/deal-options"
HANBIT: Final = "한빛파트너스"
GAP_SECONDS: Final = 60

COMPANY_NOT_FOUND: Final = "등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요."
DEAL_NOT_FOUND: Final = "Deal을 찾을 수 없습니다. 목록에서 다시 선택하세요."
DEAL_NOT_LINKED: Final = "선택한 파트너와 연결된 Deal이 아닙니다."
CONTENT_REQUIRED: Final = "미팅 내용을 입력하세요."
NO_ITEMS: Final = "입력한 미팅이 없습니다."
EDIT_FORBIDDEN: Final = "본인 미팅 기록 또는 admin만 수정할 수 있습니다."
DELETE_FORBIDDEN: Final = "본인 미팅 기록 또는 admin만 삭제할 수 있습니다."
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
NOT_FOUND: Final = "미팅 기록을 찾을 수 없습니다."
DATE_RANGE_REVERSED: Final = "미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다."
OUT_OF_BOUNDS: Final = "미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"
MEETING_KEYS: Final = {
    "id",
    "partner_company",
    "deal",
    "meeting_date",
    "content",
    "author",
    "created_at",
    "updated_at",
}


def meeting_item(code: str, *, company: str = HANBIT, **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    """요청 항목 하나(MeetingItemRequest). 기본은 한빛파트너스와 2027-03-01의 킥오프 미팅이다."""
    return {
        "partner_company": company,
        "deal_code": code,
        "meeting_date": "2027-03-01",
        "content": "킥오프 미팅",
        **overrides,
    }


# --- Given ---


async def given_partner_deal(
    api: Api,
    *,
    company: str = HANBIT,
    name: str = "ERP 구축",
    contact: str = "이영희",
    forecast: str = "pipeline",
    **overrides: Any,  # noqa: ANN401 - Deal 등록 필드를 그대로 넘긴다
) -> dict[str, Any]:
    """company의 담당자 contact가 활성 파트너인 Deal(영업 담당자가 Owner, admin 로그인 상태)."""
    owner = await given_sales_owner(api)
    return await given_forecast_deal(
        api,
        owner=owner,
        forecast=forecast,
        name=name,
        partner=partner_draft(
            company=company, name=contact, email=f"c{sum(map(ord, contact))}@partner.test"
        ),
        **overrides,
    )


async def given_meeting(api: Api, code: str, **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    """지금 로그인한 사용자가 미팅을 남겨 두었다(시계가 전진한다). 응답 항목을 돌려준다."""
    api.clock.advance(GAP_SECONDS)
    response = await api.post(MEETINGS, json={"items": [meeting_item(code, **overrides)]})
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json()["items"][0])


async def given_meeting_by(
    api: Api,
    session: Session,
    code: str,
    **overrides: Any,  # noqa: ANN401
) -> dict[str, Any]:
    """주어진 세션의 사용자가 미팅을 남겨 두었다(시계가 전진한다)."""
    api.clock.advance(GAP_SECONDS)
    response = await when_request_as(
        api, session, "POST", MEETINGS, json={"items": [meeting_item(code, **overrides)]}
    )
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json()["items"][0])


async def given_many_meetings(api: Api, code: str, count: int) -> list[dict[str, Any]]:
    """지금 로그인한 사용자가 미팅 count건을 한 번에 남겨 두었다(내용 "기록 NN", 3월 1일부터)."""
    items = [
        meeting_item(code, content=f"기록 {number:02d}", meeting_date=f"2027-03-{number + 1:02d}")
        for number in range(count)
    ]
    response = await api.post(MEETINGS, json={"items": items})
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return list(response.json()["items"])


# --- When (HTTP API 하나) ---


async def when_register_meetings(api: Api, items: Sequence[dict[str, Any]]) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.post(MEETINGS, json={"items": list(items)})


async def when_register_meetings_as(
    api: Api, session: Session, items: Sequence[dict[str, Any]]
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await when_request_as(api, session, "POST", MEETINGS, json={"items": list(items)})


async def when_register_with_body(api: Api, body: object) -> Response:
    """본문을 가공 없이 보낸다(잘못된 형식 시나리오)."""
    return await api.post(MEETINGS, json=body)


async def when_list_meetings(api: Api, **params: str | int) -> Response:
    return await api.get(MEETINGS, params=dict(params))


async def when_update_meeting(api: Api, meeting_id: object, body: dict[str, Any]) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.put(f"{MEETINGS}/{meeting_id}", json=body)


async def when_update_meeting_as(
    api: Api, session: Session, meeting_id: object, body: dict[str, Any]
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await when_request_as(api, session, "PUT", f"{MEETINGS}/{meeting_id}", json=body)


async def when_delete_meeting(api: Api, meeting_id: object) -> Response:
    return await api.delete(f"{MEETINGS}/{meeting_id}")


async def when_delete_meeting_as(api: Api, session: Session, meeting_id: object) -> Response:
    return await when_request_as(api, session, "DELETE", f"{MEETINGS}/{meeting_id}")


async def when_get_deal_options(api: Api, company: str) -> Response:
    return await api.get(DEAL_OPTIONS, params={"company": company})


async def when_get_deletion_impact(api: Api, code: str) -> Response:
    return await api.get(f"{DEALS}/{code}/deletion-impact")


# --- Then ---


def contents_of(response: Response) -> list[str]:
    return [item["content"] for item in response.json()["items"]]


def then_contents_are(response: Response, expected: Sequence[str]) -> None:
    """목록 응답의 미팅 내용이 순서까지 같다."""
    then_status_is(response, 200)
    assert contents_of(response) == list(expected), response.json()


def then_page_is(response: Response, *, total: int, offset: int, limit: int) -> None:
    body = response.json()
    assert (body["total"], body["offset"], body["limit"]) == (total, offset, limit), body


def then_meeting_has_the_documented_fields(item: dict[str, Any]) -> None:
    assert set(item) == MEETING_KEYS, set(item) ^ MEETING_KEYS


def then_errors_are(
    response: Response, expected: Sequence[tuple[Sequence[str | int], str]]
) -> None:
    """422 invalid-value 응답의 errors[]가 (위치, 문구) 순서까지 같다."""
    body = response.json()
    assert [(e["location"], e["message"]) for e in body["errors"]] == [
        (list(location), message) for location, message in expected
    ], body


async def then_all_contents_are(api: Api, expected: Sequence[str]) -> None:
    """저장된 미팅 전부(한 페이지 200건)의 내용을 다시 조회해 순서까지 확인한다."""
    then_contents_are(await api.get(MEETINGS, params={"limit": 200}), expected)
