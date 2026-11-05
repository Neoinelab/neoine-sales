"""Won 이탈 시 계약 삭제 선택(AC7·AC8).

Won인 Deal을 Won이 아닌 상태로 바꾸면서 delete_license_contracts=True를 보내면 그 Deal의 계약과
계약 첨부 행이 모두 지워지고 커밋 뒤 계약 폴더(`license-contracts/<id>`)도 통째로 지워진다(Deal 첨부
파일은 그대로). 발급 계약이 있으면 이 경로는 거부된다(test_license_contract_won_exit_blocked.py).
생략하거나 False면 계약은 그대로다. Won을 벗어나는 변경이 아니면 플래그는 무시된다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import DealChangeInput
from app.domain.common.errors import InvalidValueError
from tests.unit.application.license_contract_env import CLOSING, KIM

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv


async def _won_with_files(contract_env: ContractEnv) -> tuple[str, list[bytes | None], object]:
    """Won Deal, 계약 첨부 둘(계약 하나 + 다른 계약 하나), Deal 첨부 하나를 둔다."""
    code = await contract_env.won_deal(KIM)
    (first,) = await contract_env.contracts_of(code)
    second = await contract_env.seed_contract(code, status="ended")
    a = await contract_env.seed_file(first, name="a.pdf", data=b"first")
    b = await contract_env.seed_file(second, name="b.pdf", data=b"second")
    deal_file = await contract_env.seed_deal_file(code)
    return code, [contract_env.content_of(a), contract_env.content_of(b)], deal_file


async def test_apply_change_leave_won_with_delete_removes_contracts_and_files_after_commit(
    contract_env: ContractEnv,
) -> None:
    code, _, deal_file = await _won_with_files(contract_env)
    contract_ids = [c.id for c in await contract_env.contracts_of(code)]
    assert len(contract_ids) == 2
    assert all(contract_env.contract_folder_exists(i) for i in contract_ids)

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    assert not any(contract_env.contract_folder_exists(i) for i in contract_ids)  # 계약 폴더별 삭제
    assert contract_env.deal_folder_exists(code)  # Deal 폴더(Deal 첨부)는 지우지 않는다
    assert await contract_env.contracts_of(code) == []
    assert await contract_env.all_file_rows() == []
    assert contract_env.storage.file_count() == 1  # Deal 첨부 파일 하나만 남는다
    assert contract_env.content_of(deal_file) == b"deal"  # type: ignore[arg-type]
    assert await contract_env.forecast_of(code) == "commit"  # Deal 변경은 그대로 적용된다


async def test_update_deal_leave_won_with_delete_removes_contracts(
    contract_env: ContractEnv,
) -> None:
    code, _, _ = await _won_with_files(contract_env)

    await contract_env.leave_won_by_form(code, KIM, delete_contracts=True)

    assert await contract_env.contracts_of(code) == []
    assert await contract_env.all_file_rows() == []
    assert contract_env.storage.file_count() == 1


async def test_register_action_leave_won_with_delete_removes_contracts(
    contract_env: ContractEnv,
) -> None:
    code, _, _ = await _won_with_files(contract_env)

    await contract_env.leave_won_by_action(code, KIM, delete_contracts=True)

    assert await contract_env.contracts_of(code) == []
    assert await contract_env.all_file_rows() == []
    assert contract_env.storage.file_count() == 1


@pytest.mark.parametrize("flag", [None, False])
@pytest.mark.parametrize("path", ["change", "form", "action"])
async def test_leave_won_without_the_flag_keeps_contracts_and_files(
    contract_env: ContractEnv, path: str, flag: bool | None
) -> None:
    code, contents, _ = await _won_with_files(contract_env)
    leave = {
        "change": contract_env.leave_won_by_change,
        "form": contract_env.leave_won_by_form,
        "action": contract_env.leave_won_by_action,
    }[path]

    await leave(code, KIM, delete_contracts=flag)

    assert len(await contract_env.contracts_of(code)) == 2
    assert len(await contract_env.all_file_rows()) == 2
    assert contract_env.storage.file_count() == 3
    assert await contract_env.forecast_of(code) == "commit"
    assert contents == [b"first", b"second"]


async def test_update_deal_leave_won_without_flag_keeps_contracts(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal(KIM)

    await contract_env.leave_won_by_form(code, KIM)

    assert len(await contract_env.contracts_of(code)) == 1


async def test_delete_flag_ignored_when_not_leaving_won(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status="ended")  # Won 아닌 Deal에 남은 계약
    await contract_env.seed_file(contract)
    change = DealChangeInput(field="forecast_key", value="commit", delete_license_contracts=True)

    await contract_env.env.apply.execute(code, change, KIM)  # 오류 없음

    assert [c.id for c in await contract_env.contracts_of(code)] == [contract.id]
    assert len(await contract_env.all_file_rows()) == 1
    assert contract_env.storage.file_count() == 1


async def test_delete_flag_ignored_when_the_deal_stays_won(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal(KIM)
    change = DealChangeInput(
        field="revenue_amount", value=123_000_000, delete_license_contracts=True
    )

    await contract_env.env.apply.execute(code, change, KIM)

    assert len(await contract_env.contracts_of(code)) == 1


async def test_delete_flag_ignored_when_entering_won(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    change = DealChangeInput(
        field="forecast_key", value="won", resolution=CLOSING, delete_license_contracts=True
    )

    await contract_env.env.apply.execute(code, change, KIM)

    assert len(await contract_env.contracts_of(code)) == 1  # 진입 규칙대로 자동 생성된다


async def test_leave_won_with_delete_succeeds_when_the_deal_has_no_contract(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal(KIM)
    for contract in await contract_env.contracts_of(code):
        await contract_env.uow.license_contracts.delete(contract.id)

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    assert await contract_env.contracts_of(code) == []
    assert await contract_env.forecast_of(code) == "commit"


async def test_leave_won_with_delete_removes_only_this_deals_contracts(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal(KIM)
    other = await contract_env.won_deal(KIM)

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    assert await contract_env.contracts_of(code) == []
    assert len(await contract_env.contracts_of(other)) == 1


async def test_rejected_change_with_delete_flag_keeps_contracts_and_files(
    contract_env: ContractEnv,
) -> None:
    code, _, _ = await _won_with_files(contract_env)
    change = DealChangeInput(
        field="forecast_key", value="commit", delete_license_contracts=True
    )  # 함께 바꿀 Status 선택이 없어 거절된다

    with pytest.raises(InvalidValueError):
        await contract_env.env.apply.execute(code, change, KIM)

    assert len(await contract_env.contracts_of(code)) == 2
    assert len(await contract_env.all_file_rows()) == 2
    assert contract_env.storage.file_count() == 3
    assert await contract_env.forecast_of(code) == "won"


async def test_leave_won_with_delete_succeeds_without_storage_settings(
    contract_env: ContractEnv,
) -> None:
    code, _, _ = await _won_with_files(contract_env)
    await contract_env.remove_storage_settings()

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    assert await contract_env.contracts_of(code) == []
    assert await contract_env.all_file_rows() == []
    assert contract_env.storage.file_count() == 3  # 저장 위치를 몰라 파일은 그대로 둔다


async def test_leave_won_with_delete_survives_a_file_cleanup_failure(
    contract_env: ContractEnv,
) -> None:
    code, _, _ = await _won_with_files(contract_env)
    contract_env.storage.fail_deletes = True

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)  # DB가 정본이다

    assert await contract_env.contracts_of(code) == []
    assert await contract_env.forecast_of(code) == "commit"
