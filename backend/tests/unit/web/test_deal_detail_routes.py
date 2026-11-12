"""Deal 상세·변경·이력·삭제 영향·삭제 라우트(DD): 상태 코드, 요청 형식, 역할, 폐지 경로.

Fake UoW 위의 실제 유스케이스를 ASGI로 부른다. 규칙(동기화·diff)은 application·domain이 본다.
"""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from app.domain.contact.values import ContactKind
from tests.factories_contact import make_contact
from tests.fakes.use_cases import FakeUseCases
from tests.support.deal_payload import deal_payload
from tests.support.user_ids import OWNER_ID
from tests.unit.web.deal_detail_http import (
    BASE,
    CODE,
    NOT_FOUND,
    READ_ONLY,
    clients,
    problem,
    seed,
    stored_deal_codes,
)

UUID = "6f1c1b3a-0000-4000-8000-000000000001"
ALL_ROLES = {"boss": Role.ADMIN, "owner": Role.SALES, "viewer": Role.USER}
DETAIL_KEYS = {
    "code",
    "name",
    "owner_user_id",
    "owner",
    "vendor",
    "solution",
    "users",
    "status_key",
    "forecast_key",
    "revenue_amount",
    "revenue_date",
    "customer",
    "active_partner",
    "partner_links",
    "quote",
    "poc",
    "procurement",
    "bant",
    "next_action",
    "last_updated_at",
    "risk",
    "status_changed_at",
    "status_days",
    "license_contract_count",
    "has_issued_license_contract",
    "created_at",
    "updated_at",
    "partner_history",
}
RETIRED_FIELDS = {"stage", "id", "customer_id", "partner_id", "revenue_currency", "registered_by"}
BAD_CODES = ["20261016-ZZZZ", "not-a-code", "20261016-a001", UUID]


def _change(field: str, value: object, **rest: object) -> dict[str, Any]:
    return {"change": {"field": field, "value": value}, **rest}


async def test_every_role_reads_the_detail_with_the_documented_fields() -> None:
    """어떤 역할이든 Deal 상세를 읽으면 문서화된 필드와 Owner·고객·파트너가 돌아온다.

    테스트 코드: DD-001
    """
    # given: Owner가 owner이고 고객·활성 파트너 연락처가 있는 Deal
    use_cases = FakeUseCases()
    partner = make_contact(ContactKind.PARTNER, company="코어테크", name="민지훈")
    customer = make_contact(ContactKind.CUSTOMER, company="한빛은행", name="정민수")
    await seed(use_cases, customer=customer, partner=partner)

    # when: admin·sales·user가 각각 상세를 읽는다
    async with clients(use_cases, ALL_ROLES) as c:
        responses = {name: await http.get(f"{BASE}/{CODE}") for name, http in c.items()}

    # then: 모두 200이고 키 집합이 문서와 같으며 Owner·고객·파트너·금액이 맞다
    for response in responses.values():
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == DETAIL_KEYS
        assert body["owner"]["id"] == body["owner_user_id"] == OWNER_ID
        assert body["customer"]["company"] == "한빛은행"
        assert body["active_partner"]["company"] == "코어테크"
        assert body["revenue_amount"] == 150_000_000
        assert isinstance(body["revenue_amount"], int)


async def test_the_detail_and_registration_responses_have_no_retired_fields() -> None:
    """상세·등록 응답에는 폐지된 필드가 없고 code·status_key·forecast_key가 있다.

    테스트 코드: DD-002
    """
    # given: 상세로 읽을 Deal이 있고 Owner 사용자가 있다
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 상세를 읽고 Deal을 새로 등록한다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        detail = await c["owner"].get(f"{BASE}/{CODE}")
        registered = await c["owner"].post(BASE, json=deal_payload())

    # then: 두 응답 모두 폐지된 키가 없고 새 키가 있다
    assert registered.status_code == 201, registered.text
    for body in (detail.json(), registered.json()):
        assert not RETIRED_FIELDS & set(body)
        assert {"code", "status_key", "forecast_key"} <= set(body)


