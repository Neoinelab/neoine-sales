"""Deal feature의 step(P1 R2): 등록·수정·조회·목록·이력·삭제와 확인.

Given은 공개 API로 사전 상태를 만든다(로그인한 사용자가 Owner, 연락처는 ContactDraft로 함께 만든다).
When은 HTTP API 하나, Then은 응답과 다시 조회한 결과만 본다. 공통 Then은 `steps/common.py`,
로그인은 `steps/auth.py`다.
"""

import re
from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.auth import ME, given_user_registered

if TYPE_CHECKING:
    from datetime import date, datetime

    from httpx import Response

    from tests.functional.conftest import Api

DEALS: Final = "/api/v1/deals"
CONTACTS: Final = "/api/v1/contacts"
BANT_LABELS: Final = "/api/v1/bant-labels"
CODE_PATTERN: Final = re.compile(r"^\d{8}-[A-Z0-9]{4}$")
CREATED_ENTRY: Final = ("created", "Deal 등록", "", "Deal 등록")

SYNC_MISMATCH: Final = "Status와 Forecast의 동기화가 맞지 않습니다."
OWNER_RESIGNED: Final = "퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요."
OWNER_NOT_SALES: Final = "Owner는 재직 중인 영업 담당자여야 합니다."
NOT_FOUND: Final = "Deal을 찾을 수 없습니다."
CONTACT_NOT_FOUND: Final = "연락처를 찾을 수 없습니다."
DUPLICATE_CONTACT: Final = "이미 등록된 연락처입니다."
DELETE_FORBIDDEN: Final = "본인 Deal 또는 admin만 삭제할 수 있습니다."
CODE_MISMATCH: Final = "Deal code가 일치하지 않습니다."
ISSUE_FAILED: Final = "Deal code를 발급하지 못했습니다. 다시 시도하세요."


def customer_draft(**overrides: object) -> dict[str, Any]:
    """고객 연락처 입력(ContactDraft). contact_id가 없으면 새 고객이거나 같은 사람 재사용이다."""
    return {
        "contact_id": None,
        "company": "네오인",
        "name": "김철수",
        "title": "팀장",
        "email": "kim@neoine.example",
        "phone": "010-1234-5678",
        **overrides,
    }


def partner_draft(**overrides: object) -> dict[str, Any]:
    return {
        "contact_id": None,
        "company": "한빛파트너스",
        "name": "이영희",
        "title": "이사",
        "email": "lee@hanbit.example",
        "phone": "02-123-4567",
        **overrides,
    }


async def given_my_user_id(api: Api) -> str:
    """로그인한 사용자의 id."""
    response = await api.get(ME)
    assert response.status_code == 200, response.text
    return str(response.json()["user_id"])


async def deal_body(api: Api, **overrides: object) -> dict[str, Any]:
    """등록 본문. 기본 Owner는 로그인한 사용자이고 overrides로 일부만 바꾼다."""
    values: dict[str, Any] = {
        "name": "ERP 구축",
        "owner_user_id": await given_my_user_id(api),
        "vendor_id": None,  # 등록된 Vendor·Solution의 id(없으면 선택 안 함)
        "solution_id": None,
        "users": None,
        "status_key": "prospecting",
        "forecast_key": "pipeline",
        "revenue_amount": 150_000_000,
        "revenue_date": "2026-06-30",
        "customer": customer_draft(),
        "partner": None,
        "quote": {"submitted": None, "submitted_date": None},
        "poc": {"state": None, "completed_date": None},
        "procurement": "",
        "bant": {"budget": None, "authority": None, "need": None, "timeline": None},
    }
    return {**values, **overrides}


async def given_deal(api: Api, **overrides: object) -> dict[str, Any]:
    """로그인한 사용자가 Deal을 등록해 두었다(응답 본문을 돌려준다). 시계는 1초 흐른다."""
    api.clock.advance(1)
    response = await when_register_deal(api, **overrides)
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


async def given_sales_owner(api: Api) -> str:
    """Owner가 될 수 있는 재직 영업 담당자의 id. 없으면 admin이 `deal-owner`를 등록한다.

    admin으로 로그인한 상태에서 부른다(등록 뒤에도 admin 로그인 상태가 유지된다).
    """
    options = await api.get("/api/v1/user-options", params={"role": "sales"})
    items = options.json()["items"]
    if items:
        return str(items[0]["id"])
    return await given_user_registered(api, login_id="deal-owner", role="sales")


