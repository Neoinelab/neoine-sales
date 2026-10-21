"""Feature: 로그인한 사용자는 Forecast 요약에서 담당자별·Forecast 코드별 건수와 금액을 본다.

기간은 Expected Close(revenue_date)의 연 / 연+분기 / 연+월(양끝 포함)이다. 열은 Lost를 뺀 Forecast
코드 목록(코드 order 순)이고 Total(Open)은 Open 열의 합(Won 제외)이다. Lost는 어디에도 들어가지
않는다. 행은 기간 안에 Open 또는 Won Deal이 있는 담당자만(퇴사자 포함) 재직자 먼저·이름 순이다.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import (
    given_code_created,
    given_code_id,
    when_rename_code,
)
from tests.functional.steps.common import then_status_is
from tests.functional.steps.forecast import (
    DEFAULT_KEYS,
    given_forecast_deal,
    given_sales_user,
    then_column_keys_are,
    then_every_row_cell_follows_the_columns,
    then_owner_ids_are,
    then_row_is,
    then_total_is,
    when_get_summary,
)
from tests.functional.steps.users import given_user_deleted
from tests.functional.steps.vendors import given_vendor

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_summary_groups_deals_by_owner_and_forecast(api: Api) -> None:
    """Scenario: 담당자·Forecast 코드별 건수와 금액이 나오고 Lost와 기간 밖 Deal은 빠진다."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    park = await given_sales_user(api, "park")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=100, day="2026-11-15")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=40, day="2026-10-01")
    await given_forecast_deal(api, owner=kim, forecast="commit", amount=7, day="2026-12-31")
    await given_forecast_deal(api, owner=kim, forecast="won", amount=500, day="2026-11-20")
    await given_forecast_deal(api, owner=kim, forecast="lost", amount=999, day="2026-11-01")
    await given_forecast_deal(api, owner=kim, forecast="pipeline", amount=5000, day="2026-09-30")
    await given_forecast_deal(api, owner=lee, forecast="most_likely", amount=30, day="2026-11-02")
    await given_forecast_deal(api, owner=park, forecast="lost", amount=77, day="2026-11-03")
    # When
    response = await when_get_summary(api, year=2026, quarter=4)
    # Then
    then_status_is(response, 200)
    then_column_keys_are(response, DEFAULT_KEYS)
    then_owner_ids_are(response, [kim, lee])  # park은 Lost뿐이라 행이 없다
    then_row_is(
        response,
        owner=kim,
        cells={"pipeline": (2, 140), "commit": (1, 7), "won": (1, 500)},
        open_total=(3, 147),
    )
    then_row_is(response, owner=lee, cells={"most_likely": (1, 30)}, open_total=(1, 30))
    then_total_is(
        response,
        cells={"pipeline": (2, 140), "commit": (1, 7), "most_likely": (1, 30), "won": (1, 500)},
        open_total=(4, 177),
    )
    then_every_row_cell_follows_the_columns(response)


async def test_resigned_owner_stays_after_active_owners(api: Api) -> None:
    """Scenario: 퇴사한 담당자도 행에 남고 label에 (퇴사)가 붙으며 재직자보다 뒤에 온다."""
    # Given
    await given_logged_in_as(api, role="admin")
    gone = await given_sales_user(api, "aaa-gone")
    kim = await given_sales_user(api, "kim")
    await given_forecast_deal(api, owner=gone, amount=1)
    await given_forecast_deal(api, owner=kim, amount=2)
    await given_user_deleted(api, gone)  # 연결된 Deal이 있어 퇴사 처리된다
    # When
    response = await when_get_summary(api, year=2026)
    # Then
    then_status_is(response, 200)
    then_owner_ids_are(response, [kim, gone])
    resigned = response.json()["rows"][1]["owner"]
    assert resigned["resigned"] is True
    assert resigned["label"].endswith("(퇴사)")
    assert response.json()["rows"][0]["owner"]["resigned"] is False


