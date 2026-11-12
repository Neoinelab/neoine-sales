"""Dashboard 요약 라우터: FakeUseCases 위의 HTTP 계약과 응답 모양.

DB 없이 라우터·스키마·오류 매핑·권한을 확인한다. 집계 규칙은 application 테스트가 맡는다.
"""

import re
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories import make_deal
from tests.factories_auth import make_principal, make_user
from tests.factories_contact import make_customer
from tests.fakes.unit_of_work import FixedClock
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/dashboard/summary"
ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
COLUMN_KEYS = ["pipeline", "best", "most_likely", "commit", "won"]
STATUS_KEYS = [
    "prospecting",
    "introduction",
    "poc_preparation",
    "poc_completed",
    "technical_evaluation",
    "price_negotiation",
    "contract_completed",
]
SERVER_NOW = datetime.fromisoformat("2026-10-23T12:00:00+09:00")


@asynccontextmanager
async def _client(
    use_cases: FakeUseCases, *, role: Role | None = None
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookies = {}
    if role is not None:
        cookies[SESSION_COOKIE] = await use_cases.login_as(make_principal("root", role))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies=cookies,
    ) as http:
        yield http


def _seeded() -> FakeUseCases:
    from tests.fakes.catalog_seed import seed_catalog  # noqa: PLC0415

    use_cases = FakeUseCases()
    use_cases.clock = FixedClock(SERVER_NOW)
    seed_catalog(use_cases.uow)
    return use_cases


async def _with_kims_deal() -> FakeUseCases:
    """KIM이 담당자인 Deal 1건(금액 7, Expected Close 2026-06-30)이 있는 서버."""
    use_cases = _seeded()
    kim = make_user("kim", now=SERVER_NOW)
    await use_cases.uow.users.add(kim)
    customer = make_customer()
    await use_cases.uow.contacts.add(customer)
    deal = make_deal(
        SERVER_NOW,
        code="20261016-A001",
        customer_id=customer.id,
        forecast_key="pipeline",
        owner_user_id=kim.id,
        revenue_amount=7,
        revenue_date=date(2026, 6, 30),
    )
    await use_cases.uow.deals.add(deal)
    return use_cases


def _quarters(*values: object) -> list[tuple[str, object]]:
    return [("year", 2026), *(("quarter", value) for value in values)]


# ---- 권한과 입력 검증 (DSH-001~003) ----


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_can_read_the_summary(role: Role) -> None:
    """모든 역할이 요약을 읽고 숫자가 같다.

    테스트 코드: DSH-001
    """
    # given: KIM이 담당자인 Deal 1건(금액 7, Expected Close 2026-06-30)이 있는 서버
    use_cases = await _with_kims_deal()

    # when: 해당 역할로 로그인해 year=2026 요약을 조회한다
    async with _client(use_cases, role=role) as http:
        response = await http.get(URL, params={"year": 2026})

    # then: 200이고 Status 합계는 1건·7원이다
    assert response.status_code == 200, response.text
    assert response.json()["statuses"]["total"] == {"count": 1, "amount": 7}


async def test_anonymous_gets_401() -> None:
    """로그인하지 않으면 요약을 읽을 수 없다.

    테스트 코드: DSH-001
    """
    # given: KIM의 Deal 1건이 있는 서버
    use_cases = await _with_kims_deal()

    # when: 로그인하지 않고 요약을 조회한다
    async with _client(use_cases) as http:
        response = await http.get(URL, params={"year": 2026})

    # then: 401 unauthenticated다
    assert response.status_code == 401
    assert str(response.json()["type"]).endswith("unauthenticated")


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({}, 422),
        ({"year": "abc"}, 422),
        ({"year": 1899}, 422),
        ({"year": 10000}, 422),
        ({"year": 1900}, 200),
        ({"year": 9999}, 200),
    ],
    ids=["missing", "text", "1899", "10000", "1900", "9999"],
)
async def test_year_must_be_an_integer_from_1900_to_9999(
    params: dict[str, str | int], status: int
) -> None:
    """year 누락·문자·1899·10000은 422이고 1900·9999는 된다.

    테스트 코드: DSH-002
    """
    # given: 로그인한 사용자 (전제: sales)
    # when: 연도 값을 바꿔 조회한다
    async with _client(_seeded(), role=Role.SALES) as http:
        response = await http.get(URL, params=params)

    # then: 상태 코드가 기대와 같고 422는 request-validation이다
    assert response.status_code == status, response.text
    if status == 422:
        assert str(response.json()["type"]).endswith("request-validation")


