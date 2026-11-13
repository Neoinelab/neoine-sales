"""Status 진입일: 등록과 Status key가 실제로 바뀌는 모든 경로에서만 움직인다.

저장된 Deal의 `status_changed_on`(요청의 업무 날짜)을 본다. 폼 저장·단일 변경·Action 등록이
같은 규칙을 따라야 한다.
"""

from typing import TYPE_CHECKING

from app.application.contact.update_contact import UpdateContact
from app.application.deal_action.inputs import StatusChangeInput
from app.domain.auth.principal import Role
from app.domain.deal.sync import SyncResolution
from tests.factories_contact import make_contact_input
from tests.factories_deal import SALES, make_patch
from tests.support.auth_seed import seed_user
from tests.unit.application.apply_helpers import CLOSING, apply_change

if TYPE_CHECKING:
    from datetime import date

    from app.application.deal.dto import DealView
    from tests.unit.application.action_env import ActionEnv
    from tests.unit.application.deal_env import DealEnv


async def _entry_date(env: DealEnv, view: DealView) -> date:
    return (await env.uow.deals.get(view.item.deal.id)).status_changed_on


def _today(env: DealEnv) -> date:
    """서버 시계의 업무 날짜."""
    return env.clock.now().astimezone().date()


async def _entry_key(env: DealEnv, view: DealView) -> str:
    return (await env.uow.deals.get(view.item.deal.id)).status_entry.status_key


# ---- 등록 ----


async def test_register_deal_records_the_entry_on_the_registration_date(env: DealEnv) -> None:
    """등록하면 Status 진입일이 등록일이다.

    테스트 코드: RK-032
    """
    # when: Deal을 등록한다
    view = await env.new_deal(status_key="introduction", forecast_key="best")

    # then: 진입일이 서버 시계의 업무 날짜이고 진입 Status가 등록 Status다
    assert await _entry_date(env, view) == _today(env)
    assert await _entry_key(env, view) == "introduction"


# ---- UpdateDeal (폼 저장) ----


async def test_update_deal_status_change_moves_status_changed_on(env: DealEnv) -> None:
    """폼 수정으로 Status가 바뀌면 진입일이 그 요청의 업무 날짜가 된다.

    테스트 코드: RK-033
    """
    # given: Status prospecting으로 등록하고 하루가 지났다
    view = await env.new_deal(status_key="prospecting")
    env.clock.advance(86400)

    # when: Status를 introduction으로 수정한다
    await env.update.execute(view.item.deal.id.value, make_patch(status_key="introduction"), SALES)

    # then: 진입일이 요청의 업무 날짜이고 진입 Status가 introduction이다
    assert await _entry_date(env, view) == _today(env)
    assert await _entry_key(env, view) == "introduction"


async def test_update_deal_forecast_only_keeps_it(env: DealEnv) -> None:
    """폼 수정에서 Forecast만 바꾸면 진입일이 그대로다.

    테스트 코드: RK-034
    """
    # given: Deal을 등록하고 하루가 지났다
    view = await env.new_deal()
    registered_at = await _entry_date(env, view)
    env.clock.advance(86400)

    # when: Forecast만 best로 수정한다
    await env.update.execute(view.item.deal.id.value, make_patch(forecast_key="best"), SALES)

    # then: 진입일이 등록일 그대로다
    assert await _entry_date(env, view) == registered_at


async def test_update_deal_other_fields_keep_it(env: DealEnv) -> None:
    """폼 수정에서 다른 필드만 바꾸면 진입일이 그대로다.

    테스트 코드: RK-034
    """
    # given: Deal을 등록하고 하루가 지났다
    view = await env.new_deal()
    registered_at = await _entry_date(env, view)
    env.clock.advance(86400)

    # when: 이름과 금액만 수정한다
    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(name="다른 이름", revenue_amount=1), SALES
    )

    # then: 수정 시각은 움직이지만 진입일은 등록일 그대로다
    assert updated.item.deal.updated_at == env.clock.now()
    assert await _entry_date(env, view) == registered_at


async def test_update_deal_resending_the_same_status_keeps_it(env: DealEnv) -> None:
    """폼 수정에서 같은 Status를 다시 보내면 진입일이 그대로다.

    테스트 코드: RK-034
    """
    # given: Status prospecting으로 등록하고 하루가 지났다
    view = await env.new_deal(status_key="prospecting")
    registered_at = await _entry_date(env, view)
    env.clock.advance(86400)

    # when: 같은 Status와 새 이름을 보내 수정한다
    await env.update.execute(
        view.item.deal.id.value, make_patch(status_key="prospecting", name="새 이름"), SALES
    )

    # then: 진입일이 등록일 그대로다
    assert await _entry_date(env, view) == registered_at