@pytest.mark.parametrize("code", BAD_CODES)
async def test_an_unknown_or_malformed_code_detail_is_the_same_404(code: str) -> None:
    """없는 code와 형식이 틀린 code의 상세는 422가 아닌 같은 404 not-found다.

    테스트 코드: DD-005
    """
    # given: Deal 하나가 있고 admin이 로그인했다
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 없는 code, 형식이 틀린 code, 소문자 code, UUID로 상세를 읽는다
    async with clients(use_cases, {"boss": Role.ADMIN}) as c:
        response = await c["boss"].get(f"{BASE}/{code}")

    # then: 모두 404 not-found "Deal을 찾을 수 없습니다."다
    assert problem(response, 404, "not-found")["detail"] == NOT_FOUND


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", f"{BASE}/{UUID}"),
        ("PUT", f"{BASE}/{UUID}"),
        ("DELETE", f"{BASE}/{UUID}?confirm_code=x"),
        ("GET", f"{BASE}/by-code/20260101-AAAA"),
        ("POST", f"{BASE}/{UUID}/stage"),
        ("GET", f"{BASE}/{UUID}/stage-changes"),
        ("GET", f"{BASE}/pipeline"),
    ],
)
async def test_a_retired_deal_route_is_gone(method: str, path: str) -> None:
    """폐지된 Deal 경로는 본문이 있어도 404 또는 405다.

    테스트 코드: DD-007
    """
    # given: admin이 로그인했다
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 폐지된 경로를 부른다
    async with clients(use_cases, {"boss": Role.ADMIN}) as c:
        body: dict[str, Any] | None = {} if method in {"POST", "PUT"} else None
        response = await c["boss"].request(method, path, json=body)

    # then: 404 또는 405다
    assert response.status_code in {404, 405}, (response.status_code, response.text)


async def test_a_single_change_returns_exactly_the_documented_keys() -> None:
    """단일 변경 성공 응답은 deal·co_changed·notice 셋뿐이고 co_changed 항목은 field·from·to다.

    테스트 코드: DD-013
    """
    # given: 기회발굴·Pipeline Deal과 sales 요청자
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 계약완료로 매출금액·매출일과 함께 바꾼다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        response = await c["owner"].post(
            f"{BASE}/{CODE}/changes",
            json=_change(
                "status_key",
                "contract_completed",
                resolution={"revenue_amount": 900_000_000, "revenue_date": "2026-10-20"},
            ),
        )

    # then: 200이고 키가 정확히 셋이며 함께 바뀐 Forecast와 알림이 있다
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"deal", "co_changed", "notice"}
    assert body["co_changed"] == [{"field": "forecast_key", "from": "pipeline", "to": "won"}]
    assert body["notice"] == "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."
    assert body["deal"]["status_key"] == "contract_completed"
    assert body["deal"]["revenue_amount"] == 900_000_000


@pytest.mark.parametrize(
    "body",
    [
        _change("forecast_key", "best", resolution={"revenue_amount": "abc"}),
        _change("forecast_key", "best", resolution={"revenue_amount": 1.5}),
        _change("forecast_key", "best", resolution={"no_such_key": 1}),
        _change("forecast_key", "best", delete_license_contracts="yes"),
        _change("revenue_amount", "100"),
        _change("revenue_date", ""),
        {"resolution": {}},
        {"change": {"field": "forecast_key", "value": "best"}, "extra": 1},
    ],
)
async def test_a_malformed_single_change_request_is_a_422_request_validation(
    body: dict[str, Any],
) -> None:
    """단일 변경 요청 형식(resolution 포함)이 틀리면 422 request-validation이고 값이 그대로다.

    테스트 코드: DD-031
    """
    # given: Pipeline Deal과 sales 요청자
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 형식이 틀린 본문으로 단일 변경을 요청한다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        response = await c["owner"].post(f"{BASE}/{CODE}/changes", json=body)
        detail = (await c["owner"].get(f"{BASE}/{CODE}")).json()

    # then: 422 request-validation이고 Forecast는 Pipeline 그대로다
    problem(response, 422, "request-validation")
    assert detail["forecast_key"] == "pipeline"


async def test_users_cannot_be_changed_through_a_single_change() -> None:
    """단일 변경으로 users를 바꾸려 하면 422 request-validation이고 users는 그대로다.

    테스트 코드: DD-031
    """
    # given: users 10인 Deal과 sales 요청자
    use_cases = FakeUseCases()
    await seed(use_cases, users=10)

    # when: users를 5로 바꾸는 단일 변경을 요청한다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        response = await c["owner"].post(f"{BASE}/{CODE}/changes", json=_change("users", 5))
        detail = (await c["owner"].get(f"{BASE}/{CODE}")).json()

    # then: 422 request-validation이고 users는 10이다
    problem(response, 422, "request-validation")
    assert detail["users"] == 10


