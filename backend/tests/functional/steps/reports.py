"""Reports 1단계(필드 카탈로그와 조회 엔진) feature의 step.

Given은 공개 API로 Vendor·담당자·Deal·Action을 만들고(admin 로그인 상태에서 부른다), When은
Reports API 하나를 호출하며, Then은 응답 본문과 같은 조건의 Deals 목록(원장)만 본다.
오늘(서버 업무 날짜)은 `given_today_is`로 고정한다(로그인보다 먼저 부른다).
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.dashboard import ledger_of

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

FIELDS: Final = "/api/v1/reports/fields"
QUERY: Final = "/api/v1/reports/query"

VENDOR_QUARTER_BODY: Final[dict[str, Any]] = {
    "columns": [
        {"field": "deal.vendor", "group": True},
        {"field": "deal.expected_close", "format": "quarter", "group": True},
        {"field": "deal.amount", "aggregate": "sum", "label": "금액 합계"},
        {"field": "deal.code", "aggregate": "count", "label": "건수"},
    ],
    "conditions": [
        {"field": "deal.forecast_outcome", "operator": "not_in", "value": ["lost"]},
        {"field": "deal.expected_close", "operator": "relative", "value": {"period": "this_year"}},
    ],
    "combine": "and",
    "sort": {"column": 1, "direction": "asc"},
    "row_limit": 1000,
}
# (Vendor 이름 또는 None, Expected Close, Forecast, 금액): 연도 밖·Lost 포함
VENDOR_QUARTER_DEALS: Final = (
    ("SAP", "2026-02-10", "pipeline", 100),
    ("SAP", "2026-03-31", "commit", 110),
    ("SAP", "2026-02-11", "lost", 5000),
    ("SAP", "2026-05-10", "commit", 200),
    ("SAP", "2025-12-31", "pipeline", 777),
    ("IBM", "2026-02-12", "pipeline", 300),
    ("IBM", "2026-08-10", "best", 400),
    ("IBM", "2027-01-01", "pipeline", 888),
    (None, "2026-02-13", "pipeline", 50),
    (None, "2026-11-10", "most_likely", 60),
    (None, "2026-08-11", "lost", 9000),
)
VENDOR_NAMES: Final = ("SAP", "IBM")


# --- When (HTTP API 하나) ---


async def when_get_report_fields(api: Api) -> Response:
    return await api.get(FIELDS)


async def when_query_report(api: Api, body: object) -> Response:
    return await api.post(QUERY, json=body)


# --- Then ---


def then_fields_are_listed(response: Response, *, count: int) -> None:
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["fields"]) == count
    assert {f["key"] for f in body["fields"]} >= {"deal.amount", "deal.vendor", "action.count"}
    assert body["limits"]["columns_max"] == 30


def then_report_error_locations_are(
    response: Response, expected: list[tuple[list[str | int], str]]
) -> None:
    assert response.status_code == 422, response.text
    body = response.json()
    assert str(body["type"]).endswith("invalid-report"), body
    assert [(e["location"], e["code"]) for e in body["errors"]] == expected
    assert all(e["message"] for e in body["errors"])


def rows_of(response: Response) -> list[list[Any]]:
    assert response.status_code == 200, response.text
    return list(response.json()["rows"])


def then_rows_are(response: Response, expected: list[list[Any]]) -> None:
    assert rows_of(response) == expected


async def then_vendor_quarter_cells_match_the_deal_list(
    api: Api, response: Response, vendor_ids: dict[str, int]
) -> None:
    """리포트의 각 (Vendor, 분기) 칸이 Deals 목록의 같은 조건 건수·금액과 같다.

    Vendor 없는 칸은 그 분기 전체에서 Vendor 칸을 뺀 값과 같다.
    """
    cells = {(row[0], row[1]): (int(row[3]), int(row[2])) for row in rows_of(response)}
    base: dict[str, str | int] = {"year": 2026, "forecast_outcome": "not_lost"}
    for quarter in range(1, 5):
        whole = await ledger_of(api, **base, quarter=quarter)
        taken = (0, 0)
        for name, vendor_id in vendor_ids.items():
            found = await ledger_of(api, **base, quarter=quarter, vendor_id=vendor_id)
            taken = (taken[0] + found[0], taken[1] + found[1])
            assert cells.get((name, f"2026 Q{quarter}"), (0, 0)) == found, (name, quarter)
        rest = (whole[0] - taken[0], whole[1] - taken[1])
        assert cells.get((None, f"2026 Q{quarter}"), (0, 0)) == rest, (None, quarter)
    assert all(count > 0 for count, _ in cells.values())  # 빈 칸은 행이 아니다
