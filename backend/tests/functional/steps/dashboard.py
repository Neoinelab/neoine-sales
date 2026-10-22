"""Dashboard feature의 step.

Given은 공개 API로 담당자·Vendor·코드·Deal을 만들고(admin 로그인 상태에서 부른다), When은
요약 API 하나를 호출하며, Then은 응답 본문과 같은 조건의 다른 읽기 API(Forecast 요약,
Deal 목록 원장)만 본다.
오늘(서버 업무 날짜)은 `given_today_is`로 고정한다(로그인보다 먼저 부른다).
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.deals import DEALS, given_clock_at, given_deal
from tests.functional.steps.forecast import SUMMARY as FORECAST_SUMMARY

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

SUMMARY: Final = "/api/v1/dashboard/summary"
STATUS_KEYS: Final = [
    "prospecting",
    "introduction",
    "poc_preparation",
    "poc_completed",
    "technical_evaluation",
    "price_negotiation",
    "contract_completed",
]
Cell = tuple[int, int]  # (건수, 금액)


# --- Given ---


async def given_today_is(api: Api, day: date) -> None:
    """서버 시계를 그날 로컬 정오로 맞춘다(업무 날짜 = OS 로컬 시간대). 로그인보다 먼저 부른다."""
    await given_clock_at(api, datetime(day.year, day.month, day.day, 12).astimezone())


async def given_dashboard_deal(  # noqa: PLR0913 - Dashboard 집계 축이 모두 독립적인 선택지
    api: Api,
    *,
    owner: int,
    status: str | None = None,
    forecast: str = "pipeline",
    amount: int = 100,
    day: str = "2026-11-15",
    vendor_id: int | None = None,
    **overrides: object,
) -> dict[str, Any]:
    """담당자 `owner`의 Deal 하나. Won은 계약완료 Status와 함께만 있다."""
    return await given_deal(
        api,
        owner_user_id=owner,
        status_key=status or ("contract_completed" if forecast == "won" else "prospecting"),
        forecast_key=forecast,
        revenue_amount=amount,
        revenue_date=day,
        vendor_id=vendor_id,
        **overrides,
    )


# --- When (HTTP API 하나) ---


async def when_get_dashboard_summary(api: Api, **params: str | int) -> Response:
    return await api.get(SUMMARY, params=dict(params))


# --- Then ---


def cell_of(item: dict[str, Any]) -> Cell:
    return (int(item["count"]), int(item["amount"]))


def cells_by_key(cells: list[dict[str, Any]]) -> dict[str, Cell]:
    return {str(c["key"]): cell_of(c) for c in cells}


def then_status_items_are(response: Response, expected: dict[str, Cell]) -> None:
    """Status 항목은 코드 7개 전부를 order 순으로 담고, 지정하지 않은 Status는 (0, 0)이다."""
    items = response.json()["statuses"]["items"]
    assert [i["key"] for i in items] == STATUS_KEYS
    assert [i["order"] for i in items] == sorted(i["order"] for i in items)
    assert {i["key"]: cell_of(i) for i in items} == {
        key: expected.get(key, (0, 0)) for key in STATUS_KEYS
    }


def then_status_total_is(response: Response, expected: Cell) -> None:
    body = response.json()["statuses"]
    assert cell_of(body["total"]) == expected
    assert sum(cell_of(i)[0] for i in body["items"]) == expected[0]
    assert sum(cell_of(i)[1] for i in body["items"]) == expected[1]


def then_forecast_column_keys_are(response: Response, keys: list[str]) -> None:
    forecasts = response.json()["forecasts"]
    assert [c["key"] for c in forecasts["columns"]] == keys
    assert [c["key"] for c in forecasts["cells"]] == keys


async def then_forecast_part_equals_forecast_summary(
    api: Api, response: Response, **conditions: int
) -> None:
    """Forecast 타일(열·셀·open_total)이 같은 조건 `/forecast/summary` 응답의 total과 같다."""
    summary = await api.get(FORECAST_SUMMARY, params={**conditions})
    assert summary.status_code == 200, summary.text
    expected = summary.json()
    forecasts = response.json()["forecasts"]
    assert [c["key"] for c in forecasts["columns"]] == [c["key"] for c in expected["columns"]]
    assert cells_by_key(forecasts["cells"]) == cells_by_key(expected["total"]["cells"])
    assert cell_of(forecasts["open_total"]) == cell_of(expected["total"]["open_total"])


async def then_quarters_match_forecast_summary(
    api: Api, response: Response, **conditions: int
) -> None:
    """quarters[q]의 셀·open_total이 같은 연도·분기·담당자·Vendor의 `/forecast/summary`
    total과 같다.

    conditions에는 year와 (있으면) owner_user_id·vendor_id를 넣는다(quarter는 넣지 않는다).
    """
    quarters = response.json()["quarters"]
    assert [q["quarter"] for q in quarters] == [1, 2, 3, 4]
    for quarter in quarters:
        summary = await api.get(
            FORECAST_SUMMARY, params={**conditions, "quarter": quarter["quarter"]}
        )
        assert summary.status_code == 200, summary.text
        total = summary.json()["total"]
        assert cells_by_key(quarter["cells"]) == cells_by_key(total["cells"]), quarter["quarter"]
        assert cell_of(quarter["open_total"]) == cell_of(total["open_total"]), quarter["quarter"]
        won = cells_by_key(total["cells"]).get("won", (0, 0))
        open_total = cell_of(total["open_total"])
        assert cell_of(quarter["total"]) == (open_total[0] + won[0], open_total[1] + won[1])


async def ledger_of(api: Api, **params: str | int) -> Cell:
    """Deal 목록을 모든 페이지 순회해 (total, revenue_amount 합)을 구한다."""
    count = 0
    amount = 0
    offset = 0
    total = 0
    while True:
        page = await api.get(DEALS, params={**params, "limit": 200, "offset": offset})
        assert page.status_code == 200, page.text
        body = page.json()
        total = int(body["total"])
        count += len(body["items"])
        amount += sum(int(d["revenue_amount"]) for d in body["items"])
        offset += len(body["items"])
        if not body["items"] or offset >= total:
            break
    assert count == total, (params, count, total)
    return (total, amount)


def _period(conditions: dict[str, int]) -> dict[str, int]:
    return {k: v for k, v in conditions.items() if k in {"year", "quarter"}}


def _owner_vendor(conditions: dict[str, int]) -> dict[str, int]:
    return {k: v for k, v in conditions.items() if k in {"owner_user_id", "vendor_id"}}


async def then_every_drilldown_matches_the_ledger(
    api: Api, response: Response, **conditions: int
) -> None:
    """계획 4.5절 표의 각 요소와 같은 `/deals` 조건으로 센 건수·금액이 대시보드 숫자와 같다.

    conditions: year(필수), quarter, owner_user_id, vendor_id (대시보드 요청과 같은 값).
    """
    body = response.json()
    common = {**_period(conditions), **_owner_vendor(conditions)}
    others = _owner_vendor(conditions)

    for key, cell in cells_by_key(body["forecasts"]["cells"]).items():
        assert await ledger_of(api, **common, forecast_key=key) == cell, ("forecast", key)
    assert await ledger_of(api, **common, forecast_outcome="open") == cell_of(
        body["forecasts"]["open_total"]
    ), "open_total"

    for item in body["statuses"]["items"]:
        found = await ledger_of(api, **common, status_key=item["key"], forecast_outcome="not_lost")
        assert found == cell_of(item), ("status", item["key"])
    assert await ledger_of(api, **common, forecast_outcome="not_lost") == cell_of(
        body["statuses"]["total"]
    ), "status total"

    attention = body["attention"]
    assert (await ledger_of(api, **others, overdue="true"))[0] == attention["overdue"]
    assert (await ledger_of(api, **others, stale="true"))[0] == attention["stale"]
    this_quarter = attention["closing_this_quarter"]
    found_quarter = await ledger_of(
        api,
        year=this_quarter["year"],
        quarter=this_quarter["quarter"],
        **others,
        forecast_outcome="open",
    )
    assert found_quarter[0] == this_quarter["count"], "closing_this_quarter"
    this_month = attention["closing_this_month"]
    found_month = await ledger_of(
        api, year=this_month["year"], month=this_month["month"], **others, forecast_outcome="open"
    )
    assert found_month[0] == this_month["count"], "closing_this_month"

    year = conditions["year"]
    for quarter in body["quarters"]:
        for key, cell in cells_by_key(quarter["cells"]).items():
            found = await ledger_of(
                api, year=year, quarter=quarter["quarter"], **others, forecast_key=key
            )
            assert found == cell, ("quarter cell", quarter["quarter"], key)
        found_total = await ledger_of(
            api, year=year, quarter=quarter["quarter"], **others, forecast_outcome="not_lost"
        )
        assert found_total == cell_of(quarter["total"]), ("quarter total", quarter["quarter"])
