"""GET /api/v1/deals의 `quarter` 반복 쿼리 파라미터(Quarter 다중 선택).

DB 없이 라우터·스키마·오류 매핑을 FakeUseCases 위에서 본다.
BDD 케이스의 HTTP 수준 검증은 `web/test_deal_list_http_cases.py`가, 조회 동작은
`application/test_deal_list_period_sort_cases.py`가 맡는다.
"""

from contextlib import asynccontextmanager
from datetime import date
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.domain.contact.values import ContactKind
from app.main import create_app
from tests.factories import later, make_deal
from tests.factories_auth import make_principal
from tests.factories_contact import make_contact
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import CSRF_HEADER, make_settings
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/deals"
DAYS = {  # 이름 -> Expected Close (2026)
    "q1_first": date(2026, 1, 1),
    "q1_last": date(2026, 3, 31),
    "q2_first": date(2026, 4, 1),
    "q2_last": date(2026, 6, 30),
    "q3_first": date(2026, 7, 1),
    "q3_last": date(2026, 9, 30),
    "q4_first": date(2026, 10, 1),
}


@asynccontextmanager
async def _client() -> AsyncIterator[tuple[AsyncClient, dict[str, str]]]:
    """분기 경계일마다 Deal이 하나씩 있는 앱. 둘째 값은 이름 -> deal code."""
    from tests.fakes.catalog_seed import seed_catalog  # noqa: PLC0415

    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    await ensure_users(use_cases.uow.users, OWNER_ID)
    codes: dict[str, str] = {}
    for number, (name, day) in enumerate(DAYS.items(), start=1):
        deal = make_deal(later(number), code=f"20261016-A{number:03d}", revenue_date=day)
        await use_cases.uow.contacts.add(
            make_contact(ContactKind.CUSTOMER, entity_id=deal.customer_id)
        )
        use_cases.uow.vendors.materialize_default()  # 기본 Deal의 Vendor
        use_cases.uow.deals._items[deal.id] = deal
        codes[name] = deal.id.value
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookie = await use_cases.login_as(make_principal("root", Role.ADMIN))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies={SESSION_COOKIE: cookie},
    ) as http:
        yield http, codes


def _found(body: dict[str, object]) -> set[str]:
    items = body["items"]
    assert isinstance(items, list)
    return {item["code"] for item in items}


async def test_repeated_quarter_returns_the_deals_of_any_of_them() -> None:
    """quarter를 반복하면 그중 하나에 맞는 Deal을 모두 돌려준다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, codes):
        # when: 2026년 Q1, Q3를 반복해 조회한다
        response = await http.get(URL, params=[("year", 2026), ("quarter", 1), ("quarter", 3)])

    # then: Q1·Q3 경계일의 Deal 4건이 나온다
    assert response.status_code == 200, response.text
    assert _found(response.json()) == {
        codes[name] for name in ("q1_first", "q1_last", "q3_first", "q3_last")
    }
    assert response.json()["total"] == 4


async def test_a_single_quarter_behaves_as_before() -> None:
    """quarter를 하나만 주면 예전처럼 그 분기의 Deal만 나온다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, codes):
        # when: 2026년 Q2 하나로 조회한다
        response = await http.get(URL, params={"year": 2026, "quarter": 2})

    # then: Q2 경계일의 Deal 2건이다
    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["q2_first"], codes["q2_last"]}
    assert response.json()["total"] == 2


async def test_without_quarter_there_is_no_quarter_condition() -> None:
    """quarter가 없으면 분기 조건 없이 그 해의 Deal이 모두 나온다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: 2026년만 주고 조회한다
        response = await http.get(URL, params={"year": 2026})

    # then: 모든 Deal이 나온다
    assert response.json()["total"] == len(DAYS)


async def test_the_same_quarter_twice_equals_once() -> None:
    """같은 분기를 두 번 보내도 한 번 보낸 것과 같다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: Q1을 두 번, 그리고 한 번 보내 각각 조회한다
        twice = await http.get(URL, params=[("year", 2026), ("quarter", 1), ("quarter", 1)])
        once = await http.get(URL, params={"year": 2026, "quarter": 1})

    # then: 두 결과가 같다
    assert twice.status_code == 200, twice.text
    assert _found(twice.json()) == _found(once.json())


async def test_all_four_quarters_equal_no_quarter_condition() -> None:
    """네 분기를 모두 보내면 분기 조건이 없는 것과 같다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: Q1~Q4를 모두 보낸 조회와 분기 없는 조회를 한다
        four = await http.get(URL, params=(("year", 2026), *(("quarter", q) for q in (1, 2, 3, 4))))
        none = await http.get(URL, params={"year": 2026})

    # then: 결과 집합과 total이 같다
    assert four.status_code == 200, four.text
    assert _found(four.json()) == _found(none.json())
    assert four.json()["total"] == none.json()["total"]


async def test_quarters_without_a_year_use_this_year() -> None:
    """연도 없이 분기만 보내도 올해로 보고 오류 없이 조회한다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: 연도 없이 Q1, Q3를 보내 조회한다
        response = await http.get(URL, params=[("quarter", 1), ("quarter", 3)])

    # then: 올해 Deal이 없어도 오류가 아니다
    assert response.status_code == 200, response.text  # 올해 Deal이 없어도 오류가 아니다


@pytest.mark.parametrize("bad", ["0", "5", "x", "-1", ""])
async def test_a_quarter_outside_one_to_four_is_request_validation(bad: str) -> None:
    """1~4 밖의 분기 값은 request-validation 오류다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: 유효하지 않은 분기 값을 함께 보내 조회한다
        response = await http.get(URL, params=[("year", 2026), ("quarter", 1), ("quarter", bad)])

    # then: 422 request-validation이다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_four_quarter_values_are_accepted() -> None:
    """분기 값 네 개는 받아들인다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: Q1~Q4를 보내 조회한다
        response = await http.get(
            URL, params=(("year", 2026), *(("quarter", q) for q in (1, 2, 3, 4)))
        )

    # then: 200이다
    assert response.status_code == 200, response.text


async def test_more_than_four_quarter_values_is_request_validation() -> None:
    """분기 값이 네 개를 넘으면 request-validation 오류다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: 분기 값 다섯 개를 보내 조회한다
        response = await http.get(
            URL, params=(("year", 2026), *(("quarter", q) for q in (1, 2, 3, 4, 1)))
        )

    # then: 422 request-validation이다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_quarters_together_with_a_month_is_invalid_value() -> None:
    """분기와 월을 함께 보내면 invalid-value 오류다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: Q1과 2월을 함께 보내 조회한다
        response = await http.get(URL, params={"year": 2026, "quarter": 1, "month": 2})

    # then: 422 invalid-value와 안내 문구다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("invalid-value")
    assert "Quarter와 월은 함께 선택할 수 없습니다." in response.text


async def test_all_four_quarters_together_with_a_month_filter_by_the_month_only() -> None:
    """네 분기를 모두 보내고 월을 함께 주면 월 조건만 적용된다."""
    # given: 분기 경계일마다 Deal이 하나씩 있는 앱
    async with _client() as (http, codes):
        # when: Q1~Q4와 4월을 함께 보내 조회한다
        response = await http.get(
            URL, params=(("year", 2026), ("month", 4), *(("quarter", q) for q in (1, 2, 3, 4)))
        )

    # then: 4월 경계일 Deal만 나온다
    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["q2_first"]}