@pytest.mark.parametrize(
    "params",
    [
        _quarters(0),
        _quarters(5),
        _quarters("x"),
        _quarters(1, 0),
        _quarters(1, 2, 3, 4, 2),
        [("year", 2026), ("month", 3)],
        [("year", 2026), ("vendor", "SAP")],
        [("year", 2026), ("unknown", "x")],
        [("year", 2026), ("forecast_key", "pipeline")],
        [("year", 2026), ("owner_user_id", "abc")],
        [("year", 2026), ("vendor_id", "abc")],
    ],
    ids=[
        "quarter-0",
        "quarter-5",
        "quarter-text",
        "quarter-1-and-0",
        "five-quarters",
        "month",
        "vendor",
        "unknown",
        "forecast-key",
        "owner-text",
        "vendor-id-text",
    ],
)
async def test_invalid_queries_are_request_validation_errors(
    params: list[tuple[str, object]],
) -> None:
    """분기 0·5·문자·5개, 모르는 키(month·vendor), 문자 id는 422 request-validation이다.

    테스트 코드: DSH-003
    """
    # given: 로그인한 사용자 (전제: admin)
    # when: 잘못된 쿼리로 조회한다
    async with _client(_seeded(), role=Role.ADMIN) as http:
        response = await http.get(URL, params=params)  # type: ignore[arg-type]

    # then: 422 request-validation이다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


@pytest.mark.parametrize("bad", ["0", "5", "x"])
async def test_a_quarter_outside_one_to_four_is_reported_at_the_quarter_location(bad: str) -> None:
    """분기 오류는 위치 quarter로 알려 준다.

    테스트 코드: DSH-003
    """
    # given: 로그인한 사용자 (전제: user)
    # when: 올바른 분기 1과 잘못된 분기를 함께 보내 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        response = await http.get(URL, params=_quarters(1, bad))  # type: ignore[arg-type]

    # then: 422이고 오류 위치가 쿼리 quarter다(범위 밖 숫자는 문서의 문구를 담는다)
    assert response.status_code == 422, response.text
    errors = response.json()["errors"]
    assert all(e["loc"][:2] == ["query", "quarter"] for e in errors), errors
    if bad != "x":
        assert "분기는 1~4 중에서 선택하세요." in errors[0]["msg"]


# ---- 응답 모양 (DSH-004~006) ----


async def test_response_has_the_documented_top_level_shape(local_tz: Callable[[str], None]) -> None:
    """응답은 일곱 키이고 as_of·today는 서버 시계의 시각·업무 날짜다.

    테스트 코드: DSH-004
    """
    # given: 서버 시계 2026-10-23 12:00(+09:00)
    local_tz("Asia/Seoul")
    use_cases = _seeded()

    # when: year=2026&quarter=4로 조회한다
    async with _client(use_cases, role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2026, "quarter": 4})).json()

    # then: 최상위 키가 정확히 일곱 개다
    assert set(body) == {
        "as_of",
        "today",
        "period",
        "forecasts",
        "statuses",
        "quarters",
        "attention",
    }
    # then: as_of는 서버 시계의 시각(오프셋 표기)이고 today는 업무 날짜다
    assert ISO_WITH_OFFSET.match(body["as_of"]), body["as_of"]
    assert datetime.fromisoformat(body["as_of"]) == SERVER_NOW
    assert body["today"] == "2026-10-23"


async def test_a_year_only_period_has_a_null_quarter_and_the_whole_year() -> None:
    """연만 주면 period는 quarter null·quarters []·연 전체다.

    테스트 코드: DSH-005
    """
    # when: year=2026으로 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2026})).json()

    # then: period가 연 전체다
    assert body["period"] == {
        "year": 2026,
        "quarter": None,
        "quarters": [],
        "from": "2026-01-01",
        "to": "2026-12-31",
    }


