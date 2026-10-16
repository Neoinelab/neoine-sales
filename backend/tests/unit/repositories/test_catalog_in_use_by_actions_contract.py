"""코드 삭제의 Action 스냅숏 참조 계약(AC-18): Fake와 SQL(PostgreSQL)에 같은 기대값.

Deal은 안 쓰고 Action 스냅숏만 쓰는 코드를 지우면 행을 남기고 CodeInUseError "(Action N건)"을
낸다(SQL은 `fk_deal_actions_*_code` FK 위반을 이 오류로 바꾼다). Deal도 쓰면 Deal 수가 먼저다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_action_repository import DealActionQuery
from app.domain.code.errors import CodeInUseError
from app.domain.code.values import CodeKind
from tests.factories import later, make_deal, make_deal_code, make_sync
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from app.domain.code.entities import Code
    from tests.unit.repositories.deal_case import DealCase

CODE = make_deal_code()


async def _code(case: DealCase, kind: CodeKind, key: str) -> Code:
    found: Code = next(c for c in await case.codes.list(kind) if c.key.value == key)
    return found


@pytest.mark.parametrize(
    ("kind", "key", "snapshot"),
    [
        (CodeKind.STATUS, "introduction", make_sync("introduction", "pipeline")),
        (CodeKind.FORECAST, "best", make_sync("prospecting", "best")),
    ],
)
async def test_a_code_used_only_by_action_snapshots_is_not_deleted_and_reports_the_count(
    deal_case: DealCase, kind: CodeKind, key: str, snapshot: object
) -> None:
    deal = make_deal(later(1), code=CODE)  # Deal 자신은 prospecting/pipeline이다
    await deal_case.add(deal)
    await deal_case.add_action(deal, later(2), snapshot=snapshot)
    await deal_case.add_action(deal, later(3), snapshot=snapshot)
    code = await _code(deal_case, kind, key)

    with raises_with(CodeInUseError, "사용 중인 코드는 삭제할 수 없습니다. (Action 2건)"):
        await deal_case.codes.delete(code.id)

    assert (await deal_case.codes.get(code.id)).key.value == key


async def test_deal_usage_is_reported_before_action_usage(deal_case: DealCase) -> None:
    deal = make_deal(later(1), code=CODE, status_key="introduction")
    await deal_case.add(deal)
    await deal_case.add_action(deal, later(2), snapshot=make_sync("introduction", "pipeline"))
    code = await _code(deal_case, CodeKind.STATUS, "introduction")

    with raises_with(CodeInUseError, "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"):
        await deal_case.codes.delete(code.id)


async def test_the_transaction_stays_usable_after_the_refusal(deal_case: DealCase) -> None:
    deal = make_deal(later(1), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, later(2), snapshot=make_sync("introduction", "pipeline"))
    code = await _code(deal_case, CodeKind.STATUS, "introduction")

    with pytest.raises(CodeInUseError):
        await deal_case.codes.delete(code.id)

    await deal_case.add_action(deal, later(3))
    assert len(await deal_case.actions.search(DealActionQuery(deal_code=CODE))) == 2


async def test_the_code_becomes_deletable_once_its_last_action_is_gone(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(1), code=CODE)
    await deal_case.add(deal)
    action = await deal_case.add_action(
        deal, later(2), snapshot=make_sync("introduction", "pipeline")
    )
    code = await _code(deal_case, CodeKind.STATUS, "introduction")
    await deal_case.actions.delete(action.id)

    await deal_case.codes.delete(code.id)

    keys = [c.key.value for c in await deal_case.codes.list(CodeKind.STATUS)]
    assert "introduction" not in keys


async def test_the_code_becomes_deletable_once_its_deal_and_actions_are_deleted(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(1), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, later(2), snapshot=make_sync("introduction", "pipeline"))
    code = await _code(deal_case, CodeKind.STATUS, "introduction")
    await deal_case.deals.delete(deal.id)  # Action도 함께 지워진다

    await deal_case.codes.delete(code.id)

    keys = [c.key.value for c in await deal_case.codes.list(CodeKind.STATUS)]
    assert "introduction" not in keys
