"""Deal.apply_sync(AC-19·21): 확정된 Status/Forecast와 매출금액·매출일(있으면)을 반영한다."""

from datetime import date

from app.domain.deal.sync import SyncApplied, SyncState
from app.domain.deal.values import RevenueAmount
from tests.factories import make_deal

WON = SyncState(status_key="contract_completed", forecast_key="won")


def test_applying_a_closing_sets_the_state_the_amount_and_the_date() -> None:
    deal = make_deal(revenue_amount=100, revenue_date=date(2026, 6, 30))
    applied = SyncApplied(
        state=WON,
        revenue=(RevenueAmount(900_000_000), date(2026, 10, 20)),
        co_changed=(),
        notice=None,
    )

    deal.apply_sync(applied)

    assert deal.sync == WON
    assert deal.details.revenue_amount.value == 900_000_000
    assert deal.details.revenue_date == date(2026, 10, 20)


def test_applying_without_revenue_keeps_the_amount_and_the_date() -> None:
    deal = make_deal(
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=777,
        revenue_date=date(2026, 9, 1),
    )
    reopened = SyncState(status_key="price_negotiation", forecast_key="commit")

    deal.apply_sync(SyncApplied(state=reopened, revenue=None, co_changed=(), notice=None))

    assert deal.sync == reopened
    assert (deal.details.revenue_amount.value, deal.details.revenue_date) == (777, date(2026, 9, 1))


def test_applying_keeps_the_other_details() -> None:
    deal = make_deal(name="ERP", procurement="조달청 입찰")

    deal.apply_sync(
        SyncApplied(
            state=SyncState(status_key="introduction", forecast_key="best"),
            revenue=None,
            co_changed=(),
            notice=None,
        )
    )

    assert (deal.details.name, deal.details.procurement) == ("ERP", "조달청 입찰")
