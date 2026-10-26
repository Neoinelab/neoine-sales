"""Deal 목록 Forecast 다중 조건 feature의 step.

When은 `forecast_key`를 반복해 보내는 목록 조회 API 하나이고, Then은 응답의 code·total만 본다.
Dashboard 응답의 Forecast 열(key, outcome)에서 Drill-down 집합을 만드는 도우미를 함께 둔다.
"""

from typing import TYPE_CHECKING, Any

from tests.functional.steps.deals import DEALS

if TYPE_CHECKING:
    from collections.abc import Iterable

    from httpx import Response

    from tests.functional.conftest import Api


async def when_list_deals_of_forecasts(
    api: Api, keys: Iterable[str], **params: str | int
) -> Response:
    """`forecast_key=a&forecast_key=b` 형태로 목록을 조회한다."""
    query: dict[str, str | int | list[str]] = {"forecast_key": list(keys), **params}
    return await api.get(DEALS, params=query)


def keys_by_outcome(response: Response, outcomes: set[str]) -> list[str]:
    """Dashboard 응답 forecasts.columns 중 outcome이 outcomes에 드는 열의 key."""
    columns: list[dict[str, Any]] = response.json()["forecasts"]["columns"]
    return [str(c["key"]) for c in columns if c["outcome"] in outcomes]