async def test_renamed_and_added_codes_appear_in_columns(api: Api) -> None:
    """Scenario: 이름을 바꾼 코드는 새 이름, 추가한 Open 코드는 새 열로 나온다(셀 key는 그대로)."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    verbal = await given_code_created(api, kind="forecast", name="Verbal")
    commit_id = await given_code_id(api, kind="forecast", key="commit")
    renamed = await when_rename_code(api, code_id=commit_id, name="확정")
    assert renamed.status_code == 200, renamed.text
    await given_forecast_deal(api, owner=kim, forecast="commit", amount=7)
    await given_forecast_deal(api, owner=kim, forecast=str(verbal["key"]), amount=3)
    # When
    response = await when_get_summary(api, year=2026, quarter=4)
    # Then
    then_status_is(response, 200)
    columns = {c["key"]: c for c in response.json()["columns"]}
    assert columns["commit"]["name"] == "확정"
    assert columns[str(verbal["key"])]["name"] == "Verbal"
    assert columns[str(verbal["key"])]["outcome"] == "open"
    then_row_is(
        response,
        owner=kim,
        cells={"commit": (1, 7), str(verbal["key"]): (1, 3)},
        open_total=(2, 10),
    )


@pytest.mark.parametrize(
    ("params", "expected_amount"),
    [
        ({"year": 2026, "quarter": 3}, 1),
        ({"year": 2026, "quarter": 4}, 2),
        ({"year": 2026, "month": 12}, 2),
        ({"year": 2026, "month": 9}, 1),
        ({"year": 2027, "quarter": 1}, 12),
        ({"year": 2027, "month": 1}, 4),
        ({"year": 2027, "quarter": 2}, 16),
        ({"year": 2026}, 3),
    ],
    ids=["q3", "q4", "dec", "sep", "next-q1", "next-jan", "next-q2", "year-2026"],
)
async def test_period_boundaries_put_deals_in_the_right_bucket(
    api: Api, params: dict[str, int], expected_amount: int
) -> None:
    """Scenario: 12-31은 Q4·12월, 01-01은 다음 해 Q1·1월, 분기·월 밖 날짜는 제외된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    for amount, day in (
        (1, "2026-09-30"),
        (2, "2026-12-31"),
        (4, "2027-01-01"),
        (8, "2027-03-31"),
        (16, "2027-04-01"),
    ):
        await given_forecast_deal(api, owner=kim, amount=amount, day=day)
    # When
    response = await when_get_summary(api, **params)
    # Then
    then_status_is(response, 200)
    assert response.json()["total"]["open_total"]["amount"] == expected_amount


async def test_owner_and_vendor_conditions_narrow_the_rows(api: Api) -> None:
    """Scenario: owner_user_id는 그 담당자 행만, vendor_id는 그 Vendor의 Deal만 집계한다."""
    # Given
    sap = await given_vendor(api, "SAP", ["S/4HANA"])
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    await given_forecast_deal(api, owner=kim, amount=1, vendor_id=sap.id)
    await given_forecast_deal(api, owner=kim, amount=2)
    await given_forecast_deal(api, owner=lee, amount=4, vendor_id=sap.id)
    # When
    response = await when_get_summary(api, year=2026, owner_user_id=kim, vendor_id=sap.id)
    # Then
    then_status_is(response, 200)
    then_owner_ids_are(response, [kim])
    then_total_is(response, cells={"pipeline": (1, 1)}, open_total=(1, 1))


async def test_year_without_deals_returns_columns_and_zero_total(api: Api) -> None:
    """Scenario: Deal이 없는 기간도 열과 0인 합계를 돌려준다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_get_summary(api, year=2031)
    # Then
    then_status_is(response, 200)
    then_column_keys_are(response, DEFAULT_KEYS)
    then_owner_ids_are(response, [])
    then_total_is(response, cells={}, open_total=(0, 0))


async def test_as_of_is_the_server_time_and_basis_is_live(api: Api) -> None:
    """Scenario: 응답은 서버 현재 시각(오프셋 포함)과 basis=live를 담는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_summary(api, year=2026)
    # Then
    body = response.json()
    then_status_is(response, 200)
    assert body["basis"] == "live"
    assert body["snapshot_period"] is None
    as_of = datetime.fromisoformat(body["as_of"])
    assert as_of.utcoffset() is not None
    assert as_of == api.clock.now()
