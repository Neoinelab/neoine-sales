"""DeleteCode와 Action 스냅숏 참조(CD-007, CD-042~044): Action만 쓰는 코드도 사용 중이다."""

from typing import TYPE_CHECKING, Literal

import pytest

from app.application.code.delete_code import DeleteCode
from app.application.code.list_codes_with_usage import ListCodesWithUsage
from app.application.deal_action.inputs import StatusChangeInput
from app.domain.code.errors import CodeInUseError
from app.domain.code.values import CodeKind
from tests.support.catalog import code_by_key
from tests.support.expect import raises_with
from tests.unit.application.action_env import BOSS, KIM
from tests.unit.application.apply_helpers import apply_change

if TYPE_CHECKING:
    from app.domain.deal_action.entities import DealAction
    from tests.unit.application.action_env import ActionEnv

ONLY_ACTION = "사용 중인 코드는 삭제할 수 없습니다. (Action 1건)"
DEAL_FIRST = "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"


async def _snapshot_then_move_the_deal(
    action_env: ActionEnv, field: Literal["status_key", "forecast_key"], old: str, new: str
) -> DealAction:
    """old 값으로 Action을 등록한 뒤 Deal을 new 값으로 옮겨, old를 Action 스냅숏만 쓰게 한다."""
    change = StatusChangeInput(field, old, None)
    action = await action_env.act(KIM, status_changes=(change,))
    await apply_change(action_env.env, action_env.deal, field, new)
    return action


@pytest.mark.parametrize(
    ("kind", "field", "old", "new"),
    [
        (CodeKind.STATUS, "status_key", "introduction", "poc_preparation"),
        (CodeKind.FORECAST, "forecast_key", "best", "commit"),
    ],
)
async def test_delete_code_used_only_by_action_snapshots_conflicts_with_action_count(
    action_env: ActionEnv,
    kind: CodeKind,
    field: Literal["status_key", "forecast_key"],
    old: str,
    new: str,
) -> None:
    """Deal은 안 쓰고 Action 스냅숏만 쓰는 코드는 삭제할 수 없고 문구에 Action 수가 들어간다.

    테스트 코드: CD-042
    """
    # given: Deal이 old일 때 Action을 남기고 Deal을 new로 옮겨, old는 Action 스냅숏만 쓴다
    await _snapshot_then_move_the_deal(action_env, field, old, new)
    code = await code_by_key(action_env.env.uow, kind, old)

    # when: old 코드를 삭제한다
    with raises_with(CodeInUseError, ONLY_ACTION):
        await DeleteCode(action_env.env.uow_factory).execute(code.id)

    # then: 코드는 남는다
    assert (await action_env.env.uow.codes.get(code.id)).key.value == old


async def test_delete_code_used_by_deal_reports_deal_count_first(action_env: ActionEnv) -> None:
    """Deal과 Action이 함께 쓰는 코드는 Deal 수 문구가 먼저다.

    테스트 코드: CD-043
    """
    # given: 제품소개 Deal 1건과 그 상태의 Action 1건
    await action_env.act(
        KIM, status_changes=(StatusChangeInput("status_key", "introduction", None),)
    )
    code = await code_by_key(action_env.env.uow, CodeKind.STATUS, "introduction")

    # when: 제품소개를 삭제한다
    with raises_with(CodeInUseError, DEAL_FIRST):
        await DeleteCode(action_env.env.uow_factory).execute(code.id)

    # then: 코드는 남는다
    assert (await action_env.env.uow.codes.get(code.id)).key.value == "introduction"


async def test_the_code_becomes_deletable_once_its_last_action_is_gone(
    action_env: ActionEnv,
) -> None:
    """코드를 스냅숏으로 가진 마지막 Action이 없어지면 코드를 지울 수 있다.

    테스트 코드: CD-044
    """
    # given: 제품소개를 스냅숏으로 가진 유일한 Action이 삭제되었다(Deal은 다른 Status)
    action = await _snapshot_then_move_the_deal(
        action_env, "status_key", "introduction", "poc_preparation"
    )
    code = await code_by_key(action_env.env.uow, CodeKind.STATUS, "introduction")
    await action_env.delete.execute(action.id, BOSS)

    # when: 제품소개를 삭제한다
    await DeleteCode(action_env.env.uow_factory).execute(code.id)

    # then: 목록에서 사라진다
    keys = [c.key.value for c in await action_env.env.uow.codes.list(CodeKind.STATUS)]
    assert "introduction" not in keys


async def test_the_code_becomes_deletable_once_its_last_deal_is_gone(
    action_env: ActionEnv,
) -> None:
    """코드를 쓰던 마지막 Deal이 삭제되면 코드를 지울 수 있다.

    테스트 코드: CD-044
    """
    # given: Best를 쓰는 Deal 1건이 삭제되었다
    view = await action_env.env.new_deal(forecast_key="best")
    best = await code_by_key(action_env.env.uow, CodeKind.FORECAST, "best")
    with raises_with(CodeInUseError, DEAL_FIRST):
        await DeleteCode(action_env.env.uow_factory).execute(best.id)
    await action_env.env.uow.deals.delete(view.item.deal.id)

    # when: Best를 삭제한다
    await DeleteCode(action_env.env.uow_factory).execute(best.id)

    # then: 목록에서 사라진다
    keys = [c.key.value for c in await action_env.env.uow.codes.list(CodeKind.FORECAST)]
    assert "best" not in keys


async def test_usage_count_of_the_code_list_counts_deals_only(action_env: ActionEnv) -> None:
    """사용 수는 Action 스냅숏을 세지 않고 Deal의 현재 값만 센다.

    테스트 코드: CD-007
    """
    # given: Deal이 제품소개일 때 Action을 남기고(스냅숏 introduction) Deal을 POC준비로 옮긴다
    await _snapshot_then_move_the_deal(action_env, "status_key", "introduction", "poc_preparation")

    # when: Status 사용 현황을 읽는다
    usage = await ListCodesWithUsage(action_env.env.uow_factory).execute(CodeKind.STATUS)

    # then: introduction 0, poc_preparation 1이다
    counts = {u.code.key.value: u.usage_count for u in usage}
    assert counts["introduction"] == 0
    assert counts["poc_preparation"] == 1


@pytest.mark.parametrize(
    ("kind", "key"),
    [(CodeKind.STATUS, "technical_evaluation"), (CodeKind.FORECAST, "most_likely")],
)
async def test_an_unused_code_is_still_deleted(
    action_env: ActionEnv, kind: CodeKind, key: str
) -> None:
    """Action이 있어도 그 Action이 쓰지 않는 코드는 지워진다.

    테스트 코드: CD-039
    """
    # given: 다른 코드를 스냅숏으로 가진 Action 1건
    await action_env.act(KIM)
    code = await code_by_key(action_env.env.uow, kind, key)

    # when: 쓰이지 않는 코드를 삭제한다
    await DeleteCode(action_env.env.uow_factory).execute(code.id)

    # then: 그 코드가 사라진다
    assert key not in [c.key.value for c in await action_env.env.uow.codes.list(kind)]
