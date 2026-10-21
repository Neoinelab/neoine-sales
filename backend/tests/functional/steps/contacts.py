"""연락처(contacts) feature의 step: 등록·수정·삭제·목록·회사별 조회와 확인.

Given은 공개 API로 사전 상태를 만들고(admin으로 로그인한 상태에서 호출), When은 HTTP API 하나를
호출하며, Then은 응답과 다시 조회한 목록만 본다. 공통 Then(상태 코드, Problem)은 `steps/common.py`,
로그인은 `steps/auth.py`, Deal을 통한 참조는 `steps/deals.py`를 쓴다.
"""

from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

CONTACTS: Final = "/api/v1/contacts"
COMPANIES: Final = f"{CONTACTS}/companies"
BY_COMPANY: Final = f"{CONTACTS}/by-company"

# 사용자에게 보이는 문구(계획 4.2)
WHITESPACE_MESSAGE: Final = "공백은 입력할 수 없습니다."
EMAIL_MESSAGE: Final = "이메일 형식이 올바르지 않습니다."
PHONE_MESSAGE: Final = "전화번호 형식이 올바르지 않습니다."
COMPANY_REQUIRED_MESSAGE: Final = "회사명을 입력하세요."
NAME_REQUIRED_MESSAGE: Final = "담당자명을 입력하세요."
DUPLICATE_MESSAGE: Final = "이미 등록된 연락처입니다."

CONTACT_FIELDS: Final = {
    "id",
    "kind",
    "company",
    "name",
    "title",
    "email",
    "phone",
    "created_at",
    "updated_at",
}
ROW_FIELDS: Final = CONTACT_FIELDS | {"deal_count"}

_DEFAULTS: Final = {
    "customer": {
        "company": "네오인",
        "name": "김철수",
        "title": "팀장",
        "email": "kim@neoine.example",
        "phone": "010-1234-5678",
    },
    "partner": {
        "company": "한빛파트너스",
        "name": "이영희",
        "title": "이사",
        "email": "lee@hanbit.example",
        "phone": "02-123-4567",
    },
}


def in_use_message(count: int) -> str:
    return f"연결된 Deal이 {count}건 있어 삭제할 수 없습니다."


def contact_payload(kind: str = "customer", **overrides: object) -> dict[str, Any]:
    """등록 본문(kind 포함). 기본은 유효한 더미 값이고 overrides로 일부만 바꾼다."""
    return {"kind": kind, **_DEFAULTS[kind], **overrides}


def update_payload(kind: str = "customer", **overrides: object) -> dict[str, Any]:
    """수정 본문(kind 없음)."""
    return {**_DEFAULTS[kind], **overrides}


def payload_without(field: str) -> dict[str, Any]:
    """필수 필드 하나가 빠진 등록 본문."""
    payload = contact_payload()
    del payload[field]
    return payload


def payload_with_kind(kind_value: str) -> dict[str, Any]:
    """kind 값만 바꾼 등록 본문(허용되지 않는 값을 보내 볼 때 쓴다)."""
    return {**contact_payload(), "kind": kind_value}


def payload_with_extra(field: str, value: object = "x") -> dict[str, Any]:
    """정의에 없는 필드가 하나 더 붙은 등록 본문."""
    return {**contact_payload(), field: value}


def update_payload_with_extra(field: str, value: object = "x") -> dict[str, Any]:
    """정의에 없는 필드(예: kind)가 하나 더 붙은 수정 본문."""
    return {**update_payload(), field: value}


# --- Given ---


async def given_contact(api: Api, kind: str = "customer", **overrides: object) -> dict[str, Any]:
    """admin이 연락처를 등록해 두었다(응답 본문을 돌려준다). 등록마다 시계를 전진시킨다."""
    api.clock.advance(60)  # 등록 시각(created_at)이 서로 다르도록
    response = await when_create_contact(api, contact_payload(kind, **overrides))
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


async def given_contacts(api: Api, *payloads: dict[str, Any]) -> list[dict[str, Any]]:
    """순서대로 연락처를 등록해 두었다."""
    created = []
    for payload in payloads:
        api.clock.advance(60)  # 등록 시각(created_at)이 서로 다르도록
        response = await when_create_contact(api, payload)
        assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
        created.append(dict(response.json()))
    return created


async def given_people(api: Api, count: int, *, company: str = "회사") -> list[dict[str, Any]]:
    """같은 회사의 서로 다른 고객 담당자 count명(이름 '사람1'..)."""
    return await given_contacts(
        api,
        *(
            contact_payload(company=company, name=f"사람{n}", email=None)
            for n in range(1, count + 1)
        ),
    )