async def test_a_read_only_user_and_an_anonymous_visitor_cannot_change_a_deal() -> None:
    """user의 단일 변경은 403 읽기 전용 문구, 미인증은 401이고 값이 그대로다.

    테스트 코드: DD-033
    """
    # given: Pipeline Deal, user·미인증 요청자
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 각자 Forecast 변경을 요청한다
    async with clients(
        use_cases, {"viewer": Role.USER, "anon": Role.USER, "boss": Role.ADMIN}
    ) as c:
        denied = await c["viewer"].post(
            f"{BASE}/{CODE}/changes", json=_change("forecast_key", "best")
        )
        anonymous = await c["anon"].post(
            f"{BASE}/{CODE}/changes", json=_change("forecast_key", "best")
        )
        detail = (await c["boss"].get(f"{BASE}/{CODE}")).json()

    # then: user는 403 읽기 전용, 미인증은 401, Forecast는 Pipeline 그대로
    assert problem(denied, 403, "forbidden")["detail"] == READ_ONLY
    problem(anonymous, 401, "unauthenticated")
    assert detail["forecast_key"] == "pipeline"


@pytest.mark.parametrize("code", BAD_CODES)
async def test_a_single_change_of_an_unknown_deal_is_not_found(code: str) -> None:
    """없는 Deal·형식이 틀린 code의 단일 변경은 404 not-found다.

    테스트 코드: DD-034
    """
    # given: Deal 하나와 sales 요청자
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 없는 code로 Forecast 변경을 요청한다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        response = await c["owner"].post(
            f"{BASE}/{code}/changes", json=_change("forecast_key", "best")
        )

    # then: 404 not-found "Deal을 찾을 수 없습니다."다
    assert problem(response, 404, "not-found")["detail"] == NOT_FOUND


async def test_the_deletion_impact_is_readable_by_every_role_and_has_four_counts() -> None:
    """삭제 영향은 모든 역할이 읽고 이력·Action·첨부·계약 네 건수를 돌려준다.

    테스트 코드: DD-047
    """
    # given: 이력이 없는 시드 Deal
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 세 역할이 삭제 영향을 읽는다
    async with clients(use_cases, ALL_ROLES) as c:
        responses = [await http.get(f"{BASE}/{CODE}/deletion-impact") for http in c.values()]

    # then: 모두 200이고 네 건수가 0이다
    for response in responses:
        assert response.status_code == 200, response.text
        assert response.json() == {
            "history_count": 0,
            "action_count": 0,
            "attachment_count": 0,
            "license_contract_count": 0,
        }


@pytest.mark.parametrize("code", BAD_CODES)
async def test_the_deletion_impact_of_an_unknown_deal_is_not_found(code: str) -> None:
    """없는 Deal·형식이 틀린 code의 삭제 영향은 404 not-found다.

    테스트 코드: DD-049
    """
    # given: Deal 하나와 admin
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 없는 code의 삭제 영향을 읽는다
    async with clients(use_cases, {"boss": Role.ADMIN}) as c:
        response = await c["boss"].get(f"{BASE}/{code}/deletion-impact")

    # then: 404 not-found다
    assert problem(response, 404, "not-found")["detail"] == NOT_FOUND


@pytest.mark.parametrize("code", BAD_CODES)
async def test_the_history_of_an_unknown_deal_is_not_found(code: str) -> None:
    """없는 Deal·형식이 틀린 code의 이력은 404 not-found다.

    테스트 코드: DD-038
    """
    # given: Deal 하나와 admin
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 없는 code의 이력을 읽는다
    async with clients(use_cases, {"boss": Role.ADMIN}) as c:
        response = await c["boss"].get(f"{BASE}/{code}/history")

    # then: 404 not-found다
    assert problem(response, 404, "not-found")["detail"] == NOT_FOUND


