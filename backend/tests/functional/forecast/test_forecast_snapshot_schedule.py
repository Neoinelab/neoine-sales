"""Feature: 서버가 주기적으로 전월 Forecast 스냅숏을 확인해 없으면 저장하고 있으면 그대로 둔다.

스냅숏을 만드는 주체는 HTTP API가 아니라 서버 안의 주기 확인이므로 이 feature의 When은
"서버가 스냅숏 확인을 한 번 한다"이다(같은 DB에 실제 Container를 조립해 확인 유스케이스를 실행).
결과는 읽기 API로 관찰한다. 기준 월은 확인 시점(서버 OS 로컬 업무 날짜)의 전월이고, 셀은 확인
시점의 모든 Deal(기간 제한 없음, Lost 포함)을 (revenue 연, 월, 담당자, Forecast key)로 묶은
건수·금액이다. 전월분이 이미 있으면 아무것도 바꾸지 않는다(생성 시각 유지). 앱이 꺼져 있어 놓친
전월분은 다음 확인(몇 번째든 그달 안)에서 만들어지고, 전전월 이전은 만들지 않는다.
스냅숏은 그 시점의 Forecast 코드 목록(key·이름·outcome·순서)도 함께 저장하고, 요약의 열은
그 저장본에서 만든다(Lost 제외). Deal이 없던 코드도 0건 열로 보이고, 나중에 코드 이름이
바뀌어도 옛 이름이 남는다.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import (
    given_code_created,
    given_code_id,
    given_code_list,
    when_rename_code,
)
from tests.functional.steps.common import then_body_is, then_status_is
from tests.functional.steps.deals import given_deal_deleted
from tests.functional.steps.forecast import (
    DEFAULT_KEYS,
    given_forecast_deal,
    given_sales_user,
    then_column_keys_are,
    then_every_row_cell_follows_the_columns,
    when_get_summary,
)
from tests.functional.steps.forecast_snapshot import (
    AUGUST_RUN_AT,
    LATER_RUN_AT,
    MID_MONTH_AT,
    RUN_AT,
    given_snapshot_taken,
    row_owner,
    then_snapshot_owner_ids_are,
    then_snapshot_periods_are,
    then_snapshot_row_is,
    then_snapshot_taken_at_is,
    when_get_snapshot_summary,
    when_list_snapshots,
    when_snapshot_check_runs,
)
from tests.functional.steps.users import when_delete_user

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _admin_with_deals(api: Api) -> tuple[int, int]:
    """kim·lee와 Deal 여럿(기간·Forecast가 다양, Lost 포함). admin 로그인 상태로 남는다."""
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=100, day="2026-08-15")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=40, day="2026-08-31")
    await given_forecast_deal(api, owner=kim, forecast="commit", amount=7, day="2026-09-30")
    await given_forecast_deal(api, owner=kim, forecast="won", amount=500, day="2026-08-20")
    await given_forecast_deal(api, owner=kim, forecast="lost", amount=999, day="2026-08-01")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=5000, day="2026-11-01")
    await given_forecast_deal(api, owner=lee, forecast="best", amount=30, day="2026-09-02")
    return kim, lee


async def test_missing_previous_month_is_taken_from_all_deals(api: Api) -> None:
    """Scenario: 10월 1일 00:05 확인은 9월 기준 스냅숏 1건을 만들고 셀은 모든 Deal의 묶음이다."""
    # Given
    kim, lee = await _admin_with_deals(api)
    # When
    result = await when_snapshot_check_runs(api, at=RUN_AT)
    # Then
    assert result.outcome.value == "taken"
    listing = await when_list_snapshots(api)
    then_status_is(listing, 200)
    then_snapshot_periods_are(listing, ["2026-09"])
    then_snapshot_taken_at_is(listing, 0, RUN_AT)
    q3 = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=3)
    then_snapshot_owner_ids_are(q3, [kim, lee])
    then_snapshot_row_is(
        q3,
        owner=kim,
        cells={"pipeline": (2, 140), "commit": (1, 7), "won": (1, 500)},
        open_total=(3, 147),
    )
    then_snapshot_row_is(q3, owner=lee, cells={"best": (1, 30)}, open_total=(1, 30))
    q4 = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=4)
    then_snapshot_row_is(q4, owner=kim, cells={"pipeline": (1, 5000)}, open_total=(1, 5000))


async def test_existing_previous_month_is_left_unchanged_by_a_later_check(api: Api) -> None:
    """Scenario: 전월분이 이미 있으면 다시 확인해도 생성 시각과 셀이 그대로다(Deal이 바뀌었어도)."""
    # Given
    kim, lee = await _admin_with_deals(api)
    await given_snapshot_taken(api, at=RUN_AT)
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=1000, day="2026-08-10")
    # When
    result = await when_snapshot_check_runs(api, at=LATER_RUN_AT)
    # Then
    assert result.outcome.value == "already-exists"
    listing = await when_list_snapshots(api)
    then_snapshot_periods_are(listing, ["2026-09"])
    then_snapshot_taken_at_is(listing, 0, RUN_AT)
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=3)
    then_snapshot_row_is(
        summary,
        owner=kim,
        cells={"pipeline": (2, 140), "commit": (1, 7), "won": (1, 500)},
        open_total=(3, 147),
    )
    then_snapshot_row_is(summary, owner=lee, cells={"best": (1, 30)}, open_total=(1, 30))


async def test_start_in_the_middle_of_the_month_takes_the_missed_previous_month(api: Api) -> None:
    """Scenario: 월초에 앱이 꺼져 있었어도 그달 15일 첫 확인에서 전월분이 만들어진다."""
    # Given
    await _admin_with_deals(api)
    # When
    result = await when_snapshot_check_runs(api, at=MID_MONTH_AT)
    # Then
    assert result.outcome.value == "taken"
    listing = await when_list_snapshots(api)
    then_snapshot_periods_are(listing, ["2026-09"])
    then_snapshot_taken_at_is(listing, 0, MID_MONTH_AT)


async def test_months_before_the_previous_month_are_never_backfilled(api: Api) -> None:
    """Scenario: 전전월 이전은 만들지 않는다(10월 확인은 9월분만 만든다)."""
    # Given
    await _admin_with_deals(api)
    # When
    await when_snapshot_check_runs(api, at=MID_MONTH_AT)
    # Then
    then_snapshot_periods_are(await when_list_snapshots(api), ["2026-09"])


async def test_lost_deals_are_stored_but_never_shown(api: Api) -> None:
    """Scenario: Lost만 가진 담당자는 스냅숏에서도 행이 없고 Lost는 열·합계에 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    park = await given_sales_user(api, "park")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=5, day="2026-08-15")
    await given_forecast_deal(api, owner=kim, forecast="lost", amount=999, day="2026-08-16")
    await given_forecast_deal(api, owner=park, forecast="lost", amount=77, day="2026-08-17")
    # When
    await when_snapshot_check_runs(api, at=RUN_AT)
    # Then
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026)
    then_snapshot_owner_ids_are(summary, [kim])
    assert "lost" not in [c["key"] for c in summary.json()["columns"]]
    assert summary.json()["total"]["open_total"] == {"count": 1, "amount": 5}


