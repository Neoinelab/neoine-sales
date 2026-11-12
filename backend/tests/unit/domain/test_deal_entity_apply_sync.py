"""Deal.apply_sync: 확정된 Status/Forecast와 매출금액·매출일(있으면)을 반영한다."""

from datetime import date

from app.domain.deal.sync import SyncApplied, SyncState
from app.domain.deal.values import RevenueAmount
from tests.factories import make_deal

WON = SyncState(status_key="contract_completed", forecast_key="won")


def test_applying_a_closing_sets_the_state_the_amount_and_the_date() -> None:
    """마감 동기화를 적용하면 상태와 매출금액·매출일이 바뀌는지 확인한다."""
    # given: 매출금액·매출일이 있는 Deal과 마감 결과가 있다
    deal = make_deal(revenue_amount=100, revenue_date=date(2026, 6, 30))
    applied = SyncApplied(
        state=WON,
        revenue=(RevenueAmount(900_000_000), date(2026, 10, 20)),
        co_changed=(),
        notice=None,
    )

    # when: 마감 결과를 적용한다
    deal.apply_sync(applied)

    # then: 상태, 매출금액, 매출일이 마감 값이다
    assert deal.sync == WON
    assert deal.details.revenue_amount.value == 900_000_000
    assert deal.details.revenue_date == date(2026, 10, 20)


def test_applying_without_revenue_keeps_the_amount_and_the_date() -> None:
    """매출 정보가 없는 동기화는 기존 매출금액·매출일을 유지하는지 확인한다."""
    # given: 마감된 Deal이 있다
    deal = make_deal(
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=777,
        revenue_date=date(2026, 9, 1),
    )
    reopened = SyncState(status_key="price_negotiation", forecast_key="commit")

    # when: 매출 없이 재오픈 상태를 적용한다
    deal.apply_sync(SyncApplied(state=reopened, revenue=None, co_changed=(), notice=None))

    # then: 상태만 바뀌고 매출금액·매출일은 그대로다
    assert deal.sync == reopened
    assert (deal.details.revenue_amount.value, deal.details.revenue_date) == (777, date(2026, 9, 1))


def test_applying_keeps_the_other_details() -> None:
    """동기화를 적용해도 다른 상세 값은 유지되는지 확인한다."""
    # given: 이름과 조달 정보가 있는 Deal이 있다
    deal = make_deal(name="ERP", procurement="조달청 입찰")

    # when: 다른 상태를 적용한다
    deal.apply_sync(
        SyncApplied(
            state=SyncState(status_key="introduction", forecast_key="best"),
            revenue=None,
            co_changed=(),
            notice=None,
        )
    )

    # then: 이름과 조달 정보는 그대로다
    assert (deal.details.name, deal.details.procurement) == ("ERP", "조달청 입찰")