# --- When (HTTP API 하나) ---


async def when_create_contact(api: Api, payload: dict[str, Any]) -> Response:
    return await api.post(CONTACTS, json=payload)


async def when_update_contact(api: Api, contact_id: object, payload: dict[str, Any]) -> Response:
    return await api.put(f"{CONTACTS}/{contact_id}", json=payload)


async def when_delete_contact(api: Api, contact_id: object) -> Response:
    return await api.delete(f"{CONTACTS}/{contact_id}")


async def when_search_contacts(api: Api, **params: str | int) -> Response:
    return await api.get(CONTACTS, params=params)  # type: ignore[arg-type]


async def when_list_companies(api: Api, **params: str) -> Response:
    return await api.get(COMPANIES, params=params)  # type: ignore[arg-type]


async def when_list_contacts_of_company(api: Api, **params: str) -> Response:
    return await api.get(BY_COMPANY, params=params)  # type: ignore[arg-type]


# --- Then ---


def then_contact_has_the_documented_fields(response: Response, *, row: bool = False) -> None:
    assert set(response.json()) == (ROW_FIELDS if row else CONTACT_FIELDS), response.json()


def then_contact_values_are(response: Response, **expected: object) -> None:
    """응답 본문의 필드가 expected와 같다(나머지 필드는 보지 않는다)."""
    body = response.json()
    assert {key: body[key] for key in expected} == expected, body


def then_location_points_to_the_created(response: Response) -> None:
    assert response.headers["location"] == f"{CONTACTS}/{response.json()['id']}"


def then_detail_is(response: Response, detail: str) -> None:
    assert response.json()["detail"] == detail, response.json()


def then_item_companies_are(response: Response, companies: list[str]) -> None:
    """목록 응답 items의 회사명이 순서까지 같다."""
    assert [item["company"] for item in response.json()["items"]] == companies


def then_item_names_are(response: Response, names: list[str]) -> None:
    assert [item["name"] for item in response.json()["items"]] == names


def then_page_is(response: Response, *, total: int, offset: int, limit: int) -> None:
    body = response.json()
    assert set(body) == {"items", "total", "offset", "limit"}, set(body)
    assert (body["total"], body["offset"], body["limit"]) == (total, offset, limit)


def then_every_item_has_the_documented_fields(response: Response) -> None:
    for item in response.json()["items"]:
        assert set(item) == ROW_FIELDS, item


def then_every_row_has_the_documented_fields(response: Response) -> None:
    """GET /contacts/by-company 본문(배열)의 각 행이 목록 항목과 같은 필드를 가진다."""
    for row in response.json():
        assert set(row) == ROW_FIELDS, row


def then_row_deal_counts_are(response: Response, expected: dict[int, int]) -> None:
    """GET /contacts/by-company 본문(배열)의 id별 deal_count가 expected와 같다."""
    assert {row["id"]: row["deal_count"] for row in response.json()} == expected


def then_deal_counts_are(response: Response, expected: dict[int, int]) -> None:
    """items의 id별 deal_count가 expected와 같다."""
    counts = {item["id"]: item["deal_count"] for item in response.json()["items"]}
    assert counts == expected


def then_companies_are(response: Response, companies: list[str]) -> None:
    """GET /contacts/companies 본문(문자열 배열)이 순서까지 같다."""
    assert response.json() == companies


def then_contact_names_are(response: Response, names: list[str]) -> None:
    """GET /contacts/by-company 본문(연락처 배열)의 담당자명이 순서까지 같다."""
    assert [row["name"] for row in response.json()] == names


async def then_contact_is_listed(api: Api, contact_id: int, *, company: str | None = None) -> None:
    """admin 목록에 해당 연락처가 있다(회사명을 주면 회사명도 같다)."""
    found = [
        item
        for item in (await when_search_contacts(api, limit=200)).json()["items"]
        if item["id"] == contact_id
    ]
    assert len(found) == 1, contact_id
    if company is not None:
        assert found[0]["company"] == company


async def then_contact_is_not_listed(api: Api, contact_id: int) -> None:
    items = (await when_search_contacts(api, limit=200)).json()["items"]
    assert contact_id not in [item["id"] for item in items]


async def then_total_contacts_are(api: Api, total: int) -> None:
    assert (await when_search_contacts(api, limit=1)).json()["total"] == total