async def test_update_deal_with_closing_values_moves_it(env: DealEnv) -> None:
    """폼 수정에서 종결 값으로 Status가 바뀌면 진입일이 바뀐다.

    테스트 코드: RK-035
    """
    # given: 진행 중인 Deal을 등록하고 하루가 지났다
    view = await env.new_deal()
    env.clock.advance(86400)

    # when: Won·계약완료로 폼 수정한다
    await env.update.execute(
        view.item.deal.id.value,
        make_patch(status_key="contract_completed", forecast_key="won"),
        SALES,
    )

    # then: 진입일이 요청의 업무 날짜이고 진입 Status가 contract_completed다
    assert await _entry_date(env, view) == _today(env)
    assert await _entry_key(env, view) == "contract_completed"


# ---- ApplyDealChange (/changes) ----


async def test_apply_change_status_moves_it(env: DealEnv) -> None:
    """변경 적용으로 Status를 바꾸면 진입일이 바뀐다.

    테스트 코드: RK-036
    """
    # given: Status prospecting으로 등록하고 이틀이 지났다
    view = await env.new_deal(status_key="prospecting")
    env.clock.advance(2 * 86400)

    # when: 변경 적용으로 Status를 introduction으로 바꾼다
    await apply_change(env, view, "status_key", "introduction")

    # then: 진입일이 요청의 업무 날짜이고 진입 Status가 introduction이다
    assert await _entry_date(env, view) == _today(env)
    assert await _entry_key(env, view) == "introduction"


async def test_apply_change_forecast_only_keeps_it(env: DealEnv) -> None:
    """변경 적용에서 Forecast만 바꾸면 진입일이 그대로다.

    테스트 코드: RK-036
    """
    # given: Deal을 등록하고 이틀이 지났다
    view = await env.new_deal()
    registered_at = await _entry_date(env, view)
    env.clock.advance(2 * 86400)

    # when: 변경 적용으로 Forecast만 best로 바꾼다
    await apply_change(env, view, "forecast_key", "best")

    # then: 진입일이 등록일 그대로다
    assert await _entry_date(env, view) == registered_at


async def test_apply_change_amount_keeps_it(env: DealEnv) -> None:
    """변경 적용에서 금액만 바꾸면 진입일이 그대로다.

    테스트 코드: RK-036
    """
    # given: Deal을 등록하고 이틀이 지났다
    view = await env.new_deal()
    registered_at = await _entry_date(env, view)
    env.clock.advance(2 * 86400)

    # when: 변경 적용으로 금액만 바꾼다
    await apply_change(env, view, "revenue_amount", 42)

    # then: 진입일이 등록일 그대로다
    assert await _entry_date(env, view) == registered_at


async def test_apply_change_forecast_won_moves_it_with_contract_completed(env: DealEnv) -> None:
    """Forecast Won 적용으로 계약완료가 함께 바뀌면 진입일이 바뀐다.

    테스트 코드: RK-037
    """
    # given: 진행 중인 Deal을 등록하고 이틀이 지났다
    view = await env.new_deal()
    env.clock.advance(2 * 86400)

    # when: Forecast를 won으로 변경 적용한다
    await apply_change(env, view, "forecast_key", "won", CLOSING)

    # then: 진입일이 요청의 업무 날짜이고 진입 Status가 contract_completed다
    assert await _entry_date(env, view) == _today(env)
    assert await _entry_key(env, view) == "contract_completed"


async def test_apply_change_leaving_won_moves_it_to_the_chosen_status(env: DealEnv) -> None:
    """Won에서 다른 Status로 나가면 진입일이 바뀐다.

    테스트 코드: RK-037
    """
    # given: 계약완료·Won Deal이고 이틀이 지났다
    view = await env.new_deal(status_key="contract_completed", forecast_key="won")
    env.clock.advance(2 * 86400)

    # when: Forecast를 commit으로 바꾸고 Status로 poc_completed를 고른다
    await apply_change(
        env, view, "forecast_key", "commit", SyncResolution(status_key="poc_completed")
    )

    # then: 진입일이 요청의 업무 날짜이고 진입 Status가 poc_completed다
    assert await _entry_date(env, view) == _today(env)
    assert await _entry_key(env, view) == "poc_completed"