async def given_deal_of_contacts(
    api: Api, *, customer_id: str, partner_id: str | None = None
) -> dict[str, Any]:
    """admin이 만든 연락처를 고객·파트너로 고른 Deal(Owner는 영업 담당자). 값은 그대로 보낸다."""
    owner = await given_sales_owner(api)
    listing = await api.get(CONTACTS, params={"limit": 200})
    rows = {row["id"]: row for row in listing.json()["items"]}

    def draft_of(row: dict[str, Any]) -> dict[str, Any]:
        keep = ("company", "name", "title", "email", "phone")
        return {"contact_id": row["id"], **{key: row[key] for key in keep}}

    return await given_deal(
        api,
        owner_user_id=owner,
        customer=draft_of(rows[customer_id]),
        partner=draft_of(rows[partner_id]) if partner_id else None,
    )


async def given_deal_deleted(api: Api, code: str) -> None:
    response = await when_delete_deal(api, code)
    assert response.status_code == 204, f"Given 실패 {response.status_code}: {response.text}"


async def given_label_id(api: Api, *, category: str, name: str) -> str:
    """기본 BANT Label의 id."""
    response = await api.get(BANT_LABELS)
    assert response.status_code == 200, response.text
    found = [
        label["id"]
        for label in response.json()
        if label["category"] == category and label["name"] == name
    ]
    assert len(found) == 1, (category, name)
    return str(found[0])


async def given_clock_at(api: Api, moment: datetime) -> None:
    """서버 시계를 주어진 시각으로 맞춘다(앞으로도 뒤로도)."""
    api.clock.advance((moment - api.clock.now()).total_seconds())  # 마이크로초까지 정확히 맞춘다


# --- When (HTTP API 하나) ---


async def when_register_deal(api: Api, **overrides: object) -> Response:
    return await api.post(DEALS, json=await deal_body(api, **overrides))


async def when_update_deal(api: Api, code: str, **patch: object) -> Response:
    return await api.patch(f"{DEALS}/{code}", json=patch)


async def when_get_deal(api: Api, code: str) -> Response:
    return await api.get(f"{DEALS}/{code}")


async def when_list_deals(api: Api, **params: str | int) -> Response:
    return await api.get(DEALS, params=dict(params))


async def when_list_history(api: Api, code: str, **params: str) -> Response:
    return await api.get(f"{DEALS}/{code}/history", params=dict(params))


async def when_delete_deal(api: Api, code: str, confirm_code: str | None = None) -> Response:
    typed = code if confirm_code is None else confirm_code
    return await api.delete(f"{DEALS}/{code}?confirm_code={typed}")


# --- Then (관찰 가능한 결과) ---


def then_code_is_issued_for_day(response: Response, day: date) -> None:
    code = str(response.json()["code"])
    assert CODE_PATTERN.match(code), code
    assert code.startswith(day.strftime("%Y%m%d") + "-"), (code, day)
    assert response.headers["location"] == f"{DEALS}/{code}"


def then_code_date_is_local_today(response: Response, api: Api) -> None:
    """code의 날짜가 서버 시계 시각의 프로세스 로컬 달력 날짜다(업무 날짜 = OS 로컬 시간대)."""
    then_code_is_issued_for_day(response, api.clock.now().astimezone().date())


def history_rows(response: Response) -> list[tuple[str, str, str, str]]:
    """이력 응답(최신순)을 오래된 순서의 (category, target, before, after)로."""
    return [
        (e["category"], e["target"], e["before"], e["after"]) for e in reversed(response.json())
    ]


async def then_history_is(api: Api, code: str, expected: list[tuple[str, str, str, str]]) -> None:
    """등록 이력 뒤에 expected가 순서대로 남아 있다(오래된 순서)."""
    response = await when_list_history(api, code)
    assert response.status_code == 200, response.text
    assert history_rows(response) == [CREATED_ENTRY, *expected]


async def then_deal_keeps(api: Api, code: str, **fields: object) -> None:
    """다시 조회한 Deal의 필드가 fields와 같다."""
    response = await when_get_deal(api, code)
    assert response.status_code == 200, response.text
    body = response.json()
    assert {key: body[key] for key in fields} == fields, body


async def then_deal_count_is(api: Api, count: int) -> None:
    response = await api.get(DEALS, params={"limit": 200})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == count


def list_codes(response: Response) -> list[str]:
    return [str(item["code"]) for item in response.json()["items"]]