async def test_a_single_quarter_period_is_that_quarter() -> None:
    """분기 하나를 주면 period는 그 분기다.

    테스트 코드: DSH-005
    """
    # when: year=2026&quarter=2로 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2026, "quarter": 2})).json()

    # then: period가 Q2의 첫날~마지막 날이다
    assert body["period"] == {
        "year": 2026,
        "quarter": 2,
        "quarters": [2],
        "from": "2026-04-01",
        "to": "2026-06-30",
    }


async def test_several_quarters_give_a_period_from_the_first_start_to_the_last_end() -> None:
    """여러 분기는 오름차순 quarters와 첫 분기~마지막 분기 범위다.

    테스트 코드: DSH-006
    """
    # when: quarter=3&quarter=1로 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        response = await http.get(URL, params=_quarters(3, 1))  # type: ignore[arg-type]

    # then: quarter는 null, quarters는 [1, 3], 범위는 01-01~09-30이다
    assert response.status_code == 200, response.text
    assert response.json()["period"] == {
        "year": 2026,
        "quarter": None,
        "quarters": [1, 3],
        "from": "2026-01-01",
        "to": "2026-09-30",
    }


async def test_all_four_quarters_read_like_no_quarter() -> None:
    """넷 다 보내면 분기 없는 조회와 같다.

    테스트 코드: DSH-006
    """
    # when: 분기 1~4를 모두 보낸 조회와 분기 없는 조회를 한다
    async with _client(_seeded(), role=Role.USER) as http:
        four = await http.get(URL, params=_quarters(1, 2, 3, 4))  # type: ignore[arg-type]
        none = await http.get(URL, params={"year": 2026})

    # then: period가 같고 quarters는 []이다
    assert four.json()["period"] == none.json()["period"]
    assert four.json()["period"]["quarters"] == []


async def test_a_repeated_quarter_equals_one_quarter() -> None:
    """같은 분기를 두 번 보내면 한 번과 같다.

    테스트 코드: DSH-006
    """
    # when: quarter=2&quarter=2로 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        response = await http.get(URL, params=_quarters(2, 2))  # type: ignore[arg-type]

    # then: quarters는 [2]다
    assert response.json()["period"]["quarters"] == [2]
    assert response.json()["period"]["quarter"] == 2


# ---- 응답 각 부분의 모양 (DSH-007·010·014·017) ----


async def test_forecast_part_lists_columns_without_lost_and_cells_in_the_same_order() -> None:
    """Forecast 열은 Lost 없이 코드 순서이고 셀이 같은 순서다.

    테스트 코드: DSH-007
    """
    # when: year=2026으로 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        forecasts = (await http.get(URL, params={"year": 2026})).json()["forecasts"]

    # then: columns·cells·open_total 모양이 문서와 같다
    assert set(forecasts) == {"columns", "cells", "open_total"}
    assert [c["key"] for c in forecasts["columns"]] == COLUMN_KEYS
    assert set(forecasts["columns"][0]) == {"key", "name", "outcome", "order"}
    assert [c["key"] for c in forecasts["cells"]] == COLUMN_KEYS
    assert all(set(c) == {"key", "count", "amount"} for c in forecasts["cells"])
    assert forecasts["open_total"] == {"count": 0, "amount": 0}


async def test_status_part_lists_every_status_with_zero_and_a_total() -> None:
    """Status는 모든 코드를 순서대로 0과 함께 담고 합계가 있다.

    테스트 코드: DSH-010
    """
    # when: year=2026으로 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        statuses = (await http.get(URL, params={"year": 2026})).json()["statuses"]

    # then: items·total 모양이 문서와 같고 모두 0이다
    assert set(statuses) == {"items", "total"}
    assert [i["key"] for i in statuses["items"]] == STATUS_KEYS
    assert all(set(i) == {"key", "name", "order", "count", "amount"} for i in statuses["items"])
    assert all((i["count"], i["amount"]) == (0, 0) for i in statuses["items"])
    assert statuses["total"] == {"count": 0, "amount": 0}


