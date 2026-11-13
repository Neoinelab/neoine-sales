"""Deal 등록·폼 수정 라우터(`POST /deals`, `PATCH /deals/{code}`) 단위 테스트(DE).

FakeUseCases 위의 앱으로 상태 코드, Location, 응답 모양, 쓰기 권한, 요청 형식 오류를 본다.
필드 값 규칙은 유스케이스 테스트(`tests/unit/application/test_register_deal*.py` 등)가 맡는다.
"""

from typing import TYPE_CHECKING, Any, Final

import pytest

from app.domain.auth.principal import Role
from tests.factories_deal import seed_deal
from tests.fakes.catalog_seed import seed_catalog
from tests.fakes.use_cases import FakeUseCases
from tests.support.deal_payload import deal_payload
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users
from tests.unit.web.saved_report_http import clients, problem

if TYPE_CHECKING:
    from httpx import AsyncClient

URL: Final = "/api/v1/deals"
CODE: Final = "20261016-A001"
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
NOT_FOUND: Final = "Deal을 찾을 수 없습니다."
USERS: Final = {"kim": Role.SALES, "viewer": Role.USER, "anon": Role.USER}
PARTNER: Final = {
    "company": "한빛파트너스",
    "name": "이영희",
    "title": None,
    "email": None,
    "phone": None,
}


async def _use_cases_with_owner() -> FakeUseCases:
    """Owner(재직 sales)가 있는 Fake 앱 상태."""
    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)  # 기본 코드·BANT Label
    async with use_cases.uow as uow:
        await ensure_users(uow.users, OWNER_ID)
        await uow.commit()
    return use_cases


async def _use_cases_with_deal() -> FakeUseCases:
    """Owner와 Deal 하나(CODE)가 있는 Fake 앱 상태."""
    use_cases = await _use_cases_with_owner()
    async with use_cases.uow as uow:
        await seed_deal(uow, code=CODE, commit=False, owner_user_id=OWNER_ID)
        await uow.commit()
    return use_cases


def _stored_name(use_cases: FakeUseCases) -> str:
    deals = list(use_cases.uow.deals._items.values())
    return str(deals[0].details.name)


async def test_post_creates_the_deal_with_location_and_integer_ids_and_no_internal_id() -> None:
    """등록하면 201과 Location, 발급 code가 오고 응답에 내부 id가 없으며 id류는 정수다.

    테스트 코드: DE-001
    """
    # given: Owner(재직 sales)가 있고 sales KIM이 로그인했다
    use_cases = await _use_cases_with_owner()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 새 파트너를 포함해 Deal을 등록한다
        response = await c["kim"].post(URL, json=deal_payload(partner=PARTNER))

    # then: 201, Location이 /api/v1/deals/<code>, 응답 code가 Location과 같고 내부 id 필드가 없다
    assert response.status_code == 201, response.text
    body = response.json()
    assert response.headers["Location"] == f"{URL}/{body['code']}"
    assert "id" not in body
    assert type(body["owner_user_id"]) is int
    assert type(body["customer"]["id"]) is int
    assert type(body["revenue_amount"]) is int
    assert (body["name"], body["solution"], body["users"]) == ("ERP 구축", "S/4HANA", 10)
    assert body["active_partner"]["company"] == "한빛파트너스"
    assert [link["active"] for link in body["partner_links"]] == [True]
    assert len(use_cases.uow.deals._items) == 1


@pytest.mark.parametrize("who", ["viewer", "anon"])
async def test_post_by_a_read_only_user_or_anonymous_visitor_is_rejected(who: str) -> None:
    """user는 403(읽기 전용), 미인증은 401이며 새 BANT Label도 생기지 않는다.

    테스트 코드: DE-035
    """
    # given: Owner가 있고, 새 BANT 이름이 든 등록 본문
    use_cases = await _use_cases_with_owner()
    labels_before = len(await use_cases.uow.bant_labels.list())
    body = deal_payload(bant={"budget": {"name": "새 Label"}})
    async with clients(use_cases, USERS) as c:
        # when: user 또는 로그인하지 않은 사용자가 등록한다
        response = await c[who].post(URL, json=body)

    # then: user는 403 읽기 전용 문구, 미인증은 401이고 Deal·Label이 생기지 않는다
    if who == "viewer":
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    else:
        problem(response, 401, "unauthenticated")
    assert use_cases.uow.deals._items == {}
    assert len(await use_cases.uow.bant_labels.list()) == labels_before


