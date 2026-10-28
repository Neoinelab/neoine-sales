"""GET /api/v1/deals의 `quarter` 반복 쿼리 파라미터(Quarter 다중 선택 AC-01~05).

DB 없이 라우터·스키마·오류 매핑을 FakeUseCases 위에서 본다. DB 시나리오는 functional(deals/).
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
from tests.functional.conftest import CSRF_HEADER, make_settings
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
    async with _client() as (http, codes):
        response = await http.get(URL, params=[("year", 2026), ("quarter", 1), ("quarter", 3)])

    assert response.status_code == 200, response.text
    assert _found(response.json()) == {
        codes[name] for name in ("q1_first", "q1_last", "q3_first", "q3_last")
    }
    assert response.json()["total"] == 4


async def test_a_single_quarter_behaves_as_before() -> None:
    async with _client() as (http, codes):
        response = await http.get(URL, params={"year": 2026, "quarter": 2})

    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["q2_first"], codes["q2_last"]}
    assert response.json()["total"] == 2


async def test_without_quarter_there_is_no_quarter_condition() -> None:
    async with _client() as (http, _):
        response = await http.get(URL, params={"year": 2026})

    assert response.json()["total"] == len(DAYS)


async def test_the_same_quarter_twice_equals_once() -> None:
    async with _client() as (http, _):
        twice = await http.get(URL, params=[("year", 2026), ("quarter", 1), ("quarter", 1)])
        once = await http.get(URL, params={"year": 2026, "quarter": 1})

    assert twice.status_code == 200, twice.text
    assert _found(twice.json()) == _found(once.json())


async def test_all_four_quarters_equal_no_quarter_condition() -> None:
    async with _client() as (http, _):
        four = await http.get(URL, params=(("year", 2026), *(("quarter", q) for q in (1, 2, 3, 4))))
        none = await http.get(URL, params={"year": 2026})

    assert four.status_code == 200, four.text
    assert _found(four.json()) == _found(none.json())
    assert four.json()["total"] == none.json()["total"]


async def test_quarters_without_a_year_use_this_year() -> None:
    async with _client() as (http, _):
        response = await http.get(URL, params=[("quarter", 1), ("quarter", 3)])

    assert response.status_code == 200, response.text  # 올해 Deal이 없어도 오류가 아니다


@pytest.mark.parametrize("bad", ["0", "5", "x", "-1", ""])
async def test_a_quarter_outside_one_to_four_is_request_validation(bad: str) -> None:
    async with _client() as (http, _):
        response = await http.get(URL, params=[("year", 2026), ("quarter", 1), ("quarter", bad)])

    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_four_quarter_values_are_accepted() -> None:
    async with _client() as (http, _):
        response = await http.get(
            URL, params=(("year", 2026), *(("quarter", q) for q in (1, 2, 3, 4)))
        )

    assert response.status_code == 200, response.text


async def test_more_than_four_quarter_values_is_request_validation() -> None:
    async with _client() as (http, _):
        response = await http.get(
            URL, params=(("year", 2026), *(("quarter", q) for q in (1, 2, 3, 4, 1)))
        )

    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_quarters_together_with_a_month_is_invalid_value() -> None:
    async with _client() as (http, _):
        response = await http.get(URL, params={"year": 2026, "quarter": 1, "month": 2})

    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("invalid-value")
    assert "Quarter와 월은 함께 선택할 수 없습니다." in response.text


async def test_all_four_quarters_together_with_a_month_filter_by_the_month_only() -> None:
    async with _client() as (http, codes):
        response = await http.get(
            URL, params=(("year", 2026), ("month", 4), *(("quarter", q) for q in (1, 2, 3, 4)))
        )

    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["q2_first"]}