async def test_deleting_a_deal_after_the_snapshot_keeps_the_stored_cells(api: Api) -> None:
    """Scenario: 스냅숏을 만든 뒤 지운 Deal의 셀은 스냅숏에 그대로 남는다(다시 확인해도)."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_forecast_deal(api, owner=kim, amount=1, day="2026-08-15")
    gone = await given_forecast_deal(api, owner=kim, amount=2, day="2026-08-16")
    await given_snapshot_taken(api, at=RUN_AT)
    await given_deal_deleted(api, gone["code"])
    # When
    await when_snapshot_check_runs(api, at=LATER_RUN_AT)
    # Then
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026)
    assert summary.json()["total"]["open_total"] == {"count": 2, "amount": 3}


async def test_codes_without_deals_are_zero_columns_in_the_snapshot(api: Api) -> None:
    """Scenario: Deal이 없던 코드(best·most_likely·commit)도 스냅숏에서 0건 열로 보인다."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=5, day="2026-08-15")
    await given_snapshot_taken(api, at=RUN_AT)
    # When
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=3)
    # Then
    then_status_is(summary, 200)
    then_column_keys_are(summary, DEFAULT_KEYS)
    then_every_row_cell_follows_the_columns(summary)
    then_snapshot_row_is(summary, owner=kim, cells={"pipeline": (1, 5)}, open_total=(1, 5))
    assert summary.json()["total"]["open_total"] == {"count": 1, "amount": 5}