@pytest.mark.parametrize(
    "overrides",
    [
        {"revenue_amount": "많이"},
        {"revenue_date": "30/06/2026"},
        {"owner_user_id": "x"},
        {"users": "10"},
        {"users": None},
        {"vendor_id": None},
        {"solution": 1},
        {"quote": {"submitted": "MAYBE"}},
        {"extra": 1},
        {"vendor": "SAP"},
        {"bant": {"budget": 5}},
    ],
    ids=[
        "amount-text",
        "date-format",
        "owner-text",
        "users-text",
        "users-null",
        "vendor-null",
        "solution-number",
        "quote-enum",
        "unknown-key",
        "old-vendor-text",
        "old-bare-bant-id",
    ],
)
async def test_post_with_a_malformed_body_is_a_request_validation_error_and_stores_nothing(
    overrides: dict[str, Any],
) -> None:
    """형식이 틀린 등록 본문은 422 request-validation이고 아무것도 저장되지 않는다.

    테스트 코드: DE-010
    """
    # given: Owner가 있고 형식이 틀린 필드가 든 본문
    use_cases = await _use_cases_with_owner()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 등록한다
        response = await c["kim"].post(URL, json=deal_payload(**overrides))

    # then: 422 request-validation이고 Deal이 없다
    problem(response, 422, "request-validation")
    assert use_cases.uow.deals._items == {}


async def test_post_without_users_or_vendor_id_keys_is_a_request_validation_error() -> None:
    """users·vendor_id 키가 없는 등록 본문은 422 request-validation이다.

    테스트 코드: DE-010
    """
    # given: Owner가 있고 users 또는 vendor_id 키를 뺀 본문
    use_cases = await _use_cases_with_owner()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        without_users = {k: v for k, v in deal_payload().items() if k != "users"}
        without_vendor = {k: v for k, v in deal_payload().items() if k != "vendor_id"}
        # when: 각각 등록한다
        first = await c["kim"].post(URL, json=without_users)
        second = await c["kim"].post(URL, json=without_vendor)

    # then: 둘 다 422 request-validation이고 Deal이 없다
    problem(first, 422, "request-validation")
    problem(second, 422, "request-validation")
    assert use_cases.uow.deals._items == {}


@pytest.mark.parametrize("sent", ["omitted", None, "", "   "])
async def test_post_without_a_solution_creates_the_deal_with_an_empty_solution(
    sent: str | None,
) -> None:
    """Solution을 생략·null·빈 값·공백으로 등록하면 201이고 응답·저장 Solution이 빈 값이다.

    테스트 코드: DE-115
    """
    # given: Owner가 있고 Solution이 생략되었거나 null·''·'   '인 본문
    use_cases = await _use_cases_with_owner()
    body = {k: v for k, v in deal_payload().items() if k != "solution"}
    if sent != "omitted":
        body["solution"] = sent
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 등록한다
        response = await c["kim"].post(URL, json=body)

    # then: 201이고 응답과 저장된 Solution이 ''다
    assert response.status_code == 201, response.text
    assert response.json()["solution"] == ""
    (stored,) = use_cases.uow.deals._items.values()
    assert stored.details.solution == ""


async def test_patch_with_a_null_vendor_is_an_invalid_value_error_and_keeps_the_vendor() -> None:
    """수정에서 vendor_id null은 422 invalid-value "Vendor를 선택하세요."이고 Vendor가 그대로다.

    테스트 코드: DE-116
    """
    # given: Vendor(기본)를 고른 Deal이 있다
    use_cases = await _use_cases_with_deal()
    before = next(iter(use_cases.uow.deals._items.values())).details.vendor_id
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: vendor_id를 null로 수정한다
        response = await c["kim"].patch(f"{URL}/{CODE}", json={"vendor_id": None})

    # then: 422 invalid-value, 문구 "Vendor를 선택하세요."이고 Vendor가 그대로다
    assert problem(response, 422, "invalid-value")["detail"] == "Vendor를 선택하세요."
    assert next(iter(use_cases.uow.deals._items.values())).details.vendor_id == before


