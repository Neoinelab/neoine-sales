"""Feature: 로그인한 사용자는 저장된 월말 스냅숏 목록과 스냅숏 요약을 읽는다(읽기 전용).

`GET /api/v1/forecast/snapshots`는 기준 월 목록(최근 순), `GET /api/v1/forecast/snapshots/{period}/
summary`는 실시간 요약과 같은 모양(basis=snapshot, as_of=생성 시각)이다.
값은 스냅숏을 만들 때의 값이라 이후 Deal·코드 이름이 바뀌어도 그대로다.
Vendor 조건은 받지 않는다. 스냅숏은 서버 CLI가 만든다(`test_forecast_snapshot_job.py`가
CLI를 검증하므로 여기서는 Given으로만 쓴다).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.codes import given_code_id, when_rename_code
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.forecast import (
    DEFAULT_KEYS,
    given_forecast_deal,
    given_sales_user,
    then_column_keys_are,
    then_every_row_cell_follows_the_columns,
    when_get_summary,
)
from tests.functional.steps.forecast_snapshot import (
    RUN_AT,
    given_snapshot_taken,
    then_snapshot_basis_is,
    then_snapshot_owner_ids_are,
    then_snapshot_periods_are,
    then_snapshot_row_is,
    when_get_snapshot_summary,
    when_list_snapshots,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _snapshot_of_two_owners(api: Api) -> tuple[int, int]:
    """kim(8월 pipeline 100·commit 7)·lee(9월 best 30)의 2026-09 스냅숏을 만들어 둔다."""
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=100, day="2026-08-15")
    await given_forecast_deal(api, owner=kim, forecast="commit", amount=7, day="2026-09-30")
    await given_forecast_deal(api, owner=lee, forecast="best", amount=30, day="2026-09-02")
    await given_snapshot_taken(api, at=RUN_AT)
    return kim, lee


async def test_snapshot_summary_has_snapshot_basis_and_the_live_shape(api: Api) -> None:
    """Scenario: 스냅숏 요약은 실시간 요약과 같은 모양이고 basis=snapshot, as_of=생성 시각이다."""
    # Given
    kim, lee = await _snapshot_of_two_owners(api)
    # When
    response = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=3)
    # Then
    then_status_is(response, 200)
    then_snapshot_basis_is(response, "2026-09", RUN_AT)
    then_column_keys_are(response, DEFAULT_KEYS)
    then_snapshot_owner_ids_are(response, [kim, lee])
    then_every_row_cell_follows_the_columns(response)
    then_snapshot_row_is(
        response, owner=kim, cells={"pipeline": (1, 100), "commit": (1, 7)}, open_total=(2, 107)
    )
    assert response.json()["total"]["owner"] is None


async def test_snapshot_summary_keeps_the_values_after_deals_change(api: Api) -> None:
    """Scenario: 스냅숏 뒤에 Deal이 늘어도 스냅숏 요약은 만들 때의 값이다(실시간은 바뀐다)."""
    # Given
    kim, _ = await _snapshot_of_two_owners(api)
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=900, day="2026-08-20")
    # When
    response = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=3)
    # Then
    then_status_is(response, 200)
    then_snapshot_row_is(
        response, owner=kim, cells={"pipeline": (1, 100), "commit": (1, 7)}, open_total=(2, 107)
    )
    live = await when_get_summary(api, year=2026, quarter=3)
    assert live.json()["basis"] == "live"
    then_snapshot_row_is(
        live, owner=kim, cells={"pipeline": (2, 1000), "commit": (1, 7)}, open_total=(3, 1007)
    )


async def test_snapshot_summary_keeps_the_code_names_of_that_time(api: Api) -> None:
    """Scenario: 스냅숏 뒤에 코드 이름을 바꿔도 스냅숏 열 이름은 옛 이름이고 key는 같다."""
    # Given
    await _snapshot_of_two_owners(api)
    commit_id = await given_code_id(api, kind="forecast", key="commit")
    renamed = await when_rename_code(api, code_id=commit_id, name="확정")
    assert renamed.status_code == 200, renamed.text
    # When
    response = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=3)
    # Then
    columns = {c["key"]: c["name"] for c in response.json()["columns"]}
    assert columns["commit"] == "Commit"
    live = await when_get_summary(api, year=2026, quarter=3)
    assert {c["key"]: c["name"] for c in live.json()["columns"]}["commit"] == "확정"


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"year": 2026, "quarter": 3}, (3, 137)),
        ({"year": 2026, "month": 8}, (1, 100)),
        ({"year": 2026, "month": 9}, (2, 37)),
        ({"year": 2026, "quarter": 4}, (0, 0)),
        ({"year": 2025}, (0, 0)),
    ],
    ids=["q3", "august", "september", "q4-empty", "other-year-empty"],
)
async def test_snapshot_summary_filters_by_period(
    api: Api, params: dict[str, int], expected: tuple[int, int]
) -> None:
    """Scenario: year·quarter·month는 저장된 월별 셀을 그 기간으로 모아 보여 준다."""
    # Given
    await _snapshot_of_two_owners(api)
    # When
    response = await when_get_snapshot_summary(api, "2026-09", **params)
    # Then
    then_status_is(response, 200)
    open_total = response.json()["total"]["open_total"]
    assert (open_total["count"], open_total["amount"]) == expected


async def test_snapshot_summary_owner_filter_keeps_one_row(api: Api) -> None:
    """Scenario: owner_user_id는 그 담당자 행만 남긴다."""
    # Given
    _, lee = await _snapshot_of_two_owners(api)
    # When
    response = await when_get_snapshot_summary(api, "2026-09", year=2026, owner_user_id=lee)
    # Then
    then_status_is(response, 200)
    then_snapshot_owner_ids_are(response, [lee])
    assert response.json()["total"]["open_total"] == {"count": 1, "amount": 30}


async def test_snapshot_list_has_period_and_taken_at(api: Api) -> None:
    """Scenario: 목록은 저장된 기준 월과 생성 시각을 담는다."""
    # Given
    await _snapshot_of_two_owners(api)
    # When
    response = await when_list_snapshots(api)
    # Then
    then_status_is(response, 200)
    then_snapshot_periods_are(response, ["2026-09"])
    assert set(response.json()["items"][0]) == {"period", "taken_at"}


async def test_snapshot_list_is_empty_before_the_first_run(api: Api) -> None:
    """Scenario: 스냅숏이 없으면 목록은 비어 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_list_snapshots(api)
    # Then
    then_status_is(response, 200)
    then_snapshot_periods_are(response, [])


