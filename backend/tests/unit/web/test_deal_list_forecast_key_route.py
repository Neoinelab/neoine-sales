"""GET /api/v1/deals의 `forecast_key` 반복 쿼리 파라미터(Forecast 다중 조건 AC-01~05).

DB 없이 라우터·스키마·오류 매핑을 FakeUseCases 위에서 본다. DB 시나리오는 functional(deals/).
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

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
FORECASTS = ("pipeline", "best", "commit", "lost")


@asynccontextmanager
async def _client() -> AsyncIterator[tuple[AsyncClient, dict[str, str]]]:
    """pipeline·best·commit·lost Deal이 하나씩 있는 앱. 둘째 값은 forecast -> deal code."""
    from tests.fakes.catalog_seed import seed_catalog  # noqa: PLC0415

    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    await ensure_users(use_cases.uow.users, OWNER_ID)
    codes: dict[str, str] = {}
    for number, forecast in enumerate(FORECASTS, start=1):
        deal = make_deal(later(number), code=f"20261016-A{number:03d}", forecast_key=forecast)
        await use_cases.uow.contacts.add(
            make_contact(ContactKind.CUSTOMER, entity_id=deal.customer_id)
        )
        use_cases.uow.deals._items[deal.id] = deal
        codes[forecast] = deal.id.value
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


async def test_repeated_forecast_key_returns_the_deals_of_any_of_them() -> None:
    async with _client() as (http, codes):
        response = await http.get(
            URL, params=[("forecast_key", "pipeline"), ("forecast_key", "best")]
        )

    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["pipeline"], codes["best"]}
    assert response.json()["total"] == 2


async def test_a_single_forecast_key_behaves_as_before() -> None:
    async with _client() as (http, codes):
        response = await http.get(URL, params={"forecast_key": "commit"})

    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["commit"]}
    assert response.json()["total"] == 1


async def test_without_forecast_key_there_is_no_forecast_condition() -> None:
    async with _client() as (http, _):
        response = await http.get(URL)

    assert response.json()["total"] == len(FORECASTS)


async def test_the_same_key_twice_equals_once() -> None:
    async with _client() as (http, codes):
        response = await http.get(URL, params=[("forecast_key", "best"), ("forecast_key", "best")])

    assert _found(response.json()) == {codes["best"]}


async def test_an_unknown_key_is_not_an_error_and_others_still_match() -> None:
    async with _client() as (http, codes):
        response = await http.get(
            URL, params=[("forecast_key", "no_such"), ("forecast_key", "lost")]
        )

    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["lost"]}


async def test_an_empty_string_key_matches_nothing_without_an_error() -> None:
    async with _client() as (http, _):
        response = await http.get(URL, params={"forecast_key": ""})

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


async def test_a_comma_is_part_of_one_key() -> None:
    async with _client() as (http, _):
        response = await http.get(URL, params={"forecast_key": "pipeline,best"})

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


async def test_forecast_key_is_anded_with_the_outcome() -> None:
    async with _client() as (http, codes):
        response = await http.get(
            URL,
            params=[
                ("forecast_key", "lost"),
                ("forecast_key", "pipeline"),
                ("forecast_outcome", "open"),
            ],
        )

    assert _found(response.json()) == {codes["pipeline"]}


async def test_fifty_chars_and_one_hundred_keys_are_accepted() -> None:
    async with _client() as (http, _):
        long_key = await http.get(URL, params={"forecast_key": "a" * 50})
        many = await http.get(URL, params=[("forecast_key", f"k{i}") for i in range(100)])

    assert long_key.status_code == 200, long_key.text
    assert many.status_code == 200, many.text


async def test_more_than_one_hundred_keys_is_request_validation() -> None:
    async with _client() as (http, _):
        response = await http.get(URL, params=[("forecast_key", f"k{i}") for i in range(101)])

    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_a_key_longer_than_fifty_characters_is_request_validation() -> None:
    async with _client() as (http, _):
        response = await http.get(
            URL, params=[("forecast_key", "best"), ("forecast_key", "a" * 51)]
        )

    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")