async def test_an_unknown_history_category_is_a_422_request_validation() -> None:
    """모르는 이력 구분은 422 request-validation이고 12값은 모두 받는다.

    테스트 코드: DD-038
    """
    # given: Deal 하나와 admin
    use_cases = FakeUseCases()
    await seed(use_cases)
    known = [
        "created", "status", "forecast", "amount", "expectedClose", "owner",
        "partner", "contact", "bant", "action", "attachment", "other",
    ]  # fmt: skip

    # when: 모르는 구분과 12값을 차례로 요청한다
    async with clients(use_cases, {"boss": Role.ADMIN}) as c:
        unknown = await c["boss"].get(f"{BASE}/{CODE}/history", params={"category": "nope"})
        accepted = [
            (await c["boss"].get(f"{BASE}/{CODE}/history", params={"category": value})).status_code
            for value in known
        ]

    # then: 모르는 구분만 422이고 12값은 모두 200이다
    problem(unknown, 422, "request-validation")
    assert accepted == [200] * 12


async def test_every_role_reads_the_history() -> None:
    """어떤 역할이든 이력을 읽고, 변경이 있으면 최신 항목이 변경자와 함께 보인다.

    테스트 코드: DD-039
    """
    # given: sales가 Forecast를 바꿔 이력이 한 건 있다
    use_cases = FakeUseCases()
    await seed(use_cases)
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        changed = await c["owner"].post(
            f"{BASE}/{CODE}/changes", json=_change("forecast_key", "best")
        )
    assert changed.status_code == 200, changed.text

    # when: admin·sales·user가 각각 이력을 읽는다
    async with clients(use_cases, ALL_ROLES) as c:
        responses = [await http.get(f"{BASE}/{CODE}/history") for http in c.values()]

    # then: 모두 200이고 첫 항목은 Forecast 변경이며 변경자 이름이 있다
    for response in responses:
        assert response.status_code == 200, response.text
        first = response.json()[0]
        assert (first["category"], first["target"], first["after"]) == (
            "forecast",
            "Forecast",
            "Best",
        )
        assert set(first) == {
            "id",
            "deal_code",
            "at",
            "by",
            "category",
            "target",
            "before",
            "after",
        }
        assert first["by"]["name"]
        assert isinstance(first["id"], int)
        assert isinstance(first["by"]["id"], int)


async def test_the_owner_deletes_the_deal_with_the_matching_code() -> None:
    """Owner 영업이 code를 정확히 입력하면 204이고 Deal이 사라진다.

    테스트 코드: DD-050
    """
    # given: owner가 Owner인 Deal
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: owner가 정확한 code로 삭제를 요청하고 상세를 다시 읽는다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        response = await c["owner"].delete(f"{BASE}/{CODE}", params={"confirm_code": CODE})
        detail = await c["owner"].get(f"{BASE}/{CODE}")

    # then: 204(본문 없음)이고 상세는 404, 저장소에 Deal이 없다
    assert response.status_code == 204
    assert response.content == b""
    problem(detail, 404, "not-found")
    assert stored_deal_codes(use_cases) == set()


async def test_an_admin_deletes_a_deal_of_another_owner() -> None:
    """admin은 다른 Owner의 Deal도 지운다.

    테스트 코드: DD-051
    """
    # given: owner가 Owner인 Deal과 admin
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: admin이 정확한 code로 삭제한다
    async with clients(use_cases, {"boss": Role.ADMIN}) as c:
        response = await c["boss"].delete(f"{BASE}/{CODE}", params={"confirm_code": CODE})

    # then: 204이고 Deal이 없다
    assert response.status_code == 204
    assert stored_deal_codes(use_cases) == set()


async def test_another_sales_user_is_forbidden_before_the_confirmation_code_is_checked() -> None:
    """다른 영업은 확인 code가 틀리든 맞든 403 "본인 Deal…" 문구이고 Deal은 남는다.

    테스트 코드: DD-052
    """
    # given: owner가 Owner인 Deal과 다른 영업 other
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: other가 틀린 code와 맞는 code로 각각 삭제한다
    async with clients(use_cases, {"other": Role.SALES}) as c:
        wrong = await c["other"].delete(f"{BASE}/{CODE}", params={"confirm_code": "wrong"})
        right = await c["other"].delete(f"{BASE}/{CODE}", params={"confirm_code": CODE})

    # then: 둘 다 403 forbidden "본인 Deal 또는 admin만 삭제할 수 있습니다."이고 Deal은 남는다
    for response in (wrong, right):
        detail = problem(response, 403, "forbidden")["detail"]
        assert detail == "본인 Deal 또는 admin만 삭제할 수 있습니다."
    assert stored_deal_codes(use_cases) == {CODE}