@pytest.mark.parametrize("period", ["2026-08", "2027-01", "2026-9", "abc", "2026-13"])
async def test_a_missing_or_malformed_period_is_404(api: Api, period: str) -> None:
    """Scenario: 없는 기준 월이나 형식이 틀린 기준 월은 404(not-found)다."""
    # Given
    await _snapshot_of_two_owners(api)
    # When
    response = await when_get_snapshot_summary(api, period, year=2026)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def test_vendor_id_is_not_accepted_for_a_snapshot(api: Api) -> None:
    """Scenario: 스냅숏에는 Vendor가 없어 vendor_id를 주면 422(request-validation)다."""
    # Given
    await _snapshot_of_two_owners(api)
    # When
    response = await when_get_snapshot_summary(api, "2026-09", year=2026, vendor_id=1)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize(
    "params",
    [{}, {"year": 1899}, {"year": 2026, "quarter": 5}, {"year": 2026, "month": 13}],
)
async def test_invalid_snapshot_queries_are_422(api: Api, params: dict[str, int]) -> None:
    """Scenario: year 누락·범위 밖 값은 422(request-validation)다."""
    # Given
    await _snapshot_of_two_owners(api)
    # When
    response = await when_get_snapshot_summary(api, "2026-09", **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_quarter_with_month_is_422_invalid_value(api: Api) -> None:
    """Scenario: quarter와 month를 함께 주면 422(invalid-value)와 안내 문구다."""
    # Given
    await _snapshot_of_two_owners(api)
    # When
    response = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=1, month=1)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == "Quarter와 월은 함께 선택할 수 없습니다."


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_can_read_snapshots(api: Api, role: str) -> None:
    """Scenario: admin·sales·user 모두 목록과 요약을 200으로 읽는다."""
    # Given
    await _snapshot_of_two_owners(api)
    await given_logged_in_as(api, role=role)  # type: ignore[arg-type]
    # When
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026)
    # Then
    then_status_is(summary, 200)
    listing = await when_list_snapshots(api)
    then_status_is(listing, 200)
    then_snapshot_periods_are(listing, ["2026-09"])


async def test_anonymous_gets_401_for_both_snapshot_endpoints(api: Api) -> None:
    """Scenario: 로그인하지 않으면 목록도 요약도 401(unauthenticated)이다."""
    # Given
    await _snapshot_of_two_owners(api)
    await given_logged_out(api)
    # When
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026)
    # Then
    then_problem_is(summary, status=401, type_suffix="unauthenticated")
    then_problem_is(await when_list_snapshots(api), status=401, type_suffix="unauthenticated")