async def test_a_period_without_any_deal_still_shows_every_stored_column(api: Api) -> None:
    """Scenario: 선택한 기간에 Deal이 하나도 없어도 열은 저장된 코드 목록 그대로 보인다."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=5, day="2026-08-15")
    await given_snapshot_taken(api, at=RUN_AT)
    # When
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=1)
    # Then
    then_status_is(summary, 200)
    then_column_keys_are(summary, DEFAULT_KEYS)
    then_snapshot_owner_ids_are(summary, [])
    assert summary.json()["total"]["open_total"] == {"count": 0, "amount": 0}


async def test_a_code_renamed_after_the_snapshot_keeps_its_old_name_in_it(api: Api) -> None:
    """Scenario: 스냅숏 뒤에 코드 이름을 바꿔도 스냅숏은 옛 이름, 실시간은 새 이름이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_forecast_deal(api, owner=kim, forecast="commit", amount=7, day="2026-08-15")
    old_name = next(
        c["name"] for c in await given_code_list(api, kind="forecast") if c["key"] == "commit"
    )
    await given_snapshot_taken(api, at=RUN_AT)
    commit_id = await given_code_id(api, kind="forecast", key="commit")
    renamed = await when_rename_code(api, code_id=commit_id, name="확정")
    assert renamed.status_code == 200, renamed.text
    # When
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026, quarter=3)
    # Then
    then_status_is(summary, 200)
    names = {c["key"]: c["name"] for c in summary.json()["columns"]}
    assert names["commit"] == old_name
    assert old_name != "확정"
    then_snapshot_row_is(summary, owner=kim, cells={"commit": (1, 7)}, open_total=(1, 7))
    live = await when_get_summary(api, year=2026, quarter=3)
    assert {c["key"]: c["name"] for c in live.json()["columns"]}["commit"] == "확정"


async def test_a_code_added_after_the_snapshot_is_not_a_column_of_it(api: Api) -> None:
    """Scenario: 스냅숏 뒤에 추가한 코드는 그 스냅숏의 열이 아니다(저장 당시 목록 그대로)."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=5, day="2026-08-15")
    await given_snapshot_taken(api, at=RUN_AT)
    added = await given_code_created(api, kind="forecast", name="Verbal")
    # When
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026)
    # Then
    then_status_is(summary, 200)
    then_column_keys_are(summary, DEFAULT_KEYS)
    assert str(added["key"]) not in [c["key"] for c in summary.json()["columns"]]


async def test_snapshots_of_two_months_list_newest_first(api: Api) -> None:
    """Scenario: 9월 1일 확인(8월분)과 10월 1일 확인(9월분)이 쌓이면 목록은 최근 기준 월부터다."""
    # Given
    await _admin_with_deals(api)
    await given_snapshot_taken(api, at=AUGUST_RUN_AT)
    # When
    result = await when_snapshot_check_runs(api, at=RUN_AT)
    # Then
    assert result.outcome.value == "taken"
    listing = await when_list_snapshots(api)
    then_snapshot_periods_are(listing, ["2026-09", "2026-08"])
    taken = [datetime.fromisoformat(i["taken_at"]) for i in listing.json()["items"]]
    assert taken == [RUN_AT, AUGUST_RUN_AT]


async def test_user_referenced_by_snapshot_is_resigned_not_deleted(api: Api) -> None:
    """Scenario: 스냅숏에만 남은 담당자를 삭제하면 퇴사 처리되고 스냅숏에도 남는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    deal = await given_forecast_deal(api, owner=kim, amount=5, day="2026-08-15")
    await given_snapshot_taken(api, at=RUN_AT)
    await given_deal_deleted(api, deal["code"])  # 이제 kim을 가리키는 것은 스냅숏 셀뿐이다
    # When
    response = await when_delete_user(api, kim)
    # Then
    then_status_is(response, 200)
    then_body_is(response, {"outcome": "resigned"})
    summary = await when_get_snapshot_summary(api, "2026-09", year=2026)
    owner = row_owner(summary, kim)
    assert owner["resigned"] is True
    assert owner["label"].endswith("(퇴사)")


async def test_user_without_any_reference_is_still_physically_deleted(api: Api) -> None:
    """Scenario: 스냅숏이 있어도 그 사용자를 가리키는 셀이 없으면 물리 삭제된다(대조군)."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    await given_forecast_deal(api, owner=kim, amount=5, day="2026-08-15")
    await given_snapshot_taken(api, at=RUN_AT)
    # When
    response = await when_delete_user(api, lee)
    # Then
    then_body_is(response, {"outcome": "deleted"})
