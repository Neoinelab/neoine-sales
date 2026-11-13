"""Deal 화면 값의 risk·status_days: 목록·상세·쓰기 응답이 같은 규칙을 쓴다.

"오늘"은 서버 시계(FixedClock)를 OS 로컬 시간대로 바꾼 날짜다. 테스트가 시간대를 Asia/Seoul로
고정한다. FixedClock의 시작(2026-01-01 09:00Z)은 Seoul 18:00, 같은 날이다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.application.alert.update_alert_settings import UpdateAlertSettings
from app.application.deal.inputs import DealChangeInput
from app.application.ports.deal_repository import DealQuery
from app.domain.alert.thresholds import AlertThresholds
from app.domain.auth.principal import Role
from app.domain.deal.risk import Risk
from tests.factories import make_deal_action
from tests.factories_deal import SALES, make_patch
from tests.support.auth_seed import seed_user
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
            now=env.clock.now(),
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
    """목록 행의 경고는 저장된 경고 기준으로 계산한다.

    테스트 코드: RK-022
    """
    # given: Deal이 8일 지났고 기본 기준 14일에서는 정상이다
    view = await env.new_deal()
    code = view.item.deal.id.value
    _days_later(env, 8)
    assert (await _listed(env, code)).risk is None

    # when: 경고 기준을 7일로 저장한 뒤 목록을 조회한다
    await _save_threshold(env, 7)

    # then: 그 행의 risk가 stale이다
    assert (await _listed(env, code)).risk is Risk.STALE


async def test_list_reads_the_threshold_once_for_all_rows(env: DealEnv) -> None:
    """목록은 경고 기준을 요청당 한 번 읽어 모든 행에 쓴다.

    테스트 코드: RK-024
    """
    # given: Deal 3건이 있고 경고 기준 읽기를 센다
    await env.new_deal(name="딜 1")
    await env.new_deal(name="딜 2")
    await env.new_deal(name="딜 3")
    reads: list[None] = []
    original = env.uow.alert_settings.get

    async def counting_get() -> StoredAlertSettings | None:
        reads.append(None)
        return await original()

    env.uow.alert_settings.get = counting_get  # type: ignore[method-assign]

    # when: 목록을 조회한다
    page = await env.list.execute(DealQuery())

    # then: 3행이 나오고 경고 기준 읽기는 1번이다
    assert len(page.items) == 3
    assert len(reads) == 1


async def test_get_deal_uses_default_threshold_without_settings(env: DealEnv) -> None:
    """저장된 경고 기준이 없으면 14일 기준으로 판정한다.

    테스트 코드: RK-022
    """
    # given: 경고 기준을 저장한 적이 없고 Deal이 13일 지났다
    view = await env.new_deal()
    code = view.item.deal.id.value
    _days_later(env, 13)
    assert (await env.get.execute(code)).risk is None

    # when: 하루가 더 지난 뒤 상세를 조회한다
    _days_later(env, 1)

    # then: 13일째는 정상이었고 14일째부터 stale이다
    assert (await env.get.execute(code)).risk is Risk.STALE


async def test_list_and_detail_agree_on_the_same_deal(env: DealEnv) -> None:
    """같은 Deal의 목록 행과 상세는 같은 경고와 체류 일수를 준다.

    테스트 코드: RK-008, RK-017
    """
    # given: Due가 지난 Action이 있는 Deal이 20일 지났다
    view = await env.new_deal()
    code = view.item.deal.id.value
    await _act(env, view, due_date=date(2026, 1, 1))
    _days_later(env, 20)

    # when: 같은 시각에 목록과 상세를 조회한다
    listed = await _listed(env, code)
    detail = await env.get.execute(code)

    # then: 둘 다 overdue_stale이고 체류 일수가 20으로 같다
    assert listed.risk is detail.risk is Risk.OVERDUE_STALE
    assert listed.status_days == detail.status_days == 20


# ---- risk: 기한초과 ----


async def test_action_due_before_today_makes_the_deal_overdue(env: DealEnv) -> None:
    """기준 행의 Due가 오늘보다 앞이면 기한초과다.

    테스트 코드: RK-009
    """
    # given: 서버 시간대 Asia/Seoul에서 어제가 Due인 Action이 있다
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 2))
    _days_later(env, 2)  # 오늘 = 01-03

    # when: 상세를 조회한다
    risk = (await env.get.execute(view.item.deal.id.value)).risk
    # then: risk가 overdue다
    assert risk is Risk.OVERDUE


async def test_action_due_today_is_not_overdue(env: DealEnv) -> None:
    """Due가 오늘이면 기한초과가 아니다.

    테스트 코드: RK-010
    """
    # given: 오늘이 Due인 Action이 있다
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 3))
    _days_later(env, 2)  # 오늘 = 01-03

    # when: 상세를 조회한다
    risk = (await env.get.execute(view.item.deal.id.value)).risk
    # then: risk가 없다
    assert risk is None


async def test_deal_without_actions_is_never_overdue(env: DealEnv) -> None:
    """Action이 없는 Deal은 기한초과가 아니다.

    테스트 코드: RK-011
    """
    # given: Action이 없는 Deal이 5일 지났다
    view = await env.new_deal()
    _days_later(env, 5)

    # when: 상세를 조회한다
    risk = (await env.get.execute(view.item.deal.id.value)).risk
    # then: risk가 없다
    assert risk is None


# ---- risk: 종결 제외 ----


async def _close_as_won(env: DealEnv, view: DealView) -> None:
    await env.apply.execute(
        view.item.deal.id.value,
        DealChangeInput(field="forecast_key", value="won", resolution=CLOSING),
        SALES,
    )


@pytest.mark.parametrize("forecast_key", ["won", "lost"])
async def test_closed_deal_has_no_risk_in_list_and_detail(env: DealEnv, forecast_key: str) -> None:
    """Won·Lost Deal은 기한이 지나고 오래돼도 경고가 없다.

    테스트 코드: RK-018
    """
    # given: Due가 지난 Action을 남기고 Won 또는 Lost로 닫은 Deal이다
    view = await env.new_deal(status_key="price_negotiation", forecast_key="pipeline")
    code = view.item.deal.id.value
    await _act(env, view, due_date=date(2026, 1, 1))
    if forecast_key == "won":
        await _close_as_won(env, view)
    else:
        await env.update.execute(code, make_patch(forecast_key="lost"), SALES)
    # when: 60일이 지난 뒤 목록과 상세를 조회한다
    _days_later(env, 60)

    # then: 목록과 상세 모두 risk가 없다
    assert (await _listed(env, code)).risk is None
    assert (await env.get.execute(code)).risk is None


# ---- 업무 날짜 ----


async def test_today_and_entry_dates_use_the_local_calendar(env: DealEnv) -> None:
    """오늘과 진입 날짜는 서버 시간대의 업무 날짜로 센다.

    테스트 코드: RK-016
    """
    # given: Seoul 01-01 18:00에 등록한 Deal이다
    view = await env.new_deal()  # 등록 Seoul 01-01 18:00
    code = view.item.deal.id.value
    target = datetime(2026, 1, 14, 15, 30, tzinfo=UTC)  # Seoul 01-15 00:30, UTC 날짜로는 01-14
    env.clock.advance(int((target - env.clock.now()).total_seconds()))

    # when: 요청 시각을 UTC 01-14 15:30(Seoul 01-15 00:30)으로 옮기고 상세를 조회한다
    detail = await env.get.execute(code)

    # then: 업무 날짜 차이로 체류 14일이고 stale이다
    assert detail.status_days == 14
    assert detail.risk is Risk.STALE


# ---- status_days ----


async def test_status_days_counts_from_status_changed_on(env: DealEnv) -> None:
    """체류 일수는 진입 업무 날짜부터 센 일수이고 등록 직후는 0이다.

    테스트 코드: RK-040
    """
    # given: 방금 등록한 Deal이다(등록 응답의 체류 일수는 0)
    view = await env.new_deal()
    code = view.item.deal.id.value
    assert view.status_days == 0
    # when: 5일 뒤 목록과 상세를 조회한다
    _days_later(env, 5)

    # then: 둘 다 5일이다
    assert (await _listed(env, code)).status_days == 5
    assert (await env.get.execute(code)).status_days == 5


async def test_status_change_resets_the_days_but_forecast_only_change_does_not(
    env: DealEnv,
) -> None:
    """Status가 바뀌면 체류 일수가 0부터 다시 시작하고 Forecast만 바뀌면 이어진다.

    테스트 코드: RK-041
    """
    # given: 5일 전에 등록한 Deal이고 Forecast만 바꿔도 5일이 이어진다
    view = await env.new_deal()
    code = view.item.deal.id.value
    _days_later(env, 5)
    await env.update.execute(code, make_patch(forecast_key="best"), SALES)
    assert (await env.get.execute(code)).status_days == 5

    # when: Status를 introduction으로 바꾼 뒤 조회한다
    await env.update.execute(code, make_patch(status_key="introduction"), SALES)

    # then: 체류 일수가 0이고 2일 뒤에는 2다
    assert (await env.get.execute(code)).status_days == 0
    _days_later(env, 2)
    assert (await env.get.execute(code)).status_days == 2


async def test_closed_deal_still_shows_status_days(env: DealEnv) -> None:
    """종결 Deal도 체류 일수를 보인다.

    테스트 코드: RK-042
    """
    # given: Won으로 닫은 Deal이다
    view = await env.new_deal()
    await _close_as_won(env, view)
    # when: 9일 뒤 상세를 조회한다
    _days_later(env, 9)

    # then: 체류 일수가 9다
    assert (await env.get.execute(view.item.deal.id.value)).status_days == 9


# ---- 쓰기 응답도 같은 규칙 ----


async def test_register_response_has_zero_days_and_no_risk(env: DealEnv) -> None:
    """등록 응답은 체류 0일이고 경고가 없다.

    테스트 코드: RK-025
    """
    # when: Deal을 등록한다
    view = await env.new_deal()

    # then: risk는 없고 status_days는 0이다
    assert (view.risk, view.status_days) == (None, 0)


async def test_update_response_is_computed_at_the_request_time(env: DealEnv) -> None:
    """수정 응답은 요청 시각 기준의 경고와 체류 일수를 준다.

    테스트 코드: RK-025
    """
    # given: Due가 어제 지난 Action을 남기고 3일이 지난 Deal이다
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 2))
    _days_later(env, 3)

    # when: Status를 바꿔 수정한다
    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(status_key="introduction"), SALES
    )

    # then: risk는 overdue이고 Status가 바뀌어 status_days는 0이다
    assert updated.risk is Risk.OVERDUE
    assert updated.status_days == 0


async def test_apply_change_response_carries_risk_and_days(env: DealEnv) -> None:
    """변경 적용 응답에도 경고와 체류 일수가 실린다.

    테스트 코드: RK-025
    """
    # given: Due가 어제 지난 Action을 남기고 3일이 지난 Deal이다
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 2))
    _days_later(env, 3)

    # when: Forecast를 Won(계약완료)으로 변경 적용한다
    result = await env.apply.execute(
        view.item.deal.id.value,
        DealChangeInput(field="forecast_key", value="won", resolution=CLOSING),
        SALES,
    )

    # then: 종결이라 risk가 없고 계약완료로 바뀌어 status_days는 0이다
    assert result.view.risk is None  # 종결(Won)이 된다
    assert result.view.status_days == 0  # 계약완료로 함께 바뀐다


async def test_update_response_without_a_status_change_keeps_counting_the_days(
    env: DealEnv,
) -> None:
    """Status를 바꾸지 않는 수정 응답도 요청 시각 기준의 경고와 체류 일수를 준다.

    테스트 코드: RK-025
    """
    # given: Due가 어제 지난 Action을 남기고 3일이 지난 Deal이다
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 2))
    _days_later(env, 3)

    # when: 이름만 수정한다
    updated = await env.update.execute(view.item.deal.id.value, make_patch(name="새 이름"), SALES)

    # then: 응답의 risk는 overdue이고 status_days는 3이다
    assert updated.risk is Risk.OVERDUE
    assert updated.status_days == 3


async def test_editing_the_deal_does_not_clear_stale(env: DealEnv) -> None:
    """Deal을 수정해도 미업데이트가 풀리지 않고 최종 업데이트일은 등록일 그대로다.

    테스트 코드: RK-021
    """
    # given: Action 없이 15일이 지난 Deal이다
    view = await env.new_deal()
    code = view.item.deal.id.value
    created = view.item.deal.created_at.astimezone().date()
    _days_later(env, 15)

    # when: 금액을 수정한 뒤 상세를 조회한다
    await env.update.execute(code, make_patch(revenue_amount=1), SALES)
    detail = await env.get.execute(code)

    # then: risk는 stale이고 last_updated_on은 등록일이다
    assert detail.risk is Risk.STALE
    assert detail.item.last_updated_on == created


async def test_changing_the_saved_threshold_applies_to_the_same_deals_at_once(
    env: DealEnv,
) -> None:
    """경고 기준을 바꾸면 같은 Deal이 다음 조회부터 새 기준으로 다시 판정된다.

    테스트 코드: RK-023
    """
    # given: 15일 지난 Deal과 8일 지난 Deal이 있고 기준은 저장 전 14일이다
    old = await env.new_deal(name="오래된 딜")
    _days_later(env, 7)
    recent = await env.new_deal(name="최근 딜")
    _days_later(env, 8)
    old_code, recent_code = old.item.deal.id.value, recent.item.deal.id.value
    admin = (await seed_user(env.uow_factory, "root", Role.ADMIN)).to_principal()
    update_settings = UpdateAlertSettings(env.uow_factory, env.clock)
    assert (await _listed(env, old_code)).risk is Risk.STALE
    assert (await _listed(env, recent_code)).risk is None

    # when: admin이 기준을 7일로 저장한 뒤 조회한다
    await update_settings.execute(actor=admin, stale_days=7)

    # then: 8일 된 Deal도 stale이 된다
    assert (await _listed(env, recent_code)).risk is Risk.STALE

    # when: admin이 기준을 30일로 저장한 뒤 조회한다
    await update_settings.execute(actor=admin, stale_days=30)

    # then: 15일 된 Deal은 정상이 된다
    assert (await _listed(env, old_code)).risk is None
