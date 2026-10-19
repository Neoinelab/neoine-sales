"""Deal의 Status 진입 기록(P3 AC-08·09): `touch`가 Status key 변경을 감지해 진입 시각을 갱신한다.

Status를 바꾸는 모든 경로(폼 저장, 단일 변경, Action 등록)는 변경이 있으면 `touch(now)`를 부른다.
그래서 진입 기록의 규칙은 `touch` 계약 하나로 검증한다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.domain.deal.status_entry import StatusEntry
from app.domain.deal.sync import SyncApplied, SyncState
from app.domain.deal.values import RevenueAmount
from tests.factories import NOW, later, make_deal, make_deal_details, make_sync

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal

WON = SyncState(status_key="contract_completed", forecast_key="won")


def _revise_sync(sync: SyncState, deal: Deal) -> None:
    deal.revise(details=deal.details, sync=sync, customer_id=deal.customer_id, bant=deal.bant)


def test_create_records_entry_at_registration() -> None:
    deal = make_deal(NOW, status_key="introduction")

    assert deal.status_entry == StatusEntry(status_key="introduction", changed_at=NOW)
    assert deal.status_changed_at == NOW


def test_touch_after_status_change_records_now() -> None:
    deal = make_deal(NOW, status_key="prospecting")
    _revise_sync(make_sync("introduction", "pipeline"), deal)

    deal.touch(later(300))

    assert deal.status_entry == StatusEntry(status_key="introduction", changed_at=later(300))
    assert deal.status_changed_at == later(300)
    assert deal.updated_at == later(300)


def test_touch_after_status_change_keeps_the_invariant_between_entry_and_sync() -> None:
    deal = make_deal(NOW, status_key="prospecting")
    _revise_sync(make_sync("price_negotiation", "commit"), deal)

    deal.touch(later(1))

    assert deal.status_entry.status_key == deal.sync.status_key


def test_touch_without_status_change_keeps_entry_when_only_forecast_changes() -> None:
    deal = make_deal(NOW, status_key="prospecting", forecast_key="pipeline")
    _revise_sync(make_sync("prospecting", "best"), deal)

    deal.touch(later(300))

    assert deal.status_entry == StatusEntry(status_key="prospecting", changed_at=NOW)
    assert deal.updated_at == later(300)


def test_touch_without_status_change_keeps_entry_when_other_fields_change() -> None:
    deal = make_deal(NOW)
    deal.revise(
        details=make_deal_details(name="다른 이름", revenue_amount=1),
        sync=deal.sync,
        customer_id=deal.customer_id,
        bant=deal.bant,
    )

    deal.touch(later(60))

    assert deal.status_changed_at == NOW


def test_touch_alone_keeps_entry() -> None:
    deal = make_deal(NOW)

    deal.touch(later(60))

    assert deal.status_entry == StatusEntry(status_key="prospecting", changed_at=NOW)


def test_touch_after_resending_the_same_status_keeps_entry() -> None:
    deal = make_deal(NOW, status_key="prospecting")
    _revise_sync(make_sync("prospecting", "pipeline"), deal)

    deal.touch(later(60))

    assert deal.status_changed_at == NOW


def test_a_second_status_change_moves_the_entry_again() -> None:
    deal = make_deal(NOW, status_key="prospecting")
    _revise_sync(make_sync("introduction", "pipeline"), deal)
    deal.touch(later(60))

    _revise_sync(make_sync("prospecting", "pipeline"), deal)
    deal.touch(later(120))

    assert deal.status_entry == StatusEntry(status_key="prospecting", changed_at=later(120))


def test_apply_sync_closing_moves_status_entry() -> None:
    deal = make_deal(NOW, status_key="prospecting", forecast_key="pipeline")
    applied = SyncApplied(
        state=WON,
        revenue=(RevenueAmount(900_000_000), date(2026, 10, 20)),
        co_changed=(),
        notice=None,
    )

    deal.apply_sync(applied)
    deal.touch(later(90))

    assert deal.status_entry == StatusEntry(status_key="contract_completed", changed_at=later(90))


def test_apply_sync_forecast_only_change_keeps_status_entry() -> None:
    deal = make_deal(NOW, status_key="prospecting", forecast_key="pipeline")

    deal.apply_sync(
        SyncApplied(
            state=make_sync("prospecting", "best"), revenue=None, co_changed=(), notice=None
        )
    )
    deal.touch(later(90))

    assert deal.status_changed_at == NOW


def test_apply_sync_reopening_a_closed_deal_moves_status_entry() -> None:
    deal = make_deal(NOW, status_key="contract_completed", forecast_key="won")
    reopened = make_sync("price_negotiation", "commit")

    deal.apply_sync(SyncApplied(state=reopened, revenue=None, co_changed=(), notice=None))
    deal.touch(later(30))

    assert deal.status_entry == StatusEntry(status_key="price_negotiation", changed_at=later(30))
