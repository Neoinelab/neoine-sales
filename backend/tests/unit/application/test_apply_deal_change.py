"""ApplyDealChange의 종결·되돌림(AC-19·20·21): 규칙표, 선택 필수, notice, 이력.

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
        view = await env.new_deal()

        result = await apply_change(env, view, "status_key", "contract_completed", CLOSING)

        assert await stored_values(env, view) == ("contract_completed", "won", 900_000_000, DAY)
        assert result.view.item.deal.sync.forecast_key == "won"
        assert result.co_changed == (CoChange(SyncField.FORECAST, "pipeline", "won"),)
        assert result.notice == "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."

    async def test_forecast_to_won_also_sets_contract_completed_and_saves_the_revenue(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal()

        result = await apply_change(env, view, "forecast_key", "won", CLOSING)

        assert await stored_values(env, view) == ("contract_completed", "won", 900_000_000, DAY)
        assert result.co_changed == (
            CoChange(SyncField.STATUS, "prospecting", "contract_completed"),
        )
        assert result.notice == "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."

    async def test_the_history_marks_the_value_that_changed_together(self, env: DealEnv) -> None:
        view = await env.new_deal()

        await apply_change(env, view, "status_key", "contract_completed", CLOSING)

        assert await env.changes(view) == [
            ("status", "Status", "기회발굴", "계약완료"),
            ("forecast", "Forecast", "Pipeline", "Won (Status 계약완료와 함께 변경)"),
            ("amount", "금액(단위:천원)", "150,000", "900,000"),
            ("expectedClose", "Expected Close", "2026-06-30", "2026-10-20"),
        ]

    async def test_the_history_from_the_forecast_side_marks_the_status(self, env: DealEnv) -> None:
        view = await env.new_deal()

        await apply_change(env, view, "forecast_key", "won", CLOSING)

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
        view = await env.new_deal()
        before = await stored_values(env, view)

        with raises_with(InvalidValueError, REVENUE_REQUIRED):
            await apply_change(env, view, field, value, resolution)

        assert await stored_values(env, view) == before
        assert await env.changes(view) == []

    async def test_lost_to_won_is_a_closing_too(self, env: DealEnv) -> None:
        view = await env.new_deal(status_key="price_negotiation", forecast_key="lost")

        result = await apply_change(env, view, "forecast_key", "won", CLOSING)

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
        view = await self._won(env)

        for resolution in (
            None,
            SyncResolution(),
            SyncResolution(status_key="contract_completed"),
            SyncResolution(status_key="no_such_status"),
        ):
            with raises_with(InvalidValueError, CHOICE_REQUIRED):
                await apply_change(env, view, "forecast_key", "commit", resolution)

        assert (await stored_values(env, view))[:2] == ("contract_completed", "won")

    async def test_leaving_won_changes_the_chosen_status_and_keeps_amount_and_date(
        self, env: DealEnv
    ) -> None:
        view = await self._won(env)

        result = await apply_change(
            env, view, "forecast_key", "commit", SyncResolution(status_key="poc_completed")
        )

        assert await stored_values(env, view) == ("poc_completed", "commit", 777, date(2026, 9, 1))
        assert result.co_changed == (
            CoChange(SyncField.STATUS, "contract_completed", "poc_completed"),
        )
        assert result.notice == "Status가 'POC완료'로 함께 변경되었습니다."
        assert await env.changes(view) == [
            ("status", "Status", "계약완료", "POC완료 (Forecast Commit와 함께 변경)"),
            ("forecast", "Forecast", "Won", "Commit"),
        ]

    async def test_leaving_contract_completed_needs_a_forecast_other_than_won(
        self, env: DealEnv
    ) -> None:
        view = await self._won(env)

        for resolution in (
            None,
            SyncResolution(forecast_key="won"),
            SyncResolution(forecast_key="zz"),
        ):
            with raises_with(InvalidValueError, CHOICE_REQUIRED):
                await apply_change(env, view, "status_key", "poc_completed", resolution)

        assert (await stored_values(env, view))[:2] == ("contract_completed", "won")

    async def test_leaving_contract_completed_changes_the_chosen_forecast(
        self, env: DealEnv
    ) -> None:
        view = await self._won(env)

        result = await apply_change(
            env, view, "status_key", "poc_completed", SyncResolution(forecast_key="best")
        )

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
        view = await env.new_deal(status_key="price_negotiation", forecast_key="lost")
        with raises_with(InvalidValueError, CHOICE_REQUIRED):
            await apply_change(env, view, "forecast_key", "best")

        result = await apply_change(
            env, view, "forecast_key", "best", SyncResolution(status_key="price_negotiation")
        )

        assert (await stored_values(env, view))[:2] == ("price_negotiation", "best")
        assert result.co_changed == ()
        assert result.notice is None
        assert await env.changes(view) == [("forecast", "Forecast", "Lost", "Best")]