async def test_a_read_only_user_cannot_delete_and_the_deal_stays() -> None:
    """user의 삭제는 403 읽기 전용 문구이고 Deal은 남는다.

    테스트 코드: DD-053
    """
    # given: Deal과 user 요청자
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: user가 정확한 code로 삭제한다
    async with clients(use_cases, {"viewer": Role.USER}) as c:
        response = await c["viewer"].delete(f"{BASE}/{CODE}", params={"confirm_code": CODE})

    # then: 403 forbidden 읽기 전용 문구이고 Deal은 남는다
    assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert stored_deal_codes(use_cases) == {CODE}


async def test_a_mismatched_confirmation_code_is_a_422_and_the_deal_stays() -> None:
    """확인 code가 정확히 같지 않으면(소문자·모자람·넘침) 422 invalid-value이고 Deal은 남는다.

    테스트 코드: DD-054
    """
    # given: owner가 Owner인 Deal
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 틀린 확인 code들로 삭제를 요청한다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        responses = [
            await c["owner"].delete(f"{BASE}/{CODE}", params={"confirm_code": typed})
            for typed in ("wrong", CODE.lower(), CODE[:-1], f"{CODE}X")
        ]

    # then: 모두 422 invalid-value "Deal code가 일치하지 않습니다."이고 Deal은 남는다
    for response in responses:
        assert problem(response, 422, "invalid-value")["detail"] == "Deal code가 일치하지 않습니다."
    assert stored_deal_codes(use_cases) == {CODE}


async def test_the_confirmation_code_query_is_required() -> None:
    """confirm_code 쿼리가 없으면 422 request-validation이고 Deal은 남는다.

    테스트 코드: DD-055
    """
    # given: owner가 Owner인 Deal
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: confirm_code 없이 삭제를 요청한다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        response = await c["owner"].delete(f"{BASE}/{CODE}")

    # then: 422 request-validation이고 Deal은 남는다
    problem(response, 422, "request-validation")
    assert stored_deal_codes(use_cases) == {CODE}


@pytest.mark.parametrize("code", ["20261016-ZZZZ", "not-a-code"])
async def test_deleting_an_unknown_deal_is_not_found_even_with_a_wrong_confirmation(
    code: str,
) -> None:
    """없는 Deal·형식이 틀린 code는 확인 code가 틀려도 404다.

    테스트 코드: DD-056
    """
    # given: Deal 하나와 sales 요청자
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 없는 code를 틀린 확인 code로 삭제한다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        response = await c["owner"].delete(f"{BASE}/{code}", params={"confirm_code": "wrong"})

    # then: 404 not-found "Deal을 찾을 수 없습니다."이고 기존 Deal은 남는다
    assert problem(response, 404, "not-found")["detail"] == NOT_FOUND
    assert stored_deal_codes(use_cases) == {CODE}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", f"{BASE}/{CODE}", None),
        ("GET", f"{BASE}/{CODE}/history", None),
        ("GET", f"{BASE}/{CODE}/deletion-impact", None),
        ("POST", f"{BASE}/{CODE}/changes", _change("forecast_key", "best")),
        ("DELETE", f"{BASE}/{CODE}?confirm_code={CODE}", None),
    ],
)
async def test_an_anonymous_visitor_is_unauthenticated_on_every_deal_route(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """로그인하지 않으면 상세·이력·삭제 영향·변경·삭제 모두 401이고 Deal이 그대로다.

    테스트 코드: DD-033, DD-047
    """
    # given: Deal 하나와 로그인하지 않은 방문자
    use_cases = FakeUseCases()
    await seed(use_cases)

    # when: 각 경로를 요청한다
    async with clients(use_cases, {"anon": Role.USER}) as c:
        response = await c["anon"].request(method, path, json=body)

    # then: 401 unauthenticated이고 Deal은 남는다
    problem(response, 401, "unauthenticated")
    assert stored_deal_codes(use_cases) == {CODE}
