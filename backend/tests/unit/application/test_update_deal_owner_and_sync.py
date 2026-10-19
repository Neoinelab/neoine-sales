"""UpdateDeal(AC-17·18·21): Owner 재검사, 폼 저장의 Status/Forecast 불변식, 종결 후 수정."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from tests.factories_deal import SALES, make_patch
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from app.application.deal.dto import DealView
    from app.domain.user.entities import User
    from tests.unit.application.deal_env import DealEnv

OWNER_RESIGNED = "퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요."
OWNER_NOT_SALES = "Owner는 재직 중인 영업 담당자여야 합니다."
SYNC = "Status와 Forecast의 동기화가 맞지 않습니다."


async def _deal_of_a_resigned_owner(env: DealEnv) -> tuple[DealView, User]:
    park = await seed_user(env.uow_factory, "park", Role.SALES)
    view = await env.new_deal(owner_user_id=park.id)
    async with env.uow_factory() as uow:
        stored = await uow.users.get(park.id)
        stored.resign(env.clock.now())
        await uow.users.update(stored)
        await uow.commit()
    return view, park


class TestOwnerCheck:
    async def test_a_resigned_owner_that_is_sent_again_is_rejected(self, env: DealEnv) -> None:
        view, park = await _deal_of_a_resigned_owner(env)

        with raises_with(InvalidValueError, OWNER_RESIGNED):
            await env.update.execute(
                view.item.deal.id.value, make_patch(owner_user_id=park.id), SALES
            )

    async def test_an_owner_that_is_not_sent_is_not_checked(self, env: DealEnv) -> None:
        view, _ = await _deal_of_a_resigned_owner(env)

        updated = await env.update.execute(view.item.deal.id.value, make_patch(name="B"), SALES)

        assert updated.item.deal.details.name == "B"
        assert updated.owner.resigned is True

    async def test_a_resigned_owner_can_be_replaced_by_an_active_sales_user(
        self, env: DealEnv
    ) -> None:
        view, _ = await _deal_of_a_resigned_owner(env)

        updated = await env.update.execute(
            view.item.deal.id.value, make_patch(owner_user_id=OWNER_ID), SALES
        )

        assert updated.owner.id == OWNER_ID
        assert await env.changes(updated) == [("owner", "Owner", "park(퇴사)", "owner")]

    async def test_a_non_sales_user_cannot_become_the_owner(self, env: DealEnv) -> None:
        boss = await seed_user(env.uow_factory, "boss", Role.ADMIN)
        view = await env.new_deal()

        with raises_with(InvalidValueError, OWNER_NOT_SALES):
            await env.update.execute(
                view.item.deal.id.value, make_patch(owner_user_id=boss.id), SALES
            )

        assert (await env.uow.deals.get(view.item.deal.id)).details.owner_user_id == OWNER_ID


class TestStatusAndForecastOnTheForm:
    async def test_closing_requires_both_values_together(self, env: DealEnv) -> None:
        view = await env.new_deal()
        code = view.item.deal.id.value

        with raises_with(InvalidValueError, SYNC):
            await env.update.execute(code, make_patch(status_key="contract_completed"), SALES)
        with raises_with(InvalidValueError, SYNC):
            await env.update.execute(code, make_patch(forecast_key="won"), SALES)

        stored = await env.uow.deals.get(view.item.deal.id)
        assert (stored.sync.status_key, stored.sync.forecast_key) == ("prospecting", "pipeline")

    async def test_closing_with_both_values_is_logged_without_a_co_change_note(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal()

        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(status_key="contract_completed", forecast_key="won"),
            SALES,
        )

        assert await env.changes(updated) == [
            ("status", "Status", "기회발굴", "계약완료"),
            ("forecast", "Forecast", "Pipeline", "Won"),
        ]

    async def test_a_closed_deal_can_still_be_edited_and_reopened_keeping_amount_and_date(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal(
            status_key="contract_completed",
            forecast_key="won",
            revenue_amount=777,
            revenue_date=date(2026, 9, 1),
        )
        code = view.item.deal.id.value

        edited = await env.update.execute(code, make_patch(name="종결 후 수정"), SALES)
        reopened = await env.update.execute(
            code, make_patch(status_key="price_negotiation", forecast_key="commit"), SALES
        )

        assert edited.item.deal.details.name == "종결 후 수정"
        details = reopened.item.deal.details
        assert (details.revenue_amount.value, details.revenue_date) == (777, date(2026, 9, 1))
        assert reopened.item.deal.sync.status_key == "price_negotiation"

    async def test_reopening_requires_both_values_together(self, env: DealEnv) -> None:
        view = await env.new_deal(status_key="contract_completed", forecast_key="won")

        with raises_with(InvalidValueError, SYNC):
            await env.update.execute(
                view.item.deal.id.value, make_patch(status_key="price_negotiation"), SALES
            )

    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            ({"status_key": "unknown_status"}, "Status를 선택하세요."),
            ({"forecast_key": "unknown_forecast"}, "Forecast를 선택하세요."),
        ],
    )
    async def test_an_unknown_code_is_rejected(
        self, env: DealEnv, patch: dict[str, str], message: str
    ) -> None:
        view = await env.new_deal()

        with raises_with(InvalidValueError, message):
            await env.update.execute(view.item.deal.id.value, make_patch(**patch), SALES)
