"""ApplyDealChange의 코드 목록 읽기: 같은 종류의 코드 목록을 한 번만 읽는다.

공용 동기화 협력자(`sync_change`)로 추출한 뒤에도 Status·Forecast를 각각 한 번씩만 읽는다.
Fake 코드 저장소의 `list_calls`(읽은 종류 기록)로 확인한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.code.values import CodeKind
from tests.unit.application.apply_helpers import CLOSING, apply_change

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


@pytest.mark.parametrize(
    ("field", "value", "resolution"),
    [
        ("status_key", "introduction", None),
        ("forecast_key", "best", None),
        ("status_key", "contract_completed", CLOSING),
    ],
)
async def test_apply_deal_change_reads_codes_once_per_kind(
    env: DealEnv, field: str, value: str, resolution: object
) -> None:
    """Status·Forecast 변경은 각 종류의 코드 목록을 한 번씩만 읽는다."""
    # given: Deal 하나를 만들고 코드 목록 읽기 기록을 비운다
    view = await env.new_deal()
    env.uow.codes.list_calls.clear()

    # when: 변경 하나를 적용한다
    await apply_change(env, view, field, value, resolution)  # type: ignore[arg-type]

    # then: Forecast와 Status 목록을 각각 한 번씩만 읽었다
    assert sorted(env.uow.codes.list_calls, key=str) == [CodeKind.FORECAST, CodeKind.STATUS]


async def test_a_revenue_change_still_reads_each_kind_at_most_once(env: DealEnv) -> None:
    """매출액 변경도 코드 종류마다 최대 한 번만 읽는다."""
    # given: Deal 하나를 만들고 코드 목록 읽기 기록을 비운다
    view = await env.new_deal()
    env.uow.codes.list_calls.clear()

    # when: 매출액을 변경한다
    await apply_change(env, view, "revenue_amount", 1_000)

    # then: 같은 종류를 두 번 읽지 않고 종류는 최대 둘이다
    assert len(env.uow.codes.list_calls) == len(set(env.uow.codes.list_calls)) <= 2
