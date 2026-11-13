"""Deal의 Status 진입 기록: `touch`가 Status key 변경을 감지해 진입 시각을 갱신한다.

Status를 바꾸는 모든 경로(폼 저장, 단일 변경, Action 등록)는 변경이 있으면 `touch(now)`를 부른다.
그래서 진입 기록의 규칙은 `touch` 계약 하나로 검증한다. 진입일은 요청 시각의 업무 날짜(date)다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.domain.deal.status_entry import StatusEntry
from app.domain.deal.sync import SyncApplied, SyncState
from app.domain.deal.values import RevenueAmount
from tests.factories import NOW, later, make_deal, make_deal_details, make_sync

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.domain.deal.entities import Deal

TODAY = date(2026, 1, 1)  # NOW(UTC 09:00)의 서울 업무 날짜


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


WON = SyncState(status_key="contract_completed", forecast_key="won")


def _revise_sync(sync: SyncState, deal: Deal) -> None:
    deal.revise(details=deal.details, sync=sync, customer_id=deal.customer_id, bant=deal.bant)


def test_create_records_entry_at_registration() -> None:
    """Deal을 만들면 진입 기록이 등록 시각과 Status로 남는다.

    테스트 코드: RK-032
    """
    # when: Deal을 만든다
    deal = make_deal(NOW, status_key="introduction")

    # then: 진입 기록과 status_changed_on이 등록일(업무 날짜)이다
    assert deal.status_entry == StatusEntry(status_key="introduction", changed_on=TODAY)
    assert deal.status_changed_on == TODAY


def test_touch_after_status_change_records_now() -> None:
    """Status가 바뀐 뒤 touch하면 진입일이 그 시각의 업무 날짜가 된다.

    테스트 코드: RK-033
    """
    # given: Status를 prospecting에서 introduction으로 고친 Deal이다
    deal = make_deal(NOW, status_key="prospecting")
    _revise_sync(make_sync("introduction", "pipeline"), deal)

    # when: 이틀 뒤(1월 3일)에 touch(now)를 부른다
    deal.touch(later(2 * 86400))

    # then: 진입일은 1월 3일(date)이고 수정 시각은 그 시각이다
    assert deal.status_entry == StatusEntry(status_key="introduction", changed_on=date(2026, 1, 3))
    assert deal.status_changed_on == date(2026, 1, 3)
    assert deal.updated_at == later(2 * 86400)


def test_entry_date_is_the_business_date_not_the_utc_date() -> None:
    """진입일은 서버 시간대의 날짜다(UTC 1월 1일 16:00 = 서울 1월 2일 01:00).

    테스트 코드: RK-032
    """
    # given: Status를 고친 Deal이다
    deal = make_deal(NOW, status_key="prospecting")
    _revise_sync(make_sync("introduction", "pipeline"), deal)

    # when: UTC 날짜로는 1월 1일, 서울 날짜로는 1월 2일인 시각에 touch한다
    deal.touch(datetime(2026, 1, 1, 16, 0, tzinfo=UTC))

    # then: 진입일은 서울 날짜 1월 2일이다
    assert deal.status_changed_on == date(2026, 1, 2)


def test_touch_after_status_change_keeps_the_invariant_between_entry_and_sync() -> None:
    """Status가 바뀐 뒤 touch하면 진입 기록의 Status와 동기화 상태의 Status가 같다."""
    # given: Status를 price_negotiation으로 고친 Deal이다
    deal = make_deal(NOW, status_key="prospecting")
    _revise_sync(make_sync("price_negotiation", "commit"), deal)

    # when: touch(now)를 부른다
    deal.touch(later(1))

    # then: 진입 기록의 Status가 동기화 상태의 Status와 같다
    assert deal.status_entry.status_key == deal.sync.status_key


def test_touch_without_status_change_keeps_entry_when_only_forecast_changes() -> None:
    """Forecast만 바뀐 뒤 touch하면 진입 기록이 그대로다.

    테스트 코드: RK-034
    """
    # given: Forecast만 best로 고친 Deal이다
    deal = make_deal(NOW, status_key="prospecting", forecast_key="pipeline")
    _revise_sync(make_sync("prospecting", "best"), deal)

    # when: touch(now)를 부른다
    deal.touch(later(300))

    # then: 진입 기록은 등록일 그대로이고 수정 시각만 움직인다
    assert deal.status_entry == StatusEntry(status_key="prospecting", changed_on=TODAY)
    assert deal.updated_at == later(300)


def test_touch_without_status_change_keeps_entry_when_other_fields_change() -> None:
    """다른 필드만 바뀐 뒤 touch하면 진입 기록이 그대로다.

    테스트 코드: RK-034
    """
    # given: 이름과 금액만 고친 Deal이다
    deal = make_deal(NOW)
    deal.revise(
        details=make_deal_details(name="다른 이름", revenue_amount=1),
        sync=deal.sync,
        customer_id=deal.customer_id,
        bant=deal.bant,
    )

    # when: touch(now)를 부른다
    deal.touch(later(60))

    # then: 진입일이 등록일 그대로다
    assert deal.status_changed_on == TODAY


def test_touch_alone_keeps_entry() -> None:
    """고친 것 없이 touch만 하면 진입 기록이 그대로다."""
    deal = make_deal(NOW)

    # when: touch(now)를 부른다
    deal.touch(later(60))

    # then: 진입 기록이 그대로다
    assert deal.status_entry == StatusEntry(status_key="prospecting", changed_on=TODAY)


def test_touch_after_resending_the_same_status_keeps_entry() -> None:
    """같은 Status를 다시 넣은 뒤 touch하면 진입 기록이 그대로다.

    테스트 코드: RK-034
    """
    # given: 같은 Status prospecting을 다시 넣은 Deal이다
    deal = make_deal(NOW, status_key="prospecting")
    _revise_sync(make_sync("prospecting", "pipeline"), deal)

    # when: touch(now)를 부른다
    deal.touch(later(60))

    # then: 진입일이 등록일 그대로다
    assert deal.status_changed_on == TODAY


def test_a_second_status_change_moves_the_entry_again() -> None:
    """Status를 다시 바꾸면 진입 기록이 다시 움직인다.

    테스트 코드: RK-033
    """
    # given: Status를 한 번 바꾸고 touch한 Deal이다
    deal = make_deal(NOW, status_key="prospecting")
    _revise_sync(make_sync("introduction", "pipeline"), deal)
    deal.touch(later(60))

    _revise_sync(make_sync("prospecting", "pipeline"), deal)
    # when: Status를 prospecting으로 되돌리고 touch한다
    deal.touch(later(120))

    # then: 진입 기록이 prospecting과 Status다
    assert deal.status_entry == StatusEntry(status_key="prospecting", changed_on=TODAY)


def test_apply_sync_closing_moves_status_entry() -> None:
    """종결 값을 동기화로 적용하면 진입 기록이 계약완료로 옮겨진다.

    테스트 코드: RK-037
    """
    # given: prospecting·pipeline Deal과 Won 종결 동기화 결과다
    deal = make_deal(NOW, status_key="prospecting", forecast_key="pipeline")
    applied = SyncApplied(
        state=WON,
        revenue=(RevenueAmount(900_000_000), date(2026, 10, 20)),
        co_changed=(),
        notice=None,
    )

    # when: 동기화를 적용하고 touch한다
    deal.apply_sync(applied)
    # then: 진입 기록이 contract_completed와 그 시각이다
    deal.touch(later(90))

    assert deal.status_entry == StatusEntry(status_key="contract_completed", changed_on=TODAY)


def test_apply_sync_forecast_only_change_keeps_status_entry() -> None:
    """Forecast만 바뀌는 동기화 결과는 진입 기록을 바꾸지 않는다.

    테스트 코드: RK-036
    """
    # given: prospecting·pipeline Deal이다
    deal = make_deal(NOW, status_key="prospecting", forecast_key="pipeline")

    # when: Forecast만 best로 바꾸는 동기화를 적용하고 touch한다
    deal.apply_sync(
        SyncApplied(
            state=make_sync("prospecting", "best"), revenue=None, co_changed=(), notice=None
        )
    )
    # then: 진입일이 등록일 그대로다
    deal.touch(later(90))

    assert deal.status_changed_on == TODAY


def test_apply_sync_reopening_a_closed_deal_moves_status_entry() -> None:
    """Won Deal을 다시 열면 진입 기록이 고른 Status로 옮겨진다.

    테스트 코드: RK-037
    """
    # given: 계약완료·Won Deal이다
    deal = make_deal(NOW, status_key="contract_completed", forecast_key="won")
    reopened = make_sync("price_negotiation", "commit")

    # when: 다른 Status로 다시 여는 동기화를 적용하고 touch한다
    deal.apply_sync(SyncApplied(state=reopened, revenue=None, co_changed=(), notice=None))
    # then: 진입 기록이 price_negotiation과 그 시각이다
    deal.touch(later(30))

    assert deal.status_entry == StatusEntry(status_key="price_negotiation", changed_on=TODAY)