async def test_apply_change_to_the_same_status_keeps_it(env: DealEnv) -> None:
    """변경 적용에서 같은 Status를 적용하면 진입일이 그대로다.

    테스트 코드: RK-036
    """
    # given: Status prospecting으로 등록하고 이틀이 지났다
    view = await env.new_deal(status_key="prospecting")
    registered_at = await _entry_date(env, view)
    env.clock.advance(2 * 86400)

    # when: 같은 Status를 변경 적용한다
    await apply_change(env, view, "status_key", "prospecting")

    # then: 진입일이 등록일 그대로다
    assert await _entry_date(env, view) == registered_at


# ---- Action 등록의 status_change ----


async def test_register_action_with_status_change_moves_it(action_env: ActionEnv) -> None:
    """Status를 바꾸는 Action을 등록하면 진입일이 요청의 업무 날짜가 된다.

    테스트 코드: RK-038
    """
    # given: Deal이 있다
    env = action_env.env
    registered_on = await _entry_date(env, action_env.deal)

    # when: 이틀 뒤 status_change로 Status를 introduction으로 바꾸는 Action을 등록한다
    await action_env.act(
        advance=2 * 86400,
        status_changes=(
            StatusChangeInput(field="status_key", value="introduction", resolution=None),
        ),
    )

    # then: 진입일이 요청의 업무 날짜(등록일과 다름)이고 진입 Status가 introduction이다
    assert await _entry_date(env, action_env.deal) == _today(env)
    assert await _entry_date(env, action_env.deal) != registered_on
    assert await _entry_key(env, action_env.deal) == "introduction"


async def test_register_action_with_forecast_change_keeps_it(action_env: ActionEnv) -> None:
    """Forecast만 바꾸는 Action은 진입일을 바꾸지 않는다.

    테스트 코드: RK-038
    """
    # given: Deal이 있다
    env = action_env.env
    registered_at = await _entry_date(env, action_env.deal)

    # when: status_change로 Forecast만 best로 바꾸는 Action을 등록한다
    await action_env.act(
        status_changes=(StatusChangeInput(field="forecast_key", value="best", resolution=None),)
    )

    # then: 진입일이 등록일 그대로다
    assert await _entry_date(env, action_env.deal) == registered_at


async def test_register_action_with_closing_moves_it(action_env: ActionEnv) -> None:
    """종결하는 Action을 등록하면 진입일이 요청의 업무 날짜가 된다.

    테스트 코드: RK-038
    """
    # given: Deal이 있다
    env = action_env.env
    registered_on = await _entry_date(env, action_env.deal)

    # when: 이틀 뒤 status_change로 계약완료(종결)로 바꾸는 Action을 등록한다
    await action_env.act(
        advance=2 * 86400,
        status_changes=(
            StatusChangeInput(field="status_key", value="contract_completed", resolution=CLOSING),
        ),
    )

    # then: 진입일이 요청의 업무 날짜(등록일과 다름)이고 진입 Status가 contract_completed다
    assert await _entry_date(env, action_env.deal) == _today(env)
    assert await _entry_date(env, action_env.deal) != registered_on
    assert await _entry_key(env, action_env.deal) == "contract_completed"


async def test_register_action_without_status_change_keeps_it(action_env: ActionEnv) -> None:
    """status_change가 없는 Action은 진입일을 바꾸지 않는다.

    테스트 코드: RK-038
    """
    # given: Deal이 있다
    env = action_env.env
    registered_at = await _entry_date(env, action_env.deal)

    # when: status_change 없이 Action을 등록한다
    await action_env.act()

    # then: 진입일이 등록일 그대로다
    assert await _entry_date(env, action_env.deal) == registered_at


# ---- 수정 시각만 바뀌는 경로 ----


async def test_contact_update_touch_keeps_it(env: DealEnv) -> None:
    """연락처 변경 반영으로 수정 시각이 바뀌어도 진입일은 그대로다.

    테스트 코드: RK-039
    """
    # given: 고객 연락처가 연결된 Deal이고 하루가 지났다
    view = await env.new_deal()
    registered_at = await _entry_date(env, view)
    admin = await seed_user(env.uow_factory, "boss", Role.ADMIN)
    env.clock.advance(86400)

    # when: 연락처를 수정한다
    await UpdateContact(env.uow_factory, env.clock).execute(
        view.customer.id, make_contact_input(None, title="이사"), admin.id
    )

    # then: Deal 수정 시각은 움직이고 진입일은 그대로다
    stored = await env.uow.deals.get(view.item.deal.id)
    assert stored.updated_at == env.clock.now()  # 수정 시각은 움직인다
    assert stored.status_changed_on == registered_at
