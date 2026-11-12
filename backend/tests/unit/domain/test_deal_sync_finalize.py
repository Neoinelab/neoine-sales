"""계획 확정(`finalize_plan`, R-1): 프런트 `sync.test.ts` T-SYNC-09 이식.

사용자의 답(resolution)을 같은 규칙으로 재검증하고, 함께 바뀐 값과 notice를 만든다.
"""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync import (
    CoChange,
    SyncChange,
    SyncField,
    SyncPlan,
    SyncResolution,
    SyncState,
    finalize_plan,
    plan_change,
)
from app.domain.deal.values import RevenueAmount
from tests.support.expect import raises_with
from tests.support.sync_catalog import LOST, OPEN, WON, default_catalog

CATALOG = default_catalog()
REVENUE_REQUIRED = "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."
CHOICE_REQUIRED = "함께 바꿀 값을 선택하세요."
DAY = date(2026, 10, 20)


def _to_contract_completed(current: SyncState = OPEN) -> SyncPlan:
    return plan_change(current, SyncChange(SyncField.STATUS, "contract_completed"), CATALOG)


@pytest.mark.parametrize(
    "resolution",
    [
        None,
        SyncResolution(),
        SyncResolution(revenue_amount=0, revenue_date=DAY),
        SyncResolution(revenue_amount=-5, revenue_date=DAY),
        SyncResolution(revenue_amount=2**53, revenue_date=DAY),
        SyncResolution(revenue_amount=1000),
        SyncResolution(revenue_date=DAY),
    ],
)
def test_closing_without_a_valid_amount_and_date_is_rejected(
    resolution: SyncResolution | None,
) -> None:
    """종결 답에 금액·날짜가 없거나 금액이 0 이하·2^53이면 매출 필요 오류다.

    테스트 코드: DD-012, DD-016
    """
    # given: 계약완료로 바꾸는 계획
    plan = _to_contract_completed()

    # when·then: 금액·날짜가 빠졌거나 범위 밖인 답으로 확정한다
    #   → '매출금액과 매출일이 필요합니다' 오류다
    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        finalize_plan(OPEN, plan, resolution, CATALOG)


def test_closing_applies_both_values_the_revenue_and_reports_the_co_change() -> None:
    """종결 답이 맞으면 두 값과 매출이 적용되고 함께 바뀐 Forecast와 알림이 나온다.

    테스트 코드: DD-013
    """
    # given: Commit 상태의 계약완료 계획
    plan = _to_contract_completed()

    # when: 매출금액·매출일 답으로 확정한다
    applied = finalize_plan(
        OPEN,
        plan,
        SyncResolution(revenue_amount=900_000_000, revenue_date=DAY),
        CATALOG,
    )

    # then: 계약완료+Won, 매출 저장, 함께 바뀐 Forecast(commit→won), 알림 문구다
    assert applied.state == WON
    assert applied.revenue == (RevenueAmount(900_000_000), DAY)
    assert applied.co_changed == (CoChange(SyncField.FORECAST, "commit", "won"),)
    assert applied.notice == "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."


def test_closing_from_the_forecast_side_reports_the_status_as_the_co_change() -> None:
    """Forecast 쪽에서 종결하면 함께 바뀐 값은 Status다.

    테스트 코드: DD-014
    """
    # given: 가격협상 상태의 Won 계획
    plan = plan_change(OPEN, SyncChange(SyncField.FORECAST, "won"), CATALOG)

    # when: 매출 답으로 확정한다
    applied = finalize_plan(OPEN, plan, SyncResolution(revenue_amount=1, revenue_date=DAY), CATALOG)

    # then: 계약완료+Won이고 함께 바뀐 값은 Status(가격협상→계약완료), 알림이 같다
    assert applied.state == WON
    assert applied.co_changed == (
        CoChange(SyncField.STATUS, "price_negotiation", "contract_completed"),
    )
    assert applied.notice == "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."


def test_reopening_a_won_deal_requires_a_status_from_the_options() -> None:
    """Won에서 되돌릴 때 선택지에 있는 Status를 골라야 한다.

    테스트 코드: DD-017
    """
    # given: Won에서 Commit으로 바꾸는 계획
    plan = plan_change(WON, SyncChange(SyncField.FORECAST, "commit"), CATALOG)

    for resolution in (None, SyncResolution(), SyncResolution(status_key="contract_completed")):
        with raises_with(InvalidValueError, CHOICE_REQUIRED):
            # when: 답이 없거나 계약완료·없는 key로 확정한다
            finalize_plan(WON, plan, resolution, CATALOG)
    # then: '함께 바꿀 값을 선택하세요' 오류다
    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        finalize_plan(WON, plan, SyncResolution(status_key="no_such_status"), CATALOG)


def test_reopening_a_won_deal_changes_the_status_together() -> None:
    """Won에서 되돌릴 때 고른 Status가 함께 바뀌고 매출은 건드리지 않는다.

    테스트 코드: DD-017
    """
    # given: Won에서 Commit으로 바꾸는 계획
    plan = plan_change(WON, SyncChange(SyncField.FORECAST, "commit"), CATALOG)

    # when: POC완료를 골라 확정한다
    applied = finalize_plan(WON, plan, SyncResolution(status_key="poc_completed"), CATALOG)

    # then: POC완료+Commit, 매출 없음, 함께 바뀐 Status와 알림이 나온다
    assert applied.state == SyncState(status_key="poc_completed", forecast_key="commit")
    assert applied.revenue is None
    assert applied.co_changed == (
        CoChange(SyncField.STATUS, "contract_completed", "poc_completed"),
    )
    assert applied.notice == "Status가 'POC완료'로 함께 변경되었습니다."


