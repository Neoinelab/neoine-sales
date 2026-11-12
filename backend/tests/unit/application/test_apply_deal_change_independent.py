"""ApplyDealChange의 독립 변경·권한·없음: Lost, 같은 값, 없는 코드, 요청자."""

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
        """Won이 아닌 Deal을 Lost로 바꾸면 Status는 그대로이고 함께 바뀐 값·알림이 없다.

        테스트 코드: DD-021
        """
        # given: 기회발굴·Pipeline Deal
        view = await env.new_deal()

        # when: Forecast를 Lost로 바꾼다
        result = await apply_change(env, view, "forecast_key", "lost")

        # then: 기회발굴·Lost, 함께 바뀐 값·알림 없음, Forecast 이력 한 건
        assert (await stored_values(env, view))[:2] == ("prospecting", "lost")
        assert (result.co_changed, result.notice) == ((), None)
        assert await env.changes(view) == [("forecast", "Forecast", "Pipeline", "Lost")]

    async def test_a_plain_status_change_ignores_a_resolution(self, env: DealEnv) -> None:
        """독립 변경은 함께 보낸 매출 답을 무시한다.

        테스트 코드: DD-022
        """
        # given: 기회발굴·Pipeline Deal
        view = await env.new_deal()

        # when: 매출 답을 함께 주고 Status를 제품소개로 바꾼다
        result = await apply_change(env, view, "status_key", "introduction", CLOSING)

        # then: Status만 바뀌고 Forecast·금액·매출일은 그대로이며 알림이 없다
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
        """같은 값으로 바꾸면 이력도 수정 시각 변경도 없다.

        테스트 코드: DD-023
        """
        # given: Pipeline Deal이고 시간이 600초 지났다
        view = await env.new_deal()
        env.clock.advance(600)

        # when: Forecast를 같은 Pipeline으로 바꾼다
        result = await apply_change(env, view, "forecast_key", "pipeline")

        # then: 함께 바뀐 값·알림·이력이 없고 수정 시각이 그대로다
        assert (result.co_changed, result.notice) == ((), None)
        assert await env.changes(view) == []
        assert (await env.uow.deals.get(view.item.deal.id)).updated_at == view.item.deal.updated_at

    async def test_a_real_change_moves_the_update_time_to_now(self, env: DealEnv) -> None:
        """실제로 바꾸면 수정 시각이 서버 시각이 된다.

        테스트 코드: DD-024
        """
        # given: Pipeline Deal이고 시간이 600초 지났다
        view = await env.new_deal()
        env.clock.advance(600)

        # when: Forecast를 Best로 바꾼다
        await apply_change(env, view, "forecast_key", "best")

        # then: 저장된 수정 시각이 서버 현재 시각이다
        assert (await env.uow.deals.get(view.item.deal.id)).updated_at == env.clock.now()

    @pytest.mark.parametrize(("field", "value"), [("status_key", "nope"), ("forecast_key", "nope")])
    async def test_an_unknown_code_is_rejected(self, env: DealEnv, field: str, value: str) -> None:
        """없는 Status·Forecast key는 '존재하지 않는 코드입니다.'로 거절되고 값이 그대로다.

        테스트 코드: DD-026
        """
        # given: 기회발굴·Pipeline Deal
        view = await env.new_deal()

        # when: 없는 key로 바꾼다
        with raises_with(InvalidValueError, "존재하지 않는 코드입니다."):
            await apply_change(env, view, field, value)

        # then: 존재하지 않는 코드 오류이고 Status·Forecast가 그대로다
        assert (await stored_values(env, view))[:2] == ("prospecting", "pipeline")


class TestWhoAndWhere:
    async def test_a_deal_of_a_resigned_owner_can_still_be_changed(self, env: DealEnv) -> None:
        """Owner가 퇴사한 Deal도 sales가 바꿀 수 있다.

        테스트 코드: DD-032
        """
        # given: 퇴사한 Owner의 Deal
        park = await seed_user(env.uow_factory, "park", Role.SALES)
        view = await env.new_deal(owner_user_id=park.id)
        async with env.uow_factory() as uow:
            stored = await uow.users.get(park.id)
            stored.resign(env.clock.now())
            await uow.users.update(stored)
            await uow.commit()

        # when: Forecast를 Best로 바꾼다
        await apply_change(env, view, "forecast_key", "best")

        # then: Forecast가 Best로 저장된다
        assert (await stored_values(env, view))[1] == "best"

    async def test_another_sales_user_may_change_the_deal_and_is_the_history_author(
        self, env: DealEnv
    ) -> None:
        """Owner가 아닌 영업도 바꿀 수 있고 이력의 변경자는 요청자다.

        테스트 코드: DD-032
        """
        # given: Owner가 아닌 영업 kim과 Deal
        kim = await seed_user(env.uow_factory, "kim", Role.SALES)
        view = await env.new_deal()

        # when: kim이 Forecast를 Best로 바꾼다
        await env.apply.execute(
            view.item.deal.id.value,
            DealChangeInput(field="forecast_key", value="best", resolution=None),
            Actor(user_id=kim.id, role=Role.SALES),
        )

        # then: Forecast가 바뀌고 가장 최근 이력의 변경자가 kim이다
        assert (await stored_values(env, view))[1] == "best"
        newest = (await env.history.execute(view.item.deal.id.value, None))[0]
        assert newest.by.id == kim.id

    @pytest.mark.parametrize("code", ["20261016-ZZZZ", "not-a-code", ""])
    async def test_an_unknown_or_malformed_code_is_not_found(self, env: DealEnv, code: str) -> None:
        """없는 Deal·형식이 틀린 code의 단일 변경은 찾을 수 없음 오류다.

        테스트 코드: DD-034
        """
        # given: 변경 입력(Forecast Best)
        change = DealChangeInput(field="forecast_key", value="best", resolution=None)

        # when·then: 없는 code, 형식이 틀린 code, 빈 code로 바꾼다 → Deal을 찾을 수 없음 오류다
        with pytest.raises(DealNotFoundError):
            await env.apply.execute(code, change, SALES)

    async def test_the_result_view_has_the_new_values(self, env: DealEnv) -> None:
        """결과 Deal 보기에는 변경 뒤 값이 들어 있다.

        테스트 코드: DD-024
        """
        # given: Pipeline Deal
        view = await env.new_deal()

        # when: Forecast를 Best로 바꾼다
        result = await apply_change(env, view, "forecast_key", "best")

        # then: 결과의 Deal id·Owner는 그대로이고 Forecast가 Best다
        assert result.view.item.deal.id == view.item.deal.id
        assert result.view.item.deal.sync.forecast_key == "best"
        assert result.view.owner.id == view.owner.id
