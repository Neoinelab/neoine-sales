"""Forecast 실시간 요약 라우터: FakeUseCases 위의 HTTP 계약, 응답 모양, 판정 순서.

DB 없이 라우터·스키마·오류 매핑·권한을 확인한다.
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
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/forecast/summary"
ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
COLUMN_KEYS = ["pipeline", "best", "most_likely", "commit", "won"]
SERVER_NOW = datetime.fromisoformat("2026-10-15T09:00:00+09:00")


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


async def _with_kims_pipeline_deal() -> FakeUseCases:
    """KIM의 Pipeline Deal 1건(금액 7, Expected Close 2026-11-15)이 있는 서버."""
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
        revenue_date=date(2026, 11, 15),
    )
    await use_cases.uow.deals.add(deal)
    return use_cases


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_reads_the_same_summary(role: Role) -> None:
    """admin·sales·user 모두 실시간 요약을 읽고 숫자가 같다.

    테스트 코드: FC-001
    """
    # given: KIM의 Pipeline Deal 1건(금액 7)이 있는 서버
    use_cases = await _with_kims_pipeline_deal()
    # when: 해당 역할로 로그인해 year=2026 요약을 읽는다
    async with _client(use_cases, role=role) as http:
        response = await http.get(URL, params={"year": 2026})
    # then: 200이고 Open 합계는 (1건, 7원)이다
    assert response.status_code == 200, response.text
    assert response.json()["total"]["open_total"] == {"count": 1, "amount": 7}


async def test_anonymous_gets_401() -> None:
    """로그인하지 않으면 요약을 읽을 수 없다.

    테스트 코드: FC-001
    """
    # given: KIM의 Pipeline Deal 1건이 있는 서버
    use_cases = await _with_kims_pipeline_deal()
    # when: 로그인하지 않고 요약을 읽는다
    async with _client(use_cases) as http:
        response = await http.get(URL, params={"year": 2026})
    # then: 401 unauthenticated다
    assert response.status_code == 401
    assert str(response.json()["type"]).endswith("unauthenticated")


async def test_response_has_the_documented_shape_with_server_time() -> None:
    """응답은 basis live, 서버 현재 시각(오프셋 포함), 분기 양끝 날짜를 담는다.

    테스트 코드: FC-010
    """
    # given: 서버 시각이 2026-10-15T09:00+09:00인 서버
    use_cases = _seeded()
    # when: year=2026&quarter=4로 요약을 읽는다
    async with _client(use_cases, role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2026, "quarter": 4})).json()
    # then: 키·basis·snapshot_period·as_of(오프셋 있는 서버 시각)·period·열이 문서와 같다
    assert set(body) == {"basis", "as_of", "snapshot_period", "period", "columns", "rows", "total"}
    assert body["basis"] == "live"
    assert body["snapshot_period"] is None
    assert ISO_WITH_OFFSET.match(body["as_of"]), body["as_of"]
    assert datetime.fromisoformat(body["as_of"]) == SERVER_NOW
    assert body["period"] == {
        "year": 2026,
        "quarter": 4,
        "month": None,
        "from": "2026-10-01",
        "to": "2026-12-31",
    }
    assert [c["key"] for c in body["columns"]] == COLUMN_KEYS
    assert set(body["columns"][0]) == {"key", "name", "outcome", "order"}
    assert [c["outcome"] for c in body["columns"]][-1] == "won"


async def test_month_period_has_the_month_range() -> None:
    """윤년 2월을 월로 읽으면 기간이 2-01~2-29이고 분기는 없다.

    테스트 코드: FC-010
    """
    # given: 서버 시각이 2026-10-15인 서버
    use_cases = _seeded()
    # when: year=2028&month=2로 요약을 읽는다
    async with _client(use_cases, role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2028, "month": 2})).json()
    # then: 기간은 {2028, null, 2, 2028-02-01, 2028-02-29}다
    assert body["period"] == {
        "year": 2028,
        "quarter": None,
        "month": 2,
        "from": "2028-02-01",
        "to": "2028-02-29",
    }


async def test_a_year_without_deals_returns_every_column_and_zero_totals() -> None:
    """Deal이 없는 기간도 모든 열과 0인 합계를 돌려준다.

    테스트 코드: FC-009
    """
    # given: 2031년 Expected Close인 Deal이 없는 서버
    use_cases = await _with_kims_pipeline_deal()
    # when: year=2031로 요약을 읽는다
    async with _client(use_cases, role=Role.USER) as http:
        response = await http.get(URL, params={"year": 2031})
    # then: 200이고 열은 기본 5개, 행은 없고 합계 셀·Open 합계가 모두 0이다
    assert response.status_code == 200
    body = response.json()
    assert [c["key"] for c in body["columns"]] == COLUMN_KEYS
    assert body["rows"] == []
    total = body["total"]
    assert total["owner"] is None
    assert [cell["key"] for cell in total["cells"]] == COLUMN_KEYS
    assert all((cell["count"], cell["amount"]) == (0, 0) for cell in total["cells"])
    assert total["open_total"] == {"count": 0, "amount": 0}


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"year": "abc"},
        {"year": 1899},
        {"year": 10000},
        {"year": 2026, "quarter": 0},
        {"year": 2026, "quarter": 5},
        {"year": 2026, "month": 0},
        {"year": 2026, "month": 13},
        {"year": 2026, "vendor": "SAP"},
        {"year": 2026, "unknown": "x"},
        {"year": 2026, "owner_user_id": "abc"},
    ],
)
async def test_invalid_queries_are_request_validation_errors(params: dict[str, str | int]) -> None:
    """연도 누락·범위 밖·형식 오류·모르는 키는 422 request-validation이다.

    테스트 코드: FC-014
    """
    # given: 로그인한 admin
    async with _client(_seeded(), role=Role.ADMIN) as http:
        # when: 잘못된 쿼리로 요약을 읽는다
        response = await http.get(URL, params=params)
    # then: 422 request-validation이다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_quarter_with_month_is_an_invalid_value_problem() -> None:
    """Quarter와 월을 함께 주면 422 invalid-value와 안내 문구다.

    테스트 코드: FC-015
    """
    # given: 로그인한 admin
    async with _client(_seeded(), role=Role.ADMIN) as http:
        # when: year=2026&quarter=1&month=1로 요약을 읽는다
        response = await http.get(URL, params={"year": 2026, "quarter": 1, "month": 1})
    # then: 422 invalid-value와 안내 문구다
    assert response.status_code == 422, response.text
    body = response.json()
    assert str(body["type"]).endswith("invalid-value")
    assert body["detail"] == "Quarter와 월은 함께 선택할 수 없습니다."


async def test_the_openapi_declares_the_summary_path_as_get_only() -> None:
    """openapi의 요약 경로는 GET뿐이고 파라미터는 다섯 개다.

    테스트 코드: FC-016
    """
    # when: openapi 문서를 만든다
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    spec = app.openapi()
    # then: 메서드는 GET뿐이고 파라미터 이름은 다섯 개다
    assert set(spec["paths"][URL]) == {"get"}
    names = {p["name"] for p in spec["paths"][URL]["get"]["parameters"]}
    assert names == {"year", "quarter", "month", "owner_user_id", "vendor_id"}
