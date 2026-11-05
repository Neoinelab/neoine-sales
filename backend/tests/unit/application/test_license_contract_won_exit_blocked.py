"""발급 계약이 있는 Deal의 Won 이탈 거부(AC23~AC25).

발급 상태(issued_new·issued_renewal) 계약이 있는 Deal은 Deal 변경 세 경로(목록 인라인 변경, Deal 폼
수정, Action 등록의 status_changes)로 Won에서 벗어날 수 없다. `delete_license_contracts`가 true·
false·생략 어느 것이든 409(InvalidStateError)이고, 커밋 전에 거부하므로 Deal·이력·계약·첨부 파일·
Action·이전 Next Action이 모두 그대로다. 미발급·종료 계약뿐이면 기존 삭제/유지 규칙이 그대로다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import DealChangeInput
from app.application.deal_action.inputs import DealActionInput, StatusChangeInput
from app.domain.common.errors import InvalidStateError
from app.domain.deal.sync import SyncResolution
from tests.factories import make_deal_action_input
from tests.support.expect import raises_with
from tests.unit.application.license_contract_env import BOSS, KIM, LEAVE_WON, PARK

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv

WON_EXIT_BLOCKED = (
    "발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. "
    "계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요."
)
PATHS = ["change", "status_change", "form", "action"]


async def _leave(contract_env: ContractEnv, path: str, code: str, flag: bool | None) -> object:
    if path == "status_change":
        extra = {} if flag is None else {"delete_license_contracts": flag}
        change = DealChangeInput(
            field="status_key",
            value="poc_completed",
            resolution=SyncResolution(forecast_key="commit"),
            **extra,
        )
        return await contract_env.env.apply.execute(code, change, KIM)
    leave = {
        "change": contract_env.leave_won_by_change,
        "form": contract_env.leave_won_by_form,
        "action": contract_env.leave_won_by_action,
    }[path]
    return await leave(code, KIM, delete_contracts=flag)


@pytest.mark.parametrize("flag", [None, True, False])
@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("status", ["issued_new", "issued_renewal"])
async def test_leave_won_with_issued_contract_raises_blocked_and_keeps_everything(
    contract_env: ContractEnv, status: str, path: str, flag: bool | None
) -> None:
    from app.domain.license_contract.errors import WonExitBlockedError  # noqa: PLC0415

    code = await contract_env.won_deal_without_contract(KIM)
    issued = await contract_env.seed_contract(code, status=status)
    attachment = await contract_env.seed_file(issued, data=b"signed")
    history_before = await contract_env.env.history_rows(code)
    commits_before = contract_env.uow.commits

    with raises_with(WonExitBlockedError, WON_EXIT_BLOCKED):
        await _leave(contract_env, path, code, flag)

    assert await contract_env.forecast_of(code) == "won"
    assert [c.id for c in await contract_env.contracts_of(code)] == [issued.id]
    assert (await contract_env.stored(issued.id)).status.value == status
    assert contract_env.content_of(attachment) == b"signed"
    assert contract_env.contract_folder_exists(issued.id)
    assert await contract_env.env.history_rows(code) == history_before
    assert contract_env.uow.commits == commits_before


async def test_the_blocked_error_is_an_invalid_state_error(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    await contract_env.seed_contract(code, status="issued_new")

    with pytest.raises(InvalidStateError):
        await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)


async def test_blocked_leave_is_refused_for_every_role_that_may_change_the_deal(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    await contract_env.seed_contract(code, status="issued_new")

    for actor in (PARK, BOSS):
        with pytest.raises(InvalidStateError):
            await contract_env.leave_won_by_change(code, actor)

    assert await contract_env.forecast_of(code) == "won"


async def test_register_action_blocked_leave_saves_no_action_and_keeps_previous_next_action(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    await contract_env.seed_contract(code, status="issued_new")
    contract_env.clock.advance(60)
    previous = await contract_env.register_action.execute(
        code, DealActionInput(content=make_deal_action_input()), KIM
    )
    actions_before = dict(contract_env.uow.deal_actions._items)
    contract_env.clock.advance(60)
    leave = DealActionInput(
        content=make_deal_action_input(),
        status_changes=(
            StatusChangeInput(field="forecast_key", value="commit", resolution=LEAVE_WON),
        ),
        close_previous_next_action_id=previous.id,
        delete_license_contracts=True,
    )

    with pytest.raises(InvalidStateError):
        await contract_env.register_action.execute(code, leave, KIM)

    assert list(contract_env.uow.deal_actions._items) == list(actions_before)
    stored = contract_env.uow.deal_actions._items[previous.id]
    assert stored.next_action_state is not None
    assert stored.next_action_state.status.value == "open"


async def test_leave_won_with_ended_only_contracts_still_asks_and_deletes_by_sales(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    await contract_env.seed_contract(code, status="ended")
    await contract_env.seed_contract(code)  # 미발급

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)  # sales도 삭제(D11-A)

    assert await contract_env.contracts_of(code) == []
    assert await contract_env.forecast_of(code) == "commit"


@pytest.mark.parametrize("path", PATHS)
async def test_leave_won_with_ended_only_and_keep_leaves_the_contracts(
    contract_env: ContractEnv, path: str
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    ended = await contract_env.seed_contract(code, status="ended")

    await _leave(contract_env, path, code, False)

    assert [c.id for c in await contract_env.contracts_of(code)] == [ended.id]
    assert await contract_env.forecast_of(code) == "commit"


async def test_leave_won_after_admin_deleted_the_issued_contract_succeeds(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    issued = await contract_env.seed_contract(code, status="issued_new")
    await contract_env.delete.execute(issued.id, BOSS)  # 오류 정정 경로(AC15)

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    assert await contract_env.forecast_of(code) == "commit"


async def test_leave_won_is_allowed_once_the_issued_contract_is_ended(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    issued = await contract_env.seed_contract(code, status="issued_new")
    await contract_env.end.execute(issued.id, KIM)

    await contract_env.leave_won_by_form(code, KIM, delete_contracts=False)

    assert await contract_env.forecast_of(code) == "commit"
    assert [c.id for c in await contract_env.contracts_of(code)] == [issued.id]


async def test_issued_contract_does_not_block_changes_that_keep_the_deal_won(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    await contract_env.seed_contract(code, status="issued_new")
    change = DealChangeInput(field="revenue_amount", value=123_000_000)

    await contract_env.env.apply.execute(code, change, KIM)

    assert await contract_env.forecast_of(code) == "won"
