"""ApplyDealChange의 종결·되돌림: 규칙표, 선택 필수, notice, 이력.

한 번에 값 하나만 바꾸고(요청), 함께 바뀌어야 하는 값은 resolution으로 받아 같은 규칙으로 다시
검증한다. 어떤 값을 물을지 알려 주는 서버 API는 없다(Q4).
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync import CoChange, SyncField, SyncResolution
from tests.support.expect import raises_with
from tests.unit.application.apply_helpers import (
    CHOICE_REQUIRED,
    CLOSING,
    DAY,
    REVENUE_REQUIRED,
    apply_change,
    stored_values,
)

if TYPE_CHECKING:
    from app.application.deal.dto import DealView
    from tests.unit.application.deal_env import DealEnv


class TestClosing:
    async def test_status_to_contract_completed_also_sets_won_and_saves_the_revenue(
        self, env: DealEnv
    ) -> None:
        """Status를 계약완료로 바꾸면 Forecast도 Won이 되고 매출이 저장되며 알림이 나온다.

        테스트 코드: DD-013
        """
        # given: 기회발굴·Pipeline Deal
        view = await env.new_deal()

        # when: 매출 답과 함께 계약완료로 바꾼다
        result = await apply_change(env, view, "status_key", "contract_completed", CLOSING)

        # then: 계약완료·Won·매출 900,000,000·2026-10-20이 저장되고 함께 바뀐 Forecast·알림이 나온다
        assert await stored_values(env, view) == ("contract_completed", "won", 900_000_000, DAY)
        assert result.view.item.deal.sync.forecast_key == "won"
        assert result.co_changed == (CoChange(SyncField.FORECAST, "pipeline", "won"),)
        assert result.notice == "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."

    async def test_forecast_to_won_also_sets_contract_completed_and_saves_the_revenue(
        self, env: DealEnv
    ) -> None:
        """Forecast를 Won으로 바꾸면 Status도 계약완료가 되고 매출이 저장된다.

        테스트 코드: DD-014
        """
        # given: 기회발굴·Pipeline Deal
        view = await env.new_deal()

        # when: 매출 답과 함께 Won으로 바꾼다
        result = await apply_change(env, view, "forecast_key", "won", CLOSING)

        # then: 계약완료·Won·매출이 저장되고 함께 바뀐 값은 Status다
        assert await stored_values(env, view) == ("contract_completed", "won", 900_000_000, DAY)
        assert result.co_changed == (
            CoChange(SyncField.STATUS, "prospecting", "contract_completed"),
        )
        assert result.notice == "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."

    async def test_the_history_marks_the_value_that_changed_together(self, env: DealEnv) -> None:
        """종결 이력 4건(Status·Forecast·금액·Expected Close)에 Forecast의 함께 변경 표기가 붙는다.

        테스트 코드: DD-013
        """
        # given: 기회발굴·Pipeline Deal
        view = await env.new_deal()

        # when: 매출 답과 함께 계약완료로 바꾼다
        await apply_change(env, view, "status_key", "contract_completed", CLOSING)

        # then: 이력이 Status, Forecast(함께 변경 표기), 금액, Expected Close 순서 4건이다
        assert await env.changes(view) == [
            ("status", "Status", "기회발굴", "계약완료"),
            ("forecast", "Forecast", "Pipeline", "Won (Status 계약완료와 함께 변경)"),
            ("amount", "금액(단위:원)", "150,000,000", "900,000,000"),
            ("expectedClose", "Expected Close", "2026-06-30", "2026-10-20"),
        ]

    async def test_the_history_from_the_forecast_side_marks_the_status(self, env: DealEnv) -> None:
        """Won으로 종결하면 이력의 Status에 함께 변경 표기가 붙는다.

        테스트 코드: DD-014
        """
        # given: 기회발굴·Pipeline Deal
        view = await env.new_deal()

        # when: 매출 답과 함께 Won으로 바꾼다
        await apply_change(env, view, "forecast_key", "won", CLOSING)

        # then: 처음 두 건이 Status(함께 변경 표기)와 Forecast다
        assert (await env.changes(view))[:2] == [
            ("status", "Status", "기회발굴", "계약완료 (Forecast Won과 함께 변경)"),
            ("forecast", "Forecast", "Pipeline", "Won"),
        ]

    @pytest.mark.parametrize(
        "resolution",
        [
            None,
            SyncResolution(),
            SyncResolution(revenue_amount=0, revenue_date=DAY),
            SyncResolution(revenue_amount=900_000_000),
            SyncResolution(revenue_date=DAY),
        ],
    )
    @pytest.mark.parametrize(
        ("field", "value"), [("status_key", "contract_completed"), ("forecast_key", "won")]
    )
    async def test_closing_without_a_valid_amount_and_date_is_rejected_and_changes_nothing(
        self, env: DealEnv, field: str, value: str, resolution: SyncResolution | None
    ) -> None:
        """매출 답이 없거나 틀리면 종결은 422 문구로 거절되고 값·이력이 그대로다.

        테스트 코드: DD-012, DD-016
        """
        # given: 기회발굴·Pipeline Deal
        view = await env.new_deal()
        before = await stored_values(env, view)

        # when: 매출 없음·0원·한쪽만 있는 답으로 종결을 요청한다
        with raises_with(InvalidValueError, REVENUE_REQUIRED):
            await apply_change(env, view, field, value, resolution)

        # then: 매출 필요 오류이고 저장 값과 이력이 그대로다
        assert await stored_values(env, view) == before
        assert await env.changes(view) == []

    async def test_lost_to_won_is_a_closing_too(self, env: DealEnv) -> None:
        """Lost에서 Won으로 바꾸는 것도 종결이라 매출을 저장하고 Status가 계약완료가 된다.

        테스트 코드: DD-015
        """
        # given: 가격협상·Lost Deal
        view = await env.new_deal(status_key="price_negotiation", forecast_key="lost")

        # when: 매출 답과 함께 Won으로 바꾼다
        result = await apply_change(env, view, "forecast_key", "won", CLOSING)

        # then: 계약완료·Won·매출이 저장되고 함께 바뀐 Status가 나온다
        assert await stored_values(env, view) == ("contract_completed", "won", 900_000_000, DAY)
        assert result.co_changed == (
            CoChange(SyncField.STATUS, "price_negotiation", "contract_completed"),
        )


class TestReopening:
    async def _won(self, env: DealEnv) -> DealView:
        return await env.new_deal(
            status_key="contract_completed",
            forecast_key="won",
            revenue_amount=777,
            revenue_date=date(2026, 9, 1),
        )

    async def test_leaving_won_needs_a_status_other_than_contract_completed(
        self, env: DealEnv
    ) -> None:
        """Won에서 벗어나려면 계약완료가 아닌 Status를 골라야 하고 거절되면 값이 그대로다.

        테스트 코드: DD-017
        """
        # given: 계약완료·Won Deal(금액 777)
        view = await self._won(env)

        for resolution in (
            None,
            SyncResolution(),
            SyncResolution(status_key="contract_completed"),
            SyncResolution(status_key="no_such_status"),
        ):
            with raises_with(InvalidValueError, CHOICE_REQUIRED):
                # when: 답이 없거나 계약완료·없는 key인 답으로 Forecast를 바꾼다
                await apply_change(env, view, "forecast_key", "commit", resolution)

        # then: 선택 필요 오류이고 계약완료·Won이 그대로다
        assert (await stored_values(env, view))[:2] == ("contract_completed", "won")

    async def test_leaving_won_changes_the_chosen_status_and_keeps_amount_and_date(
        self, env: DealEnv
    ) -> None:
        """Won에서 벗어나면 고른 Status가 함께 바뀌고 금액·매출일은 그대로다.

        테스트 코드: DD-017
        """
        # given: 계약완료·Won Deal(금액 777, 2026-09-01)
        view = await self._won(env)

        # when: POC완료를 골라 Forecast를 Commit으로 바꾼다
        result = await apply_change(
            env, view, "forecast_key", "commit", SyncResolution(status_key="poc_completed")
        )

        # then: POC완료·Commit, 금액·매출일 그대로, 함께 바뀐 Status와 알림, 이력 두 건이 남는다
        assert await stored_values(env, view) == ("poc_completed", "commit", 777, date(2026, 9, 1))
        assert result.co_changed == (
            CoChange(SyncField.STATUS, "contract_completed", "poc_completed"),
        )
        assert result.notice == "Status가 'POC완료'로 함께 변경되었습니다."
        assert await env.changes(view) == [
            ("status", "Status", "계약완료", "POC완료 (Forecast Commit과 함께 변경)"),
            ("forecast", "Forecast", "Won", "Commit"),
        ]

    async def test_leaving_contract_completed_needs_a_forecast_other_than_won(
        self, env: DealEnv
    ) -> None:
        """계약완료에서 이전 단계로 가려면 Won이 아닌 Forecast를 골라야 한다.

        테스트 코드: DD-019
        """
        # given: 계약완료·Won Deal
        view = await self._won(env)

        for resolution in (
            None,
            SyncResolution(forecast_key="won"),
            SyncResolution(forecast_key="zz"),
        ):
            with raises_with(InvalidValueError, CHOICE_REQUIRED):
                # when: 답이 없거나 Won·없는 key인 답으로 Status를 바꾼다
                await apply_change(env, view, "status_key", "poc_completed", resolution)

        # then: 선택 필요 오류이고 계약완료·Won이 그대로다
        assert (await stored_values(env, view))[:2] == ("contract_completed", "won")

    async def test_leaving_contract_completed_changes_the_chosen_forecast(
        self, env: DealEnv
    ) -> None:
        """계약완료에서 벗어나면 고른 Forecast가 함께 바뀌고 금액·매출일은 그대로다.

        테스트 코드: DD-019
        """
        # given: 계약완료·Won Deal(금액 777, 2026-09-01)
        view = await self._won(env)

        # when: Best를 골라 Status를 POC완료로 바꾼다
        result = await apply_change(
            env, view, "status_key", "poc_completed", SyncResolution(forecast_key="best")
        )

        # then: POC완료·Best, 금액·매출일 그대로, 함께 바뀐 Forecast와 알림, 이력이 남는다
        assert await stored_values(env, view) == ("poc_completed", "best", 777, date(2026, 9, 1))
        assert result.co_changed == (CoChange(SyncField.FORECAST, "won", "best"),)
        assert result.notice == "Forecast가 'Best'로 함께 변경되었습니다."
        assert await env.changes(view) == [
            ("status", "Status", "계약완료", "POC완료"),
            ("forecast", "Forecast", "Won", "Best (Status POC완료와 함께 변경)"),
        ]

    async def test_leaving_lost_asks_for_a_status_but_the_current_one_is_a_valid_answer(
        self, env: DealEnv
    ) -> None:
        """Lost에서 되돌리면 Status를 묻고 현재 Status를 그대로 고르면 함께 바뀐 값이 없다.

        테스트 코드: DD-020
        """
        # given: 가격협상·Lost Deal
        view = await env.new_deal(status_key="price_negotiation", forecast_key="lost")
        # when: 답 없이, 이어서 현재 Status를 골라 Forecast를 Best로 바꾼다
        with raises_with(InvalidValueError, CHOICE_REQUIRED):
            await apply_change(env, view, "forecast_key", "best")

        # then: 처음은 선택 필요 오류, 다음은 가격협상·Best, 함께 바뀐 값·알림 없이 이력만 남는다
        result = await apply_change(
            env, view, "forecast_key", "best", SyncResolution(status_key="price_negotiation")
        )

        assert (await stored_values(env, view))[:2] == ("price_negotiation", "best")
        assert result.co_changed == ()
        assert result.notice is None
        assert await env.changes(view) == [("forecast", "Forecast", "Lost", "Best")]
