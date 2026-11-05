"""종료·계약 칸 수정·삭제(AC11·AC14·AC15)."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.license_contract.errors import (
    ContractDeleteForbiddenError,
    ContractTransitionError,
    LicenseContractNotFoundError,
)
from app.domain.license_contract.values import ContractFields, ContractStatus, InspectionCycle
from tests.support.expect import raises_with
from tests.support.ids import MISSING_ID
from tests.unit.application.license_contract_env import BOSS, KIM, PARK, VIEWER

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv

ALREADY_ENDED = "이미 종료된 계약입니다."
NOT_ISSUED_ONLY = "미발급 계약만 발급할 수 있습니다."
ISSUED_ONLY = "발급 상태 계약만 갱신할 수 있습니다."
DELETE_FORBIDDEN = "계약 삭제는 관리자만 할 수 있습니다."
NEW_FIELDS = ContractFields(tech_owner="이기술", inspection=InspectionCycle.YEARLY, note="메모")


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal"])
async def test_end_moves_the_contract_to_ended(contract_env: ContractEnv, status: str) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status=status)

    await contract_env.end.execute(contract.id, PARK)

    stored = await contract_env.stored(contract.id)
    assert stored.status is ContractStatus.ENDED
    assert stored.ended_at == contract_env.clock.now()
    assert stored.updated_by == PARK.user_id


async def test_end_twice_raises_and_keeps_the_first_end_time(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status="ended")
    first = (await contract_env.stored(contract.id)).ended_at
    contract_env.clock.advance(600)

    with raises_with(ContractTransitionError, ALREADY_ENDED):
        await contract_env.end.execute(contract.id, KIM)

    assert (await contract_env.stored(contract.id)).ended_at == first


async def test_ended_contract_cannot_be_issued_or_renewed(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal_without_contract()
    contract = await contract_env.seed_contract(code, status="ended")

    with raises_with(ContractTransitionError, NOT_ISSUED_ONLY):
        await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)
    with raises_with(ContractTransitionError, ISSUED_ONLY):
        await contract_env.renew.execute(contract.id, contract_env.issue_input(), KIM)


async def test_ending_a_contract_allows_issuing_another_one_of_the_deal(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract()
    issued = await contract_env.seed_contract(code, status="issued_new")
    waiting = await contract_env.seed_contract(code)

    await contract_env.end.execute(issued.id, KIM)
    await contract_env.issue.execute(waiting.id, contract_env.issue_input(), KIM)

    assert (await contract_env.stored(waiting.id)).status is ContractStatus.ISSUED_NEW


async def test_end_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.end.execute(MISSING_ID, KIM)  # type: ignore[arg-type]


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal", "ended"])
async def test_update_saves_the_contract_fields_in_every_status(
    contract_env: ContractEnv, status: str
) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status=status, start=date(2026, 1, 1))

    await contract_env.update.execute(contract.id, NEW_FIELDS, PARK)

    stored = await contract_env.stored(contract.id)
    assert stored.fields == NEW_FIELDS
    assert stored.status is ContractStatus(status)
    assert stored.license_start == contract.license_start
    assert stored.updated_by == PARK.user_id


async def test_update_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.update.execute(MISSING_ID, NEW_FIELDS, KIM)  # type: ignore[arg-type]


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal", "ended"])
async def test_delete_by_admin_works_in_any_status(contract_env: ContractEnv, status: str) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status=status)

    await contract_env.delete.execute(contract.id, BOSS)

    assert await contract_env.contracts_of(code) == []


@pytest.mark.parametrize("actor", [KIM, VIEWER])
async def test_delete_by_non_admin_is_forbidden_and_removes_nothing(
    contract_env: ContractEnv, actor: object
) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status="ended")
    attachment = await contract_env.seed_file(contract)

    with raises_with(ContractDeleteForbiddenError, DELETE_FORBIDDEN):
        await contract_env.delete.execute(contract.id, actor)  # type: ignore[arg-type]

    assert len(await contract_env.contracts_of(code)) == 1
    assert contract_env.content_of(attachment) == b"hello"


async def test_delete_missing_contract_is_not_found_before_the_permission_check(
    contract_env: ContractEnv,
) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.delete.execute(MISSING_ID, KIM)  # type: ignore[arg-type]


async def test_delete_contract_by_admin_removes_files_after_commit(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status="issued_new")
    first = await contract_env.seed_file(contract, name="a.pdf", data=b"one")
    second = await contract_env.seed_file(contract, name="b.pdf", data=b"two")

    await contract_env.delete.execute(contract.id, BOSS)

    assert await contract_env.all_file_rows() == []
    assert contract_env.content_of(first) is None
    assert contract_env.content_of(second) is None
    assert not contract_env.contract_folder_exists(contract.id)  # 폴더째 지워진다(AC33)


async def test_delete_contract_keeps_other_contracts_and_the_deal_files(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    target = await contract_env.seed_contract(code, status="ended")
    sibling = await contract_env.seed_contract(code)
    gone = await contract_env.seed_file(target, name="gone.pdf")
    kept = await contract_env.seed_file(sibling, name="kept.pdf", data=b"sibling")
    deal_file = await contract_env.seed_deal_file(code)

    await contract_env.delete.execute(target.id, BOSS)

    assert [c.id for c in await contract_env.contracts_of(code)] == [sibling.id]
    assert contract_env.content_of(gone) is None
    assert not contract_env.contract_folder_exists(target.id)
    assert contract_env.content_of(kept) == b"sibling"  # 다른 계약 폴더는 그대로
    assert contract_env.contract_folder_exists(sibling.id)
    assert contract_env.content_of(deal_file) == b"deal"  # Deal 첨부(Deal 폴더)도 그대로


async def test_delete_contract_survives_a_file_cleanup_failure(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    await contract_env.seed_file(contract)
    contract_env.storage.fail_deletes = True

    await contract_env.delete.execute(contract.id, BOSS)  # DB가 정본이다

    assert await contract_env.contracts_of(code) == []


async def test_delete_contract_without_storage_settings_still_removes_the_rows(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    attachment = await contract_env.seed_file(contract)
    await contract_env.remove_storage_settings()

    await contract_env.delete.execute(contract.id, BOSS)

    assert await contract_env.all_file_rows() == []
    assert contract_env.content_of(attachment) == b"hello"  # 위치를 몰라 파일은 둔다


async def test_deleting_the_renewed_row_clears_the_link_of_its_successor(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(code, status="issued_new")
    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)

    await contract_env.delete.execute(previous.id, BOSS)

    (renewal,) = await contract_env.contracts_of(code)
    assert renewal.renewed_from_id is None
