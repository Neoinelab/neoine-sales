"""GET /api/v1/deals의 `forecast_key` 반복 쿼리 파라미터(Forecast 다중 조건).

DB 없이 라우터·스키마·오류 매핑을 FakeUseCases 위에서 본다.
BDD 케이스의 HTTP 수준 검증은 `web/test_deal_list_http_cases.py`가, 조회 동작은
`application/test_deal_list_search_cases.py`가 맡는다.
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
from tests.support.app_settings import CSRF_HEADER, make_settings
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
        use_cases.uow.vendors.materialize_default()  # 기본 Deal의 Vendor
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
    """forecast_key를 반복하면 그중 하나에 맞는 Deal을 모두 돌려준다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, codes):
        # when: forecast_key를 pipeline, best로 반복해 조회한다
        response = await http.get(
            URL, params=[("forecast_key", "pipeline"), ("forecast_key", "best")]
        )

    # then: 두 Forecast의 Deal 2건이 나온다
    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["pipeline"], codes["best"]}
    assert response.json()["total"] == 2


async def test_a_single_forecast_key_behaves_as_before() -> None:
    """forecast_key를 하나만 주면 예전처럼 그 Forecast의 Deal만 나온다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, codes):
        # when: forecast_key를 commit 하나로 조회한다
        response = await http.get(URL, params={"forecast_key": "commit"})

    # then: commit Deal 1건이다
    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["commit"]}
    assert response.json()["total"] == 1


async def test_without_forecast_key_there_is_no_forecast_condition() -> None:
    """forecast_key가 없으면 Forecast 조건 없이 모두 나온다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: forecast_key 없이 조회한다
        response = await http.get(URL)

    # then: 4건 모두 나온다
    assert response.json()["total"] == len(FORECASTS)


async def test_the_same_key_twice_equals_once() -> None:
    """같은 키를 두 번 보내도 한 번 보낸 것과 같다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, codes):
        # when: forecast_key를 best로 두 번 보내 조회한다
        response = await http.get(URL, params=[("forecast_key", "best"), ("forecast_key", "best")])

    # then: best Deal 하나만 나온다
    assert _found(response.json()) == {codes["best"]}


async def test_an_unknown_key_is_not_an_error_and_others_still_match() -> None:
    """모르는 키는 오류가 아니고 함께 보낸 알려진 키는 그대로 맞는다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, codes):
        # when: 모르는 키 no_such와 lost를 함께 보내 조회한다
        response = await http.get(
            URL, params=[("forecast_key", "no_such"), ("forecast_key", "lost")]
        )

    # then: 오류 없이 lost Deal만 나온다
    assert response.status_code == 200, response.text
    assert _found(response.json()) == {codes["lost"]}


async def test_an_empty_string_key_matches_nothing_without_an_error() -> None:
    """빈 문자열 키는 오류 없이 아무것도 맞지 않는다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: forecast_key를 빈 문자열로 조회한다
        response = await http.get(URL, params={"forecast_key": ""})

    # then: 오류 없이 0건이다
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


async def test_a_comma_is_part_of_one_key() -> None:
    """쉼표는 키를 나누지 않고 한 키의 일부다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: forecast_key를 "pipeline,best" 하나로 조회한다
        response = await http.get(URL, params={"forecast_key": "pipeline,best"})

    # then: 그런 키가 없어 0건이다
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


async def test_forecast_key_is_anded_with_the_outcome() -> None:
    """forecast_key는 forecast_outcome과 AND로 합쳐진다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, codes):
        # when: lost·pipeline 키에 outcome=open을 함께 보내 조회한다
        response = await http.get(
            URL,
            params=[
                ("forecast_key", "lost"),
                ("forecast_key", "pipeline"),
                ("forecast_outcome", "open"),
            ],
        )

    # then: 진행 중인 pipeline Deal만 나온다
    assert _found(response.json()) == {codes["pipeline"]}


async def test_fifty_chars_and_one_hundred_keys_are_accepted() -> None:
    """50자 키와 키 100개는 받아들인다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: 50자 키 하나, 그리고 키 100개로 각각 조회한다
        long_key = await http.get(URL, params={"forecast_key": "a" * 50})
        many = await http.get(URL, params=[("forecast_key", f"k{i}") for i in range(100)])

    # then: 둘 다 200이다
    assert long_key.status_code == 200, long_key.text
    assert many.status_code == 200, many.text


async def test_more_than_one_hundred_keys_is_request_validation() -> None:
    """키가 100개를 넘으면 request-validation 오류다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: 키 101개로 조회한다
        response = await http.get(URL, params=[("forecast_key", f"k{i}") for i in range(101)])

    # then: 422 request-validation이다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_a_key_longer_than_fifty_characters_is_request_validation() -> None:
    """키가 50자를 넘으면 request-validation 오류다."""
    # given: pipeline·best·commit·lost Deal이 하나씩 있는 앱
    async with _client() as (http, _):
        # when: 51자 키를 포함해 조회한다
        response = await http.get(
            URL, params=[("forecast_key", "best"), ("forecast_key", "a" * 51)]
        )

    # then: 422 request-validation이다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")
