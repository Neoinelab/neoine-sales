"""ApplyDealChange의 독립 변경·권한·없음(AC-19·21): Lost, 같은 값, 없는 코드, 요청자."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import Actor, DealChangeInput
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from tests.factories_deal import SALES
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with
from tests.unit.application.apply_helpers import CLOSING, apply_change, stored_values

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


class TestIndependentChanges:
    async def test_forecast_to_lost_keeps_the_status(self, env: DealEnv) -> None:
        view = await env.new_deal()

        result = await apply_change(env, view, "forecast_key", "lost")

        assert (await stored_values(env, view))[:2] == ("prospecting", "lost")
        assert (result.co_changed, result.notice) == ((), None)
        assert await env.changes(view) == [("forecast", "Forecast", "Pipeline", "Lost")]

    async def test_a_plain_status_change_ignores_a_resolution(self, env: DealEnv) -> None:
        view = await env.new_deal()

        result = await apply_change(env, view, "status_key", "introduction", CLOSING)

        assert await stored_values(env, view) == (
            "introduction",
            "pipeline",
            150_000_000,
            date(2026, 6, 30),
        )
        assert result.notice is None

    async def test_the_same_value_changes_nothing_and_keeps_the_update_time(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal()
        env.clock.advance(600)

        result = await apply_change(env, view, "forecast_key", "pipeline")

        assert (result.co_changed, result.notice) == ((), None)
        assert await env.changes(view) == []
        assert (await env.uow.deals.get(view.item.deal.id)).updated_at == view.item.deal.updated_at

    async def test_a_real_change_moves_the_update_time_to_now(self, env: DealEnv) -> None:
        view = await env.new_deal()
        env.clock.advance(600)

        await apply_change(env, view, "forecast_key", "best")

        assert (await env.uow.deals.get(view.item.deal.id)).updated_at == env.clock.now()

    @pytest.mark.parametrize(("field", "value"), [("status_key", "nope"), ("forecast_key", "nope")])
    async def test_an_unknown_code_is_rejected(self, env: DealEnv, field: str, value: str) -> None:
        view = await env.new_deal()

        with raises_with(InvalidValueError, "존재하지 않는 코드입니다."):
            await apply_change(env, view, field, value)

        assert (await stored_values(env, view))[:2] == ("prospecting", "pipeline")


class TestWhoAndWhere:
    async def test_a_deal_of_a_resigned_owner_can_still_be_changed(self, env: DealEnv) -> None:
        park = await seed_user(env.uow_factory, "park", Role.SALES)
        view = await env.new_deal(owner_user_id=park.id)
        async with env.uow_factory() as uow:
            stored = await uow.users.get(park.id)
            stored.resign(env.clock.now())
            await uow.users.update(stored)
            await uow.commit()

        await apply_change(env, view, "forecast_key", "best")

        assert (await stored_values(env, view))[1] == "best"

    async def test_another_sales_user_may_change_the_deal_and_is_the_history_author(
        self, env: DealEnv
    ) -> None:
        kim = await seed_user(env.uow_factory, "kim", Role.SALES)
        view = await env.new_deal()

        await env.apply.execute(
            view.item.deal.id.value,
            DealChangeInput(field="forecast_key", value="best", resolution=None),
            Actor(user_id=kim.id, role=Role.SALES),
        )

        assert (await stored_values(env, view))[1] == "best"
        newest = (await env.history.execute(view.item.deal.id.value, None))[0]
        assert newest.by.id == kim.id

    @pytest.mark.parametrize("code", ["20261016-ZZZZ", "not-a-code", ""])
    async def test_an_unknown_or_malformed_code_is_not_found(self, env: DealEnv, code: str) -> None:
        change = DealChangeInput(field="forecast_key", value="best", resolution=None)

        with pytest.raises(DealNotFoundError):
            await env.apply.execute(code, change, SALES)

    async def test_the_result_view_has_the_new_values(self, env: DealEnv) -> None:
        view = await env.new_deal()

        result = await apply_change(env, view, "forecast_key", "best")

        assert result.view.item.deal.id == view.item.deal.id
        assert result.view.item.deal.sync.forecast_key == "best"
        assert result.view.owner.id == view.owner.id
