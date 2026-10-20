"""DeleteCode와 Action 스냅숏 참조(AC-18, R-16): Deal은 안 쓰고 Action만 쓰는 코드도 사용 중이다."""

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


async def test_delete_code_used_only_by_actions_conflicts_with_action_count(
    action_env: ActionEnv,
) -> None:
    await _snapshot_then_move_the_deal(action_env, "status_key", "introduction", "poc_preparation")
    code = await code_by_key(action_env.env.uow, CodeKind.STATUS, "introduction")

    with raises_with(CodeInUseError, ONLY_ACTION):
        await DeleteCode(action_env.env.uow_factory).execute(code.id)

    assert (await action_env.env.uow.codes.get(code.id)).key.value == "introduction"


async def test_forecast_code_used_only_by_action_snapshots_conflicts_too(
    action_env: ActionEnv,
) -> None:
    await _snapshot_then_move_the_deal(action_env, "forecast_key", "best", "commit")
    code = await code_by_key(action_env.env.uow, CodeKind.FORECAST, "best")

    with raises_with(CodeInUseError, ONLY_ACTION):
        await DeleteCode(action_env.env.uow_factory).execute(code.id)


async def test_delete_code_used_by_deal_reports_deal_count_first(action_env: ActionEnv) -> None:
    await action_env.act(
        KIM, status_changes=(StatusChangeInput("status_key", "introduction", None),)
    )
    code = await code_by_key(action_env.env.uow, CodeKind.STATUS, "introduction")

    with raises_with(CodeInUseError, DEAL_FIRST):  # Action도 쓰지만 Deal 문구가 먼저다
        await DeleteCode(action_env.env.uow_factory).execute(code.id)


async def test_the_code_becomes_deletable_once_its_last_action_is_gone(
    action_env: ActionEnv,
) -> None:
    action = await _snapshot_then_move_the_deal(
        action_env, "status_key", "introduction", "poc_preparation"
    )
    code = await code_by_key(action_env.env.uow, CodeKind.STATUS, "introduction")
    await action_env.delete.execute(action.id, BOSS)

    await DeleteCode(action_env.env.uow_factory).execute(code.id)

    keys = [c.key.value for c in await action_env.env.uow.codes.list(CodeKind.STATUS)]
    assert "introduction" not in keys


async def test_usage_count_of_the_code_list_counts_deals_only(action_env: ActionEnv) -> None:
    await _snapshot_then_move_the_deal(action_env, "status_key", "introduction", "poc_preparation")

    usage = await ListCodesWithUsage(action_env.env.uow_factory).execute(CodeKind.STATUS)

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
    await action_env.act(KIM)
    code = await code_by_key(action_env.env.uow, kind, key)

    await DeleteCode(action_env.env.uow_factory).execute(code.id)

    assert key not in [c.key.value for c in await action_env.env.uow.codes.list(kind)]
