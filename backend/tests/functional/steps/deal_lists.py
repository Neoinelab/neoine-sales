"""Deal 목록 확장 필터·정렬·파생값·삭제 영향 feature의 step.

Given은 공개 API로 Deal·Action을 만들고, When은 목록·facets·삭제 영향 조회 API 하나를 호출하며,
Then은 응답의 code 목록과 값만 본다. 기본 목록 조회 step은 `steps/deals.py`다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.actions import given_action_at
from tests.functional.steps.deals import DEALS

if TYPE_CHECKING:
    from datetime import datetime

    from httpx import Response

    from tests.functional.conftest import Api

QUARTER_WITHOUT_YEAR: Final = "분기는 연도와 함께 선택하세요."
IMPACT_KEYS: Final = {"history_count", "action_count", "attachment_count"}


async def given_action(
    api: Api,
    code: str,
    *,
    acted_at: datetime,
    next_action: str = "견적서 전달",
    due_date: str = "2027-01-15",
) -> dict[str, Any]:
    """로그인한 사용자가 Deal에 Action을 남겨 두었다(응답 본문을 돌려준다).

    수행 일시는 본문이 아니라 서버 시계가 정한다(P2). 그래서 `acted_at`은 요청에 싣지 않고,
    등록 전에 `api.clock`을 그 시각으로 맞춘다(앞으로도 뒤로도 갈 수 있다).
    """
    return await given_action_at(
        api, code, acted_at, action="미팅", next_action=next_action, due_date=due_date, memo=""
    )


async def when_get_facets(api: Api) -> Response:
    return await api.get(f"{DEALS}/facets")


async def when_get_deletion_impact(api: Api, code: str) -> Response:
    return await api.get(f"{DEALS}/{code}/deletion-impact")


def codes_of(response: Response) -> list[str]:
    return [str(item["code"]) for item in response.json()["items"]]


def then_codes_are(response: Response, expected: list[str]) -> None:
    """목록의 code가 순서까지 expected와 같다."""
    assert codes_of(response) == expected, response.json()


def then_codes_are_exactly(response: Response, expected: list[str]) -> None:
    """목록의 code 집합이 expected와 같다(순서는 보지 않는다)."""
    assert sorted(codes_of(response)) == sorted(expected), response.json()


def then_total_is(response: Response, total: int) -> None:
    assert response.json()["total"] == total


def then_facets_are(response: Response, *, vendors: list[str], solutions: list[str]) -> None:
    assert response.json() == {"vendors": vendors, "solutions": solutions}


def then_impact_is(response: Response, *, history: int, actions: int) -> None:
    assert response.json() == {
        "history_count": history,
        "action_count": actions,
        "attachment_count": 0,
    }
