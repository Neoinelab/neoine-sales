"""UpdateDeal: Owner 재검사, 폼 저장의 Status/Forecast 불변식, 종결 후 수정."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.user.change_user_role import ChangeUserRole
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
        """퇴사한 Owner를 같은 값으로 다시 보내면 퇴사 문구로 거절한다.

        테스트 코드: DE-044
        """
        # given: Owner가 퇴사한 Deal.
        view, park = await _deal_of_a_resigned_owner(env)

        # when·then: owner_user_id를 현재 Owner(퇴사자)로 보내 수정한다
        # → '퇴사한 사용자는 Owner로 지정할 수 없습니다…' 오류다.
        with raises_with(InvalidValueError, OWNER_RESIGNED):
            await env.update.execute(
                view.item.deal.id.value, make_patch(owner_user_id=park.id), SALES
            )

    async def test_an_owner_that_is_not_sent_is_not_checked(self, env: DealEnv) -> None:
        """Owner를 보내지 않으면 퇴사한 Owner의 Deal도 다른 필드를 수정할 수 있다.

        테스트 코드: DE-045
        """
        # given: Owner가 퇴사한 Deal.
        view, _ = await _deal_of_a_resigned_owner(env)

        # when: 이름만 보내 수정한다.
        updated = await env.update.execute(view.item.deal.id.value, make_patch(name="B"), SALES)

        # then: 수정되고 Owner는 퇴사자로 그대로다.
        assert updated.item.deal.details.name == "B"
        assert updated.owner.resigned is True

    async def test_a_resigned_owner_can_be_replaced_by_an_active_sales_user(
        self, env: DealEnv
    ) -> None:
        """퇴사한 Owner를 재직 sales로 바꾸면 저장되고 Owner 이력이 남는다.

        테스트 코드: DE-046
        """
        # given: Owner가 퇴사한 Deal.
        view, _ = await _deal_of_a_resigned_owner(env)

        # when: 재직 sales를 Owner로 보낸다.
        updated = await env.update.execute(
            view.item.deal.id.value, make_patch(owner_user_id=OWNER_ID), SALES
        )

        # then: Owner가 바뀌고 이력이 '이름(퇴사)' -> 새 Owner로 남는다.
        assert updated.owner.id == OWNER_ID
        assert await env.changes(updated) == [("owner", "Owner", "park(퇴사)", "owner")]

    async def test_a_non_sales_user_cannot_become_the_owner(self, env: DealEnv) -> None:
        """admin을 Owner로 바꾸려 하면 거절되고 Owner는 그대로다.

        테스트 코드: DE-047
        """
        # given: admin 사용자와 Deal.
        boss = await seed_user(env.uow_factory, "boss", Role.ADMIN)
        view = await env.new_deal()

        # when: admin을 Owner로 보낸다.
        with raises_with(InvalidValueError, OWNER_NOT_SALES):
            await env.update.execute(
                view.item.deal.id.value, make_patch(owner_user_id=boss.id), SALES
            )

        # then: 'Owner는 재직 중인 영업 담당자여야 합니다.' 오류이고 Owner가 그대로다.
        assert (await env.uow.deals.get(view.item.deal.id)).details.owner_user_id == OWNER_ID


class TestStatusAndForecastOnTheForm:
    async def test_closing_requires_both_values_together(self, env: DealEnv) -> None:
        """계약완료/Won으로 닫을 때 한 쪽만 보내면 동기화 문구로 거절한다(규칙은 DD 소유).

        테스트 코드: DD-009
        """
        # given: 진행 중 Deal.
        view = await env.new_deal()
        code = view.item.deal.id.value

        # when: Status만, Forecast만 따로 보낸다.
        with raises_with(InvalidValueError, SYNC):
            await env.update.execute(code, make_patch(status_key="contract_completed"), SALES)
        with raises_with(InvalidValueError, SYNC):
            await env.update.execute(code, make_patch(forecast_key="won"), SALES)

        # then: 둘 다 동기화 오류이고 값이 그대로다.
        stored = await env.uow.deals.get(view.item.deal.id)
        assert (stored.sync.status_key, stored.sync.forecast_key) == ("prospecting", "pipeline")

    async def test_closing_with_both_values_is_logged_without_a_co_change_note(
        self, env: DealEnv
    ) -> None:
        """두 값을 함께 보내면 종결되고 각각 이력이 남는다(문구는 DD 소유).

        테스트 코드: DD-010
        """
        # given: 진행 중 Deal.
        view = await env.new_deal()

        # when: 계약완료와 Won을 함께 보낸다.
        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(status_key="contract_completed", forecast_key="won"),
            SALES,
        )

        # then: Status·Forecast 이력이 각각 남는다.
        assert await env.changes(updated) == [
            ("status", "Status", "기회발굴", "계약완료"),
            ("forecast", "Forecast", "Pipeline", "Won"),
        ]

    async def test_a_closed_deal_can_still_be_edited_and_reopened_keeping_amount_and_date(
        self, env: DealEnv
    ) -> None:
        """종결된 Deal도 수정·되돌리기가 되고 금액·Expected Close는 유지된다(DD 소유 규칙).

        테스트 코드: DD-011
        """
        # given: 금액 777인 종결 Deal.
        view = await env.new_deal(
            status_key="contract_completed",
            forecast_key="won",
            revenue_amount=777,
            revenue_date=date(2026, 9, 1),
        )
        code = view.item.deal.id.value

        # when: 이름을 고치고 다시 협상 단계로 되돌린다.
        edited = await env.update.execute(code, make_patch(name="종결 후 수정"), SALES)
        reopened = await env.update.execute(
            code, make_patch(status_key="price_negotiation", forecast_key="commit"), SALES
        )

        # then: 수정되고 금액·날짜가 그대로다.
        assert edited.item.deal.details.name == "종결 후 수정"
        details = reopened.item.deal.details
        assert (details.revenue_amount.value, details.revenue_date) == (777, date(2026, 9, 1))
        assert reopened.item.deal.sync.status_key == "price_negotiation"

    async def test_reopening_requires_both_values_together(self, env: DealEnv) -> None:
        """종결 Deal을 되돌릴 때 한 쪽만 보내면 동기화 문구로 거절한다(DD 소유 규칙).

        테스트 코드: DD-009
        """
        # given: 종결된 Deal.
        view = await env.new_deal(status_key="contract_completed", forecast_key="won")

        # when·then: Status만 보낸다 → 동기화 오류다.
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
        """수정에서 없는 Status·Forecast 코드를 보내면 거절한다.

        테스트 코드: DE-055
        """
        # given: Deal이 있다.
        view = await env.new_deal()

        # when·then: 없는 Status 또는 Forecast 코드를 보낸다
        # → 'Status를 선택하세요.'/'Forecast를 선택하세요.' 오류다.
        with raises_with(InvalidValueError, message):
            await env.update.execute(view.item.deal.id.value, make_patch(**patch), SALES)


class TestOwnerRoleRules:
    @pytest.mark.parametrize("role", [Role.ADMIN, Role.USER])
    async def test_a_non_sales_user_cannot_become_the_owner_and_the_owner_stays(
        self, env: DealEnv, role: Role
    ) -> None:
        """admin·user를 Owner로 바꾸려 하면 422이고 Owner는 그대로다.

        테스트 코드: DE-047
        """
        # given: Owner가 KIM인 Deal과 admin 또는 user 사용자
        other = await seed_user(env.uow_factory, "other", role)
        view = await env.new_deal()

        # when: 그 사용자를 Owner로 보낸다
        with raises_with(InvalidValueError, OWNER_NOT_SALES):
            await env.update.execute(
                view.item.deal.id.value, make_patch(owner_user_id=other.id), SALES
            )

        # then: 오류이고 Owner와 이력이 그대로다
        assert (await env.uow.deals.get(view.item.deal.id)).details.owner_user_id == OWNER_ID
        assert await env.changes(view) == []

    async def test_an_owner_whose_role_changed_keeps_the_deal_and_other_edits_work(
        self, env: DealEnv
    ) -> None:
        """역할이 sales에서 바뀐 Owner의 Deal은 Owner가 그대로이고 Owner 없는 수정은 된다.

        테스트 코드: DE-048
        """
        # given: park가 Owner인 Deal, 그 뒤 admin이 park의 역할을 user로 바꿨다
        boss = await seed_user(env.uow_factory, "boss", Role.ADMIN)
        park = await seed_user(env.uow_factory, "park", Role.SALES)
        view = await env.new_deal(owner_user_id=park.id)
        await ChangeUserRole(env.uow_factory, env.clock).execute(
            user_id=park.id, role=Role.USER, actor=boss.to_principal()
        )

        # when: Owner를 보내지 않고 Deal 이름을 고친다
        updated = await env.update.execute(view.item.deal.id.value, make_patch(name="B"), SALES)

        # then: 수정되고 Owner는 park 그대로다
        assert updated.item.deal.details.name == "B"
        assert updated.item.deal.details.owner_user_id == park.id
        assert updated.owner.role is Role.USER
