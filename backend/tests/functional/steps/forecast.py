"""Forecast 요약 feature의 step(P6 R1).

Given은 공개 API로 담당자·Deal·코드를 만들고(admin 로그인 상태에서 부른다), When은 요약 API 하나를
호출하며, Then은 응답 본문과 같은 조건의 Deal 목록(원장)만 본다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.auth import given_user_registered
from tests.functional.steps.deals import DEALS, given_deal

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

SUMMARY: Final = "/api/v1/forecast/summary"
OPEN_KEYS: Final = ["pipeline", "best", "most_likely", "commit"]
DEFAULT_KEYS: Final = [*OPEN_KEYS, "won"]
Cell = tuple[int, int]  # (건수, 금액)


# --- Given ---


async def given_sales_user(api: Api, login_id: str) -> int:
    """admin이 영업 담당자를 등록해 두었다(admin 로그인 상태)."""
    return await given_user_registered(api, login_id=login_id, role="sales")


async def given_forecast_deal(
    api: Api,
    *,
    owner: int,
    forecast: str = "pipeline",
    amount: int = 100,
    day: str = "2026-11-15",
    **overrides: object,
) -> dict[str, Any]:
    """담당자 `owner`의 Deal 하나. Won은 계약완료 Status와 함께만 있을 수 있다."""
    return await given_deal(
        api,
        owner_user_id=owner,
        forecast_key=forecast,
        status_key="contract_completed" if forecast == "won" else "prospecting",
        revenue_amount=amount,
        revenue_date=day,
        **overrides,
    )


def conditions_of(**conditions: int | None) -> dict[str, int]:
    """값이 None이 아닌 조건만 쿼리 파라미터로 남긴다(요약·Deal 목록이 같은 조건을 쓴다)."""
    return {key: value for key, value in conditions.items() if value is not None}


# --- When (HTTP API 하나) ---


async def when_get_summary(api: Api, **params: str | int) -> Response:
    return await api.get(SUMMARY, params=dict(params))


# --- Then ---


def cells_of(row: dict[str, Any]) -> dict[str, Cell]:
    return {cell["key"]: (cell["count"], cell["amount"]) for cell in row["cells"]}


def open_total_of(row: dict[str, Any]) -> Cell:
    return (row["open_total"]["count"], row["open_total"]["amount"])


def then_column_keys_are(response: Response, keys: list[str]) -> None:
    assert [c["key"] for c in response.json()["columns"]] == keys, response.json()["columns"]


def then_owner_ids_are(response: Response, owner_ids: list[int]) -> None:
    """행의 담당자 id가 순서까지 같다."""
    assert [row["owner"]["id"] for row in response.json()["rows"]] == owner_ids


def then_row_is(
    response: Response, *, owner: int, cells: dict[str, Cell], open_total: Cell
) -> None:
    """그 담당자 행의 0이 아닌 셀과 open_total이 같다(나머지 셀은 0)."""
    row = next(r for r in response.json()["rows"] if r["owner"]["id"] == owner)
    nonzero = {key: cell for key, cell in cells_of(row).items() if cell != (0, 0)}
    assert nonzero == cells
    assert open_total_of(row) == open_total


def then_total_is(response: Response, *, cells: dict[str, Cell], open_total: Cell) -> None:
    total = response.json()["total"]
    nonzero = {key: cell for key, cell in cells_of(total).items() if cell != (0, 0)}
    assert nonzero == cells
    assert open_total_of(total) == open_total
    assert total["owner"] is None


def then_every_row_cell_follows_the_columns(response: Response) -> None:
    keys = [c["key"] for c in response.json()["columns"]]
    for row in [*response.json()["rows"], response.json()["total"]]:
        assert [cell["key"] for cell in row["cells"]] == keys


async def then_ledger_matches(api: Api, response: Response, **conditions: str | int) -> None:
    """요약의 Open 합 + Won 셀이, 같은 조건 Deal 목록(원장 전체 페이지)에서 Lost를 뺀 합과 같다.

    건수와 금액 모두 본다(검수 4·9장).
    """
    items: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = await api.get(DEALS, params={**conditions, "limit": 200, "offset": offset})
        assert page.status_code == 200, page.text
        batch = page.json()["items"]
        items.extend(batch)
        offset += len(batch)
        if not batch or offset >= page.json()["total"]:
            break
    ledger = [d for d in items if d["forecast_key"] != "lost"]
    total = response.json()["total"]
    won = cells_of(total).get("won", (0, 0))
    open_total = open_total_of(total)
    assert open_total[0] + won[0] == len(ledger)
    assert open_total[1] + won[1] == sum(int(d["revenue_amount"]) for d in ledger)
