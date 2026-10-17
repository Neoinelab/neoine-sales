"""Status 진입 시각(P3 AC-08·09): 등록과 Status key가 실제로 바뀌는 모든 경로에서만 움직인다.

저장된 Deal의 `status_changed_at`을 본다. 폼 저장·단일 변경·Action 등록이 같은 규칙을 따라야 한다.
"""

from typing import TYPE_CHECKING

from app.application.contact.update_contact import UpdateContact
from app.application.deal_action.inputs import StatusChangeInput
from app.domain.auth.principal import Role
from app.domain.deal.sync import SyncResolution
from tests.factories import NOW
from tests.factories_contact import make_contact_input
from tests.factories_deal import SALES, make_patch
from tests.support.auth_seed import seed_user
from tests.unit.application.apply_helpers import CLOSING, apply_change

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.deal.dto import DealView
    from tests.unit.application.action_env import ActionEnv
    from tests.unit.application.deal_env import DealEnv


async def _entry_time(env: DealEnv, view: DealView) -> datetime:
    return (await env.uow.deals.get(view.item.deal.id)).status_changed_at


async def _entry_key(env: DealEnv, view: DealView) -> str:
    return (await env.uow.deals.get(view.item.deal.id)).status_entry.status_key


# ---- 등록 ----


async def test_register_deal_records_the_entry_at_registration_time(env: DealEnv) -> None:
    view = await env.new_deal(status_key="introduction", forecast_key="best")

    assert await _entry_time(env, view) == env.clock.now()
    assert await _entry_key(env, view) == "introduction"
    assert await _entry_time(env, view) > NOW


# ---- UpdateDeal (폼 저장) ----


async def test_update_deal_status_change_moves_status_changed_at(env: DealEnv) -> None:
    view = await env.new_deal(status_key="prospecting")
    env.clock.advance(3600)

    await env.update.execute(view.item.deal.id.value, make_patch(status_key="introduction"), SALES)

    assert await _entry_time(env, view) == env.clock.now()
    assert await _entry_key(env, view) == "introduction"


async def test_update_deal_forecast_only_keeps_it(env: DealEnv) -> None:
    view = await env.new_deal()
    registered_at = await _entry_time(env, view)
    env.clock.advance(3600)

    await env.update.execute(view.item.deal.id.value, make_patch(forecast_key="best"), SALES)

    assert await _entry_time(env, view) == registered_at


async def test_update_deal_other_fields_keep_it(env: DealEnv) -> None:
    view = await env.new_deal()
    registered_at = await _entry_time(env, view)
    env.clock.advance(3600)

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(name="다른 이름", revenue_amount=1), SALES
    )

    assert updated.item.deal.updated_at == env.clock.now()
    assert await _entry_time(env, view) == registered_at


async def test_update_deal_resending_the_same_status_keeps_it(env: DealEnv) -> None:
    view = await env.new_deal(status_key="prospecting")
    registered_at = await _entry_time(env, view)
    env.clock.advance(3600)

    await env.update.execute(
        view.item.deal.id.value, make_patch(status_key="prospecting", name="새 이름"), SALES
    )

    assert await _entry_time(env, view) == registered_at


async def test_update_deal_with_closing_values_moves_it(env: DealEnv) -> None:
    view = await env.new_deal()
    env.clock.advance(3600)

    await env.update.execute(
        view.item.deal.id.value,
        make_patch(status_key="contract_completed", forecast_key="won"),
        SALES,
    )

    assert await _entry_time(env, view) == env.clock.now()
    assert await _entry_key(env, view) == "contract_completed"


# ---- ApplyDealChange (/changes) ----


async def test_apply_change_status_moves_it(env: DealEnv) -> None:
    view = await env.new_deal(status_key="prospecting")
    env.clock.advance(7200)

    await apply_change(env, view, "status_key", "introduction")

    assert await _entry_time(env, view) == env.clock.now()
    assert await _entry_key(env, view) == "introduction"


async def test_apply_change_forecast_only_keeps_it(env: DealEnv) -> None:
    view = await env.new_deal()
    registered_at = await _entry_time(env, view)
    env.clock.advance(7200)

    await apply_change(env, view, "forecast_key", "best")

    assert await _entry_time(env, view) == registered_at


async def test_apply_change_amount_keeps_it(env: DealEnv) -> None:
    view = await env.new_deal()
    registered_at = await _entry_time(env, view)
    env.clock.advance(7200)

    await apply_change(env, view, "revenue_amount", 42)

    assert await _entry_time(env, view) == registered_at


async def test_apply_change_forecast_won_moves_it_with_contract_completed(env: DealEnv) -> None:
    view = await env.new_deal()
    env.clock.advance(7200)

    await apply_change(env, view, "forecast_key", "won", CLOSING)

    assert await _entry_time(env, view) == env.clock.now()
    assert await _entry_key(env, view) == "contract_completed"


async def test_apply_change_leaving_won_moves_it_to_the_chosen_status(env: DealEnv) -> None:
    view = await env.new_deal(status_key="contract_completed", forecast_key="won")
    env.clock.advance(7200)

    await apply_change(
        env, view, "forecast_key", "commit", SyncResolution(status_key="poc_completed")
    )

    assert await _entry_time(env, view) == env.clock.now()
    assert await _entry_key(env, view) == "poc_completed"


async def test_apply_change_to_the_same_status_keeps_it(env: DealEnv) -> None:
    view = await env.new_deal(status_key="prospecting")
    registered_at = await _entry_time(env, view)
    env.clock.advance(7200)

    await apply_change(env, view, "status_key", "prospecting")

    assert await _entry_time(env, view) == registered_at


# ---- Action 등록의 status_change ----


async def test_register_action_with_status_change_moves_it(action_env: ActionEnv) -> None:
    env = action_env.env

    action = await action_env.act(
        status_change=StatusChangeInput(field="status_key", value="introduction", resolution=None)
    )

    assert await _entry_time(env, action_env.deal) == action.acted_at
    assert await _entry_key(env, action_env.deal) == "introduction"


async def test_register_action_with_forecast_change_keeps_it(action_env: ActionEnv) -> None:
    env = action_env.env
    registered_at = await _entry_time(env, action_env.deal)

    await action_env.act(
        status_change=StatusChangeInput(field="forecast_key", value="best", resolution=None)
    )

    assert await _entry_time(env, action_env.deal) == registered_at


async def test_register_action_with_closing_moves_it(action_env: ActionEnv) -> None:
    env = action_env.env

    action = await action_env.act(
        status_change=StatusChangeInput(
            field="status_key", value="contract_completed", resolution=CLOSING
        )
    )

    assert await _entry_time(env, action_env.deal) == action.acted_at
    assert await _entry_key(env, action_env.deal) == "contract_completed"


async def test_register_action_without_status_change_keeps_it(action_env: ActionEnv) -> None:
    env = action_env.env
    registered_at = await _entry_time(env, action_env.deal)

    await action_env.act()

    assert await _entry_time(env, action_env.deal) == registered_at


# ---- 수정 시각만 바뀌는 경로 ----


async def test_contact_update_touch_keeps_it(env: DealEnv) -> None:
    view = await env.new_deal()
    registered_at = await _entry_time(env, view)
    admin = await seed_user(env.uow_factory, "boss", Role.ADMIN)
    env.clock.advance(3600)

    await UpdateContact(env.uow_factory, env.clock).execute(
        view.customer.id, make_contact_input(None, title="이사"), admin.id
    )

    stored = await env.uow.deals.get(view.item.deal.id)
    assert stored.updated_at == env.clock.now()  # 수정 시각은 움직인다
    assert stored.status_changed_at == registered_at
