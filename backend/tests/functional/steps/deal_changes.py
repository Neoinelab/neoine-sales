"""Deal 단일 변경(applyChange) feature의 step: Status·Forecast·금액·Expected Close를 하나씩 바꾼다.

Given은 `steps/deals.py`로 Deal을 만들고, When은 `POST /deals/{code}/changes` 하나를 호출하며,
Then은 응답(`{deal, co_changed, notice}`)과 다시 조회한 결과만 본다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.deals import DEALS

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

REVENUE_REQUIRED: Final = "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."
CHOICE_REQUIRED: Final = "함께 바꿀 값을 선택하세요."
UNKNOWN_CODE: Final = "존재하지 않는 코드입니다."
AMOUNT_INVALID: Final = "매출금액은 1원 이상의 정수로 입력하세요."
CLOSING_NOTICE: Final = "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."
CLOSING: Final = {"revenue_amount": 900_000_000, "revenue_date": "2026-10-20"}
RESPONSE_KEYS: Final = {"deal", "co_changed", "notice"}


async def when_change_deal(
    api: Api,
    code: str,
    field: str,
    value: object,
    resolution: dict[str, Any] | None = None,
) -> Response:
    body: dict[str, Any] = {"change": {"field": field, "value": value}}
    if resolution is not None:
        body["resolution"] = resolution
    return await api.post(f"{DEALS}/{code}/changes", json=body)


def then_response_has_the_documented_keys(response: Response) -> None:
    assert set(response.json()) == RESPONSE_KEYS, response.json()


def then_co_changed_is(response: Response, expected: list[tuple[str, str, str]]) -> None:
    """함께 바뀐 값 목록이 (field, from, to)와 같다."""
    actual = [(c["field"], c["from"], c["to"]) for c in response.json()["co_changed"]]
    assert actual == expected


def then_notice_is(response: Response, notice: str | None) -> None:
    assert response.json()["notice"] == notice


def then_returned_deal_has(response: Response, **fields: object) -> None:
    deal = response.json()["deal"]
    assert {key: deal[key] for key in fields} == fields, deal