@pytest.mark.parametrize("who", ["viewer", "anon"])
async def test_patch_by_a_read_only_user_or_anonymous_visitor_is_rejected(who: str) -> None:
    """user는 403(읽기 전용), 미인증은 401이고 Deal은 그대로다(본문 검증보다 먼저).

    테스트 코드: DE-042
    """
    # given: Deal이 있고, 형식도 틀린 본문
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        # when: user 또는 로그인하지 않은 사용자가 수정한다
        response = await c[who].patch(f"{URL}/{CODE}", json={"name": "바뀜", "extra": 1})

    # then: user는 403 읽기 전용 문구, 미인증은 401이고 이름이 그대로다
    if who == "viewer":
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    else:
        problem(response, 401, "unauthenticated")
    assert _stored_name(use_cases) != "바뀜"


async def test_patch_of_an_unknown_or_malformed_code_is_the_same_not_found() -> None:
    """없는 code와 형식이 틀린 code의 수정은 같은 404 문구다.

    테스트 코드: DE-041
    """
    # given: Deal 하나만 있는 앱
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 없는 code와 형식이 틀린 code를 각각 수정한다
        unknown = await c["kim"].patch(f"{URL}/20261016-ZZZZ", json={"name": "B"})
        malformed = await c["kim"].patch(f"{URL}/bad-code", json={"name": "B"})

    # then: 둘 다 404 not-found에 같은 문구다
    assert problem(unknown, 404, "not-found")["detail"] == NOT_FOUND
    assert problem(malformed, 404, "not-found")["detail"] == NOT_FOUND


async def test_patch_updates_only_the_sent_fields_and_returns_the_detail() -> None:
    """수정은 200과 Deal 상세를 돌려주고 보낸 필드만 바뀐다.

    테스트 코드: DE-036
    """
    # given: Deal이 있다
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        before = (await c["kim"].get(f"{URL}/{CODE}")).json()
        # when: 이름만 보내 수정한다
        response = await c["kim"].patch(f"{URL}/{CODE}", json={"name": "확장 프로젝트"})

    # then: 200이고 응답의 이름만 바뀌고 금액·Solution은 그대로다
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "확장 프로젝트"
    assert (body["revenue_amount"], body["solution"]) == (
        before["revenue_amount"],
        before["solution"],
    )
    assert body["code"] == CODE


async def test_an_empty_patch_body_changes_nothing() -> None:
    """빈 본문 {}은 아무것도 바꾸지 않는 200이다.

    테스트 코드: DE-037
    """
    # given: Deal이 있다
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        before = (await c["kim"].get(f"{URL}/{CODE}")).json()
        # when: 빈 본문으로 수정한다
        response = await c["kim"].patch(f"{URL}/{CODE}", json={})

    # then: 200이고 응답이 수정 전 상세와 같다(수정 시각 포함)
    assert response.status_code == 200, response.text
    assert response.json()["updated_at"] == before["updated_at"]
    assert response.json()["name"] == before["name"]


@pytest.mark.parametrize(
    "body",
    [
        {"revenue_amount": "많이"},
        {"revenue_date": "30/06/2026"},
        {"owner_user_id": "x"},
        {"users": "10"},
        {"solution": 1},
        {"extra": 1},
        {"code": "20261016-B001"},
        {"vendor": "SAP"},
        {"quote": None},
        {"poc": None},
        {"bant": None},
        {"bant": {"budget": 5}},
    ],
    ids=[
        "amount-text",
        "date-format",
        "owner-text",
        "users-text",
        "solution-number",
        "unknown-key",
        "code-change",
        "old-vendor-text",
        "quote-null",
        "poc-null",
        "bant-null",
        "old-bare-bant-id",
    ],
)
async def test_patch_with_a_malformed_body_is_a_request_validation_error_and_changes_nothing(
    body: dict[str, Any],
) -> None:
    """형식이 틀린 수정 본문(quote·poc·bant null 포함)은 422 request-validation이다.

    테스트 코드: DE-072, DE-062
    """
    # given: Deal이 있다
    use_cases = await _use_cases_with_deal()
    http: AsyncClient
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        http = c["kim"]
        before = (await http.get(f"{URL}/{CODE}")).json()
        # when: 형식이 틀린 본문으로 수정한다
        response = await http.patch(f"{URL}/{CODE}", json=body)
        after = (await http.get(f"{URL}/{CODE}")).json()

    # then: 422 request-validation이고 Deal이 그대로다
    problem(response, 422, "request-validation")
    assert after == before
