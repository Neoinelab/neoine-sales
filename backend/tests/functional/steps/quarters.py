"""Quarter 다중 선택 feature의 step.

When은 `quarter`를 반복해 보내는 API 하나(Deal 목록 또는 Dashboard 요약)이고, Then은 응답의
code·total·period만 본다.
"""

from typing import TYPE_CHECKING

from tests.functional.steps.dashboard import SUMMARY
from tests.functional.steps.deals import DEALS

if TYPE_CHECKING:
    from collections.abc import Iterable

    from httpx import Response

    from tests.functional.conftest import Api


async def when_list_deals_of_quarters(
    api: Api, quarters: Iterable[int | str], **params: str | int
) -> Response:
    """`quarter=1&quarter=3` 형태로 목록을 조회한다."""
    query: dict[str, str | int | list[str]] = {"quarter": [str(q) for q in quarters], **params}
    return await api.get(DEALS, params=query)


async def when_get_dashboard_summary_of_quarters(
    api: Api, quarters: Iterable[int | str], **params: str | int
) -> Response:
    query: dict[str, str | int | list[str]] = {"quarter": [str(q) for q in quarters], **params}
    return await api.get(SUMMARY, params=query)
