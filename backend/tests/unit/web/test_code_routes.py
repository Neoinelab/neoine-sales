"""Status·Forecast 코드 라우터(CD-001, CD-008, CD-009, CD-036, CD-046): FakeUseCases 위의 HTTP 계약.

DB 없이 라우터·스키마·오류 매핑·권한을 확인한다. 유스케이스는 기본 코드를 넣은 Fake UoW 위에서 돈다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.code.values import CodeKind
from tests.fakes.catalog_seed import DEFAULT_FORECASTS, DEFAULT_STATUSES, seed_catalog
from tests.fakes.use_cases import FakeUseCases
from tests.support.catalog import code_by_key
from tests.unit.web.vendor_http import client_for, problem

if TYPE_CHECKING:
    from httpx import AsyncClient

URL = "/api/v1/codes"
CODE_KEYS = {
    "id",
    "kind",
    "key",
    "name",
    "order",
    "locked",
    "outcome",
    "probability_hint",
    "usage_count",
}
ADMIN_ONLY = "관리자 권한이 필요합니다"


def _seeded() -> FakeUseCases:
    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    return use_cases


async def _snapshot(use_cases: FakeUseCases) -> list[tuple[str, str, str, int]]:
    """두 종류 코드의 (종류, key, 이름, 순서) 전체."""
    rows = []
    for kind in CodeKind:
        rows += [
            (kind.value, c.key.value, c.name, c.order) for c in await use_cases.uow.codes.list(kind)
        ]
    return rows


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_reads_the_default_codes(role: Role) -> None:
    """어떤 역할이든 기본 Status 7개·Forecast 6개를 순서대로 받는다.

    테스트 코드: CD-001
    """
    # given: 기본 코드와 해당 역할로 로그인한 클라이언트
    async with client_for(_seeded(), role=role) as http:
        # when: GET /codes
        response = await http.get(URL)

    # then: 200이고 두 목록이 기본 순서이며 응답 필드는 정해진 8개다
    assert response.status_code == 200, response.text
    body = response.json()
    assert [c["key"] for c in body["statuses"]] == [key for key, _ in DEFAULT_STATUSES]
    assert [c["key"] for c in body["forecasts"]] == [key for key, *_ in DEFAULT_FORECASTS]
    assert set(body["statuses"][0]) == CODE_KEYS - {"usage_count"}
    assert [c["locked"] for c in body["forecasts"]] == [True, False, False, False, True, True]


@pytest.mark.parametrize("query", ["", "?kind=deal", "?kind="], ids=["missing", "unknown", "empty"])
async def test_usage_with_a_missing_or_invalid_kind_is_422(query: str) -> None:
    """사용 현황 요청의 kind가 없거나 잘못되면 422 request-validation이다.

    테스트 코드: CD-008
    """
    # given: admin으로 로그인
    async with client_for(_seeded()) as http:
        # when: kind 없이, 또는 잘못된 kind로 GET /codes/usage
        response = await http.get(f"{URL}/usage{query}")

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_usage_with_a_valid_kind_returns_only_that_kind_with_counts() -> None:
    """kind를 주면 그 종류의 코드만 사용 수와 함께 돌려준다.

    테스트 코드: CD-006
    """
    # given: admin으로 로그인
    async with client_for(_seeded()) as http:
        # when: GET /codes/usage?kind=forecast
        response = await http.get(f"{URL}/usage", params={"kind": "forecast"})

    # then: 200이고 Forecast 6개가 사용 수 0과 함께 기본 순서로 온다
    assert response.status_code == 200, response.text
    body = response.json()
    assert [c["key"] for c in body] == [key for key, *_ in DEFAULT_FORECASTS]
    assert {c["kind"] for c in body} == {"forecast"}
    assert all(set(c) == CODE_KEYS and c["usage_count"] == 0 for c in body)


async def test_create_code_returns_201_with_location_and_the_documented_body() -> None:
    """Status를 추가하면 201과 Location, 새 코드 본문이 돌아온다.

    테스트 코드: CD-009
    """
    # given: admin으로 로그인, 기본 코드
    use_cases = _seeded()
    async with client_for(use_cases) as http:
        # when: POST /codes {"kind": "status", "name": "Final Review"}
        response = await http.post(URL, json={"kind": "status", "name": "Final Review"})

    # then: 201, Location, 본문 값이 문서와 같고 Status 목록 맨 끝에 놓인다
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == CODE_KEYS
    assert response.headers["location"] == f"{URL}/{body['id']}"
    assert type(body["id"]) is int
    assert (body["key"], body["name"], body["order"]) == ("final_review", "Final Review", 8)
    assert (body["locked"], body["outcome"], body["usage_count"]) == (False, "open", 0)
    assert body["probability_hint"] is None
    assert (await use_cases.uow.codes.list(CodeKind.STATUS))[-1].id == body["id"]


@pytest.mark.parametrize("bad", ["7", 1.5, True, ["1"]], ids=["str", "float", "bool", "list"])
async def test_reorder_with_non_integer_ids_is_422_request_validation(bad: object) -> None:
    """순서 목록의 id가 정수가 아니면 422 request-validation이다.

    테스트 코드: CD-036
    """
    # given: admin으로 로그인
    async with client_for(_seeded()) as http:
        # when: ordered_ids에 정수가 아닌 값을 담아 PUT /codes/order
        response = await http.put(f"{URL}/order", json={"kind": "status", "ordered_ids": [bad]})

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_reorder_with_integer_ids_applies_the_sent_order() -> None:
    """정수 id 전체 목록은 보낸 순서 그대로 받아들인다.

    테스트 코드: CD-036
    """
    # given: admin으로 로그인, 거꾸로 된 Status 전체 id
    use_cases = _seeded()
    ids = [c.id for c in await use_cases.uow.codes.list(CodeKind.STATUS)]
    async with client_for(use_cases) as http:
        # when: PUT /codes/order
        response = await http.put(
            f"{URL}/order", json={"kind": "status", "ordered_ids": list(reversed(ids))}
        )

    # then: 200이고 응답 순서가 보낸 순서이며 order는 1부터다
    assert response.status_code == 200, response.text
    assert [c["id"] for c in response.json()] == list(reversed(ids))
    assert [c["order"] for c in response.json()] == list(range(1, 8))


async def _admin_requests(
    use_cases: FakeUseCases,
) -> list[tuple[str, str, dict[str, object] | None]]:
    introduction = await code_by_key(use_cases.uow, CodeKind.STATUS, "introduction")
    completed = await code_by_key(use_cases.uow, CodeKind.STATUS, "poc_completed")
    ids = [c.id for c in await use_cases.uow.codes.list(CodeKind.STATUS)]
    return [
        ("GET", f"{URL}/usage?kind=status", None),
        ("POST", URL, {"kind": "status", "name": "Final Review"}),
        ("PATCH", f"{URL}/{introduction.id}", {"name": "소개"}),
        ("PUT", f"{URL}/order", {"kind": "status", "ordered_ids": list(reversed(ids))}),
        ("DELETE", f"{URL}/{completed.id}", None),
    ]


async def _send(http: AsyncClient, request: tuple[str, str, dict[str, object] | None]) -> int:
    method, url, body = request
    return (await http.request(method, url, json=body)).status_code


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_management_requests_are_403_for_non_admin_and_change_nothing(role: Role) -> None:
    """sales·user의 관리 요청은 403 관리자 문구이고 아무것도 바뀌지 않는다.

    테스트 코드: CD-046
    """
    # given: sales 또는 user로 로그인, 변경 전 코드 상태
    use_cases = _seeded()
    before = await _snapshot(use_cases)
    async with client_for(use_cases, role=role) as http:
        # when: 사용 현황·추가·이름 변경·순서 변경·삭제를 각각 요청한다
        responses = [
            await http.request(method, url, json=body)
            for method, url, body in await _admin_requests(use_cases)
        ]

    # then: 모두 403 forbidden 관리자 문구이고 코드 수·이름·순서가 그대로다
    for response in responses:
        assert problem(response, 403, "forbidden")["detail"] == ADMIN_ONLY
    assert await _snapshot(use_cases) == before


async def test_management_requests_are_401_without_a_session() -> None:
    """로그인하지 않은 관리 요청은 401이다(공통 인증, 코드는 바뀌지 않는다).

    테스트 코드: CD-046
    """
    # given: 세션 없는 클라이언트
    use_cases = _seeded()
    before = await _snapshot(use_cases)
    async with client_for(use_cases, role=None) as http:
        # when: 관리 요청 5종을 보낸다
        statuses = [await _send(http, r) for r in await _admin_requests(use_cases)]

    # then: 모두 401이고 코드는 그대로다
    assert statuses == [401] * 5
    assert await _snapshot(use_cases) == before