async def test_quarters_part_always_has_four_quarters_with_their_date_range() -> None:
    """분기 행은 고른 분기와 무관하게 Q1~Q4이고 각 분기의 첫날·마지막 날을 가진다.

    테스트 코드: DSH-014
    """
    # when: year=2026&quarter=2로 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        quarters = (await http.get(URL, params={"year": 2026, "quarter": 2})).json()["quarters"]

    # then: Q1~Q4 네 행이고 날짜 범위와 키가 문서와 같다
    assert [q["quarter"] for q in quarters] == [1, 2, 3, 4]
    assert [(q["from"], q["to"]) for q in quarters] == [
        ("2026-01-01", "2026-03-31"),
        ("2026-04-01", "2026-06-30"),
        ("2026-07-01", "2026-09-30"),
        ("2026-10-01", "2026-12-31"),
    ]
    for q in quarters:
        assert set(q) == {"quarter", "from", "to", "cells", "open_total", "total"}
        assert [c["key"] for c in q["cells"]] == COLUMN_KEYS
        assert q["open_total"] == {"count": 0, "amount": 0}
        assert q["total"] == {"count": 0, "amount": 0}


async def test_the_quarter_rows_are_always_the_four_quarters_with_several_chosen() -> None:
    """여러 분기를 골라도 분기 행은 Q1~Q4 네 개다.

    테스트 코드: DSH-014
    """
    # when: quarter=1&quarter=3으로 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        body = (await http.get(URL, params=_quarters(1, 3))).json()  # type: ignore[arg-type]

    # then: 분기 행은 1~4다
    assert [row["quarter"] for row in body["quarters"]] == [1, 2, 3, 4]


async def test_attention_part_has_the_documented_fields() -> None:
    """주의 부분은 문서의 필드를 가지며 경고 기준은 기본 14일이다.

    테스트 코드: DSH-017
    """
    # when: year=2026으로 조회한다
    async with _client(_seeded(), role=Role.USER) as http:
        attention = (await http.get(URL, params={"year": 2026})).json()["attention"]

    # then: 필드 집합이 문서와 같고 stale_days는 14, 기한초과·미업데이트는 0이다
    assert set(attention) == {
        "stale_days",
        "overdue",
        "stale",
        "closing_this_month",
        "closing_this_quarter",
    }
    assert attention["stale_days"] == 14
    assert (attention["overdue"], attention["stale"]) == (0, 0)
    assert set(attention["closing_this_month"]) == {"year", "month", "count"}
    assert set(attention["closing_this_quarter"]) == {"year", "quarter", "count"}


# ---- openapi ----


async def test_the_openapi_declares_the_summary_path_as_get_only_with_four_params() -> None:
    """openapi에서 요약 경로는 GET만이고 파라미터는 네 개다.

    BDD 밖: 계약 문서(`openapi.json`)가 코드와 같은 모양인지 확인한다.
    """
    # given: 앱의 openapi 문서
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())

    # when: 요약 경로를 읽는다
    spec = app.openapi()

    # then: GET만 있고 파라미터 이름이 정확히 네 개다
    assert set(spec["paths"][URL]) == {"get"}
    names = {p["name"] for p in spec["paths"][URL]["get"]["parameters"]}
    assert names == {"year", "quarter", "owner_user_id", "vendor_id"}


async def test_the_openapi_declares_forecast_outcome_on_the_deal_list() -> None:
    """openapi에서 Deal 목록이 forecast_outcome 파라미터를 문서화한다.

    BDD 밖: Dashboard Drill-down이 쓰는 목록 조건이 계약에 남아 있는지 확인한다.
    """
    # given: 앱의 openapi 문서
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())

    # when: Deal 목록 경로의 파라미터를 읽는다
    spec = app.openapi()

    # then: forecast_outcome이 있다
    names = {p["name"] for p in spec["paths"]["/api/v1/deals"]["get"]["parameters"]}
    assert "forecast_outcome" in names
