"""Deal 화면 값의 risk·status_days(P3 AC-01~04·06·10): 목록·상세·쓰기 응답이 같은 규칙을 쓴다.

"오늘"은 서버 시계(FixedClock)를 OS 로컬 시간대로 바꾼 날짜다. 테스트가 시간대를 Asia/Seoul로
고정한다. FixedClock의 시작(2026-01-01 09:00Z)은 Seoul 18:00, 같은 날이다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import DealChangeInput
from app.application.ports.deal_repository import DealQuery
from app.domain.alert.thresholds import AlertThresholds
from app.domain.deal.risk import Risk
from tests.factories import make_deal_action
from tests.factories_deal import SALES, make_patch
from tests.support.user_ids import ACTOR_ID, OWNER_ID
from tests.unit.application.apply_helpers import CLOSING

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealView
    from app.domain.alert.settings import StoredAlertSettings
    from tests.unit.application.deal_env import DealEnv

DAY = 24 * 3600


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def _days_later(env: DealEnv, days: int) -> None:
    env.clock.advance(days * DAY)


async def _save_threshold(env: DealEnv, days: int) -> None:
    async with env.uow_factory() as uow:
        await uow.alert_settings.save(
            AlertThresholds(stale_days=days), updated_by=OWNER_ID, now=env.clock.now()
        )
        await uow.commit()


async def _act(env: DealEnv, view: DealView, *, due_date: date) -> None:
    """지금 시각에 수행한 Action을 저장소에 직접 둔다(Due Date만 본다)."""
    await env.uow.deal_actions.add(
        make_deal_action(
            deal_code=view.item.deal.id,
            acted_at=env.clock.now(),
            actor_user_id=ACTOR_ID,
            due_date=due_date,
        )
    )


async def _listed(env: DealEnv, code: str) -> DealView:
    page = await env.list.execute(DealQuery(keyword=code))
    (row,) = page.items
    return row


# ---- risk: 경고 기준 ----


async def test_list_rows_carry_risk_from_saved_threshold(env: DealEnv) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    _days_later(env, 8)
    assert (await _listed(env, code)).risk is None

    await _save_threshold(env, 7)

    assert (await _listed(env, code)).risk is Risk.STALE


async def test_list_reads_the_threshold_once_for_all_rows(env: DealEnv) -> None:
    await env.new_deal(name="딜 1")
    await env.new_deal(name="딜 2")
    await env.new_deal(name="딜 3")
    reads: list[None] = []
    original = env.uow.alert_settings.get

    async def counting_get() -> StoredAlertSettings | None:
        reads.append(None)
        return await original()

    env.uow.alert_settings.get = counting_get  # type: ignore[method-assign]

    page = await env.list.execute(DealQuery())

    assert len(page.items) == 3
    assert len(reads) == 1


async def test_get_deal_uses_default_threshold_without_settings(env: DealEnv) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    _days_later(env, 13)
    assert (await env.get.execute(code)).risk is None

    _days_later(env, 1)

    assert (await env.get.execute(code)).risk is Risk.STALE


async def test_list_and_detail_agree_on_the_same_deal(env: DealEnv) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    await _act(env, view, due_date=date(2026, 1, 1))
    _days_later(env, 20)

    listed = await _listed(env, code)
    detail = await env.get.execute(code)

    assert listed.risk is detail.risk is Risk.OVERDUE_STALE
    assert listed.status_days == detail.status_days == 20


# ---- risk: 기한초과 ----


async def test_action_due_before_today_makes_the_deal_overdue(env: DealEnv) -> None:
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 2))
    _days_later(env, 2)  # 오늘 = 01-03

    assert (await env.get.execute(view.item.deal.id.value)).risk is Risk.OVERDUE


async def test_action_due_today_is_not_overdue(env: DealEnv) -> None:
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 3))
    _days_later(env, 2)  # 오늘 = 01-03

    assert (await env.get.execute(view.item.deal.id.value)).risk is None


async def test_deal_without_actions_is_never_overdue(env: DealEnv) -> None:
    view = await env.new_deal()
    _days_later(env, 5)

    assert (await env.get.execute(view.item.deal.id.value)).risk is None


# ---- risk: 종결 제외 ----


async def _close_as_won(env: DealEnv, view: DealView) -> None:
    await env.apply.execute(
        view.item.deal.id.value,
        DealChangeInput(field="forecast_key", value="won", resolution=CLOSING),
        SALES,
    )


@pytest.mark.parametrize("forecast_key", ["won", "lost"])
async def test_closed_deal_has_no_risk_in_list_and_detail(env: DealEnv, forecast_key: str) -> None:
    view = await env.new_deal(status_key="price_negotiation", forecast_key="pipeline")
    code = view.item.deal.id.value
    await _act(env, view, due_date=date(2026, 1, 1))
    if forecast_key == "won":
        await _close_as_won(env, view)
    else:
        await env.update.execute(code, make_patch(forecast_key="lost"), SALES)
    _days_later(env, 60)

    assert (await _listed(env, code)).risk is None
    assert (await env.get.execute(code)).risk is None


# ---- 업무 날짜 ----


async def test_today_and_entry_dates_use_the_local_calendar(env: DealEnv) -> None:
    view = await env.new_deal()  # 등록 Seoul 01-01 18:00
    code = view.item.deal.id.value
    target = datetime(2026, 1, 14, 15, 30, tzinfo=UTC)  # Seoul 01-15 00:30, UTC 날짜로는 01-14
    env.clock.advance(int((target - env.clock.now()).total_seconds()))

    detail = await env.get.execute(code)

    assert detail.status_days == 14
    assert detail.risk is Risk.STALE


# ---- status_days ----


async def test_status_days_counts_from_status_changed_at(env: DealEnv) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    assert view.status_days == 0
    _days_later(env, 5)

    assert (await _listed(env, code)).status_days == 5
    assert (await env.get.execute(code)).status_days == 5


async def test_status_change_resets_the_days_but_forecast_only_change_does_not(
    env: DealEnv,
) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    _days_later(env, 5)
    await env.update.execute(code, make_patch(forecast_key="best"), SALES)
    assert (await env.get.execute(code)).status_days == 5

    await env.update.execute(code, make_patch(status_key="introduction"), SALES)

    assert (await env.get.execute(code)).status_days == 0
    _days_later(env, 2)
    assert (await env.get.execute(code)).status_days == 2


async def test_closed_deal_still_shows_status_days(env: DealEnv) -> None:
    view = await env.new_deal()
    await _close_as_won(env, view)
    _days_later(env, 9)

    assert (await env.get.execute(view.item.deal.id.value)).status_days == 9


# ---- 쓰기 응답도 같은 규칙 ----


async def test_register_response_has_zero_days_and_no_risk(env: DealEnv) -> None:
    view = await env.new_deal()

    assert (view.risk, view.status_days) == (None, 0)


async def test_update_response_is_computed_at_the_request_time(env: DealEnv) -> None:
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 2))
    _days_later(env, 3)

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(status_key="introduction"), SALES
    )

    assert updated.risk is Risk.OVERDUE
    assert updated.status_days == 0


async def test_apply_change_response_carries_risk_and_days(env: DealEnv) -> None:
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 2))
    _days_later(env, 3)

    result = await env.apply.execute(
        view.item.deal.id.value,
        DealChangeInput(field="forecast_key", value="won", resolution=CLOSING),
        SALES,
    )

    assert result.view.risk is None  # 종결(Won)이 된다
    assert result.view.status_days == 0  # 계약완료로 함께 바뀐다