def test_leaving_contract_completed_requires_a_forecast_other_than_won() -> None:
    """계약완료에서 벗어날 때 Won이 아닌 Forecast를 골라야 한다.

    테스트 코드: DD-019
    """
    # given: 계약완료에서 POC완료로 바꾸는 계획
    plan = plan_change(WON, SyncChange(SyncField.STATUS, "poc_completed"), CATALOG)

    for resolution in (
        None,
        SyncResolution(forecast_key="won"),
        SyncResolution(forecast_key="zzz"),
    ):
        with raises_with(InvalidValueError, CHOICE_REQUIRED):
            # when·then: 답이 없거나 Won·없는 key로 확정한다 → '함께 바꿀 값을 선택하세요' 오류다
            finalize_plan(WON, plan, resolution, CATALOG)


def test_leaving_contract_completed_changes_the_forecast_together() -> None:
    """계약완료에서 벗어날 때 고른 Forecast가 함께 바뀐다.

    테스트 코드: DD-019
    """
    # given: 계약완료에서 POC완료로 바꾸는 계획
    plan = plan_change(WON, SyncChange(SyncField.STATUS, "poc_completed"), CATALOG)

    # when: Best를 골라 확정한다
    applied = finalize_plan(WON, plan, SyncResolution(forecast_key="best"), CATALOG)

    # then: POC완료+Best이고 함께 바뀐 Forecast(won→best)와 알림이 나온다
    assert applied.state == SyncState(status_key="poc_completed", forecast_key="best")
    assert applied.co_changed == (CoChange(SyncField.FORECAST, "won", "best"),)
    assert applied.notice == "Forecast가 'Best'로 함께 변경되었습니다."


def test_picking_the_current_status_again_when_leaving_lost_changes_nothing_together() -> None:
    """Lost에서 되돌리며 현재 Status를 그대로 고르면 함께 바뀐 값과 알림이 없다.

    테스트 코드: DD-020
    """
    # given: 가격협상·Lost에서 Best로 바꾸는 계획
    plan = plan_change(LOST, SyncChange(SyncField.FORECAST, "best"), CATALOG)

    # when: 현재 Status(가격협상)를 골라 확정한다
    applied = finalize_plan(LOST, plan, SyncResolution(status_key="price_negotiation"), CATALOG)

    # then: 상태는 가격협상+Best이고 함께 바뀐 값·알림이 없다
    assert applied.state == SyncState(status_key="price_negotiation", forecast_key="best")
    assert applied.co_changed == ()
    assert applied.notice is None


def test_an_independent_change_ignores_the_resolution() -> None:
    """독립 변경은 함께 보낸 답을 무시한다.

    테스트 코드: DD-022
    """
    # given: Forecast를 Best로 바꾸는 독립 계획
    plan = plan_change(OPEN, SyncChange(SyncField.FORECAST, "best"), CATALOG)

    # when: 매출 답을 함께 주고 확정한다
    applied = finalize_plan(OPEN, plan, SyncResolution(revenue_amount=5), CATALOG)

    # then: 요청한 값만 바뀌고 매출·함께 바뀐 값·알림이 없다
    assert applied.state == SyncState(status_key="price_negotiation", forecast_key="best")
    assert (applied.revenue, applied.co_changed, applied.notice) == (None, (), None)


def test_the_same_value_changes_nothing() -> None:
    """같은 값으로 바꾸면 아무것도 바뀌지 않는다.

    테스트 코드: DD-023
    """
    # given: Won 상태에서 Won으로 바꾸는 계획
    plan = plan_change(WON, SyncChange(SyncField.FORECAST, "won"), CATALOG)

    # when: 답 없이 확정한다
    applied = finalize_plan(WON, plan, None, CATALOG)

    # then: 상태 그대로이고 매출·함께 바뀐 값·알림이 없다
    assert (applied.state, applied.revenue, applied.co_changed, applied.notice) == (
        WON,
        None,
        (),
        None,
    )


def test_the_notice_uses_the_current_code_names_and_their_josa() -> None:
    """알림은 현재 코드 이름과 받침에 맞는 조사(로/으로)를 쓴다.

    테스트 코드: DD-025
    """
    # given: 계약완료를 '수주확정', Won을 '성사'로 바꾼 코드 목록
    renamed = default_catalog(contract_completed="수주확정", won="성사")
    plan = plan_change(OPEN, SyncChange(SyncField.STATUS, "contract_completed"), renamed)

    # when: 종결 답으로 확정한다
    applied = finalize_plan(OPEN, plan, SyncResolution(revenue_amount=1, revenue_date=DAY), renamed)

    # then: 알림이 새 이름과 '으로'·'로' 조사로 나온다
    assert applied.notice == "Status가 '수주확정'으로, Forecast가 '성사'로 함께 변경되었습니다."
