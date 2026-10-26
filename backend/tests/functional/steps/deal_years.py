"""연도 선택지 기준 feature의 step: `GET /api/v1/deals/years` 하나와 결과 확인.

Given은 공개 API로 Deal을 만들고, When은 GET 하나, Then은 응답과 다시 조회한 결과만 본다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.common import then_body_is
from tests.functional.steps.deals import DEALS, given_deal, given_sales_owner
from tests.functional.steps.users import Session, when_request_as

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

YEARS: Final = f"{DEALS}/years"


async def given_deal_closing_on(api: Api, revenue_date: str, **overrides: object) -> dict[str, Any]:
    """영업 담당자가 Owner이고 Expected Close가 revenue_date인 Deal을 등록했다(admin 로그인)."""
    owner = await given_sales_owner(api)
    return await given_deal(api, owner_user_id=owner, revenue_date=revenue_date, **overrides)


async def given_deals_closing_on(api: Api, *revenue_dates: str) -> list[dict[str, Any]]:
    return [await given_deal_closing_on(api, day) for day in revenue_dates]


async def when_get_years(api: Api) -> Response:
    return await api.get(YEARS)


async def when_get_years_as(api: Api, session: Session) -> Response:
    return await when_request_as(api, session, "GET", YEARS)


def then_earliest_year_is(response: Response, year: int | None) -> None:
    assert response.status_code == 200, f"{response.status_code}: {response.text}"
    then_body_is(response, {"earliest_year": year})
