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
MISSING_CONTRACT = "라이선스 계약을 찾을 수 없습니다."
NEW_FIELDS = ContractFields(tech_owner="이기술", inspection=InspectionCycle.YEARLY, note="메모")


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal"])
async def test_end_moves_the_contract_to_ended(contract_env: ContractEnv, status: str) -> None:
    """미발급·발급 계약을 종료하면 종료 시각이 기록되고 수정자가 바뀐다.

    테스트 코드: LC-054
    """
    # given: 미발급 또는 발급 상태 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status=status)

    # when: PARK가 종료한다
    await contract_env.end.execute(contract.id, PARK)

    stored = await contract_env.stored(contract.id)
    # then: 상태 ended, ended_at은 요청 시각, 수정자는 PARK
    assert stored.status is ContractStatus.ENDED
    assert stored.ended_at == contract_env.clock.now()
    assert stored.updated_by == PARK.user_id


async def test_end_twice_raises_and_keeps_the_first_end_time(contract_env: ContractEnv) -> None:
    """이미 종료된 계약을 다시 종료하면 오류이고 첫 종료 시각이 유지된다.

    테스트 코드: LC-055
    """
    # given: 종료 계약(첫 종료 시각 기억)과 10분 뒤
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status="ended")
    first = (await contract_env.stored(contract.id)).ended_at
    contract_env.clock.advance(600)

    # when: 다시 종료한다
    with raises_with(ContractTransitionError, ALREADY_ENDED):
        await contract_env.end.execute(contract.id, KIM)

    # then: ContractTransitionError 문구, ended_at은 첫 값 그대로
    assert (await contract_env.stored(contract.id)).ended_at == first


async def test_ended_contract_cannot_be_issued_or_renewed(contract_env: ContractEnv) -> None:
    """종료된 계약은 다시 발급하거나 갱신할 수 없다.

    테스트 코드: LC-041, LC-050
    """
    # given: Won Deal의 종료 계약
    code = await contract_env.won_deal_without_contract()
    contract = await contract_env.seed_contract(code, status="ended")

    with raises_with(ContractTransitionError, NOT_ISSUED_ONLY):
        await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)
    # when: 발급과 갱신을 각각 시도한다
    with raises_with(ContractTransitionError, ISSUED_ONLY):
        await contract_env.renew.execute(contract.id, contract_env.issue_input(), KIM)
    # then: 발급은 미발급 전용, 갱신은 발급 상태 전용 오류다


async def test_ending_a_contract_allows_issuing_another_one_of_the_deal(
    contract_env: ContractEnv,
) -> None:
    """발급 계약을 종료하면 같은 Deal의 미발급 계약을 발급할 수 있다.

    테스트 코드: LC-042
    """
    # given: 발급(신규) 계약과 미발급 계약이 있는 Won Deal
    code = await contract_env.won_deal_without_contract()
    issued = await contract_env.seed_contract(code, status="issued_new")
    waiting = await contract_env.seed_contract(code)

    await contract_env.end.execute(issued.id, KIM)
    # when: 발급 계약을 종료한 뒤 미발급 계약을 발급한다
    await contract_env.issue.execute(waiting.id, contract_env.issue_input(), KIM)

    # then: 미발급 계약이 발급(신규)가 된다
    assert (await contract_env.stored(waiting.id)).status is ContractStatus.ISSUED_NEW


async def test_end_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    """없는 계약을 종료하면 404다.

    테스트 코드: LC-029
    """
    # when: 없는 계약 id로 종료한다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.end.execute(MISSING_ID, KIM)  # type: ignore[arg-type]
    # then: LicenseContractNotFoundError


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal", "ended"])
async def test_update_saves_the_contract_fields_in_every_status(
    contract_env: ContractEnv, status: str
) -> None:
    """계약 칸 수정은 모든 상태에서 저장되고 상태·시작일은 그대로다.

    테스트 코드: LC-031
    """
    # given: 미발급·발급(신규)·발급(갱신)·종료 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status=status, start=date(2026, 1, 1))

    # when: PARK가 기술담당·점검주기·Note를 수정한다
    await contract_env.update.execute(contract.id, NEW_FIELDS, PARK)

    stored = await contract_env.stored(contract.id)
    # then: 칸이 저장되고 상태·시작일은 그대로, 수정자는 PARK
    assert stored.fields == NEW_FIELDS
    assert stored.status is ContractStatus(status)
    assert stored.license_start == contract.license_start
    assert stored.updated_by == PARK.user_id


async def test_update_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    """없는 계약의 칸 수정은 404다.

    테스트 코드: LC-029
    """
    # when: 없는 계약 id로 수정한다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.update.execute(MISSING_ID, NEW_FIELDS, KIM)  # type: ignore[arg-type]
    # then: LicenseContractNotFoundError


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal", "ended"])
async def test_delete_by_admin_works_in_any_status(contract_env: ContractEnv, status: str) -> None:
    """admin은 어떤 상태의 계약이든 삭제할 수 있다.

    테스트 코드: LC-058
    """
    # given: 미발급·발급(신규)·발급(갱신)·종료 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status=status)

    # when: BOSS(admin)가 삭제한다
    await contract_env.delete.execute(contract.id, BOSS)

    # then: 그 Deal의 계약이 0건이다
    assert await contract_env.contracts_of(code) == []


@pytest.mark.parametrize("actor", [KIM, VIEWER])
async def test_delete_by_non_admin_is_forbidden_and_removes_nothing(
    contract_env: ContractEnv, actor: object
) -> None:
    """sales와 user는 계약을 삭제할 수 없고 계약·첨부는 그대로다.

    테스트 코드: LC-059
    """
    # given: 첨부 파일이 있는 종료 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status="ended")
    attachment = await contract_env.seed_file(contract)

    # when: KIM(sales) 또는 VIEWER(user)가 삭제한다
    with raises_with(ContractDeleteForbiddenError, DELETE_FORBIDDEN):
        await contract_env.delete.execute(contract.id, actor)  # type: ignore[arg-type]

    # then: ContractDeleteForbiddenError 문구, 계약과 첨부 내용 그대로
    assert len(await contract_env.contracts_of(code)) == 1
    assert contract_env.content_of(attachment) == b"hello"


@pytest.mark.parametrize("actor", [KIM, VIEWER])
async def test_delete_missing_contract_by_non_admin_is_forbidden_not_not_found(
    contract_env: ContractEnv, actor: object
) -> None:
    """없는 계약을 지우려 해도 admin이 아니면 404가 아니라 403이다.

    테스트 코드: LC-083, LC-029
    """
    # given: 존재하지 않는 계약 id, 요청자는 sales 또는 user
    # when: 그 id의 계약을 삭제한다
    with raises_with(ContractDeleteForbiddenError, DELETE_FORBIDDEN):
        await contract_env.delete.execute(MISSING_ID, actor)  # type: ignore[arg-type]
    # then: ContractDeleteForbiddenError(관리자만 문구)


async def test_delete_missing_contract_by_admin_is_not_found(contract_env: ContractEnv) -> None:
    """admin이 없는 계약을 지우면 404다.

    테스트 코드: LC-083, LC-029
    """
    # given: 존재하지 않는 계약 id
    # when: BOSS(admin)가 삭제한다
    with raises_with(LicenseContractNotFoundError, MISSING_CONTRACT):
        await contract_env.delete.execute(MISSING_ID, BOSS)  # type: ignore[arg-type]
    # then: LicenseContractNotFoundError 문구


async def test_delete_contract_by_admin_removes_files_after_commit(
    contract_env: ContractEnv,
) -> None:
    """admin 삭제는 첨부 행과 파일, 계약 폴더를 커밋 뒤 지운다.

    테스트 코드: LC-058
    """
    # given: 첨부 파일 2개가 있는 발급(신규) 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status="issued_new")
    first = await contract_env.seed_file(contract, name="a.pdf", data=b"one")
    second = await contract_env.seed_file(contract, name="b.pdf", data=b"two")

    # when: BOSS(admin)가 삭제한다
    await contract_env.delete.execute(contract.id, BOSS)

    # then: 첨부 행·파일이 없고 계약 폴더도 없다
    assert await contract_env.all_file_rows() == []
    assert contract_env.content_of(first) is None
    assert contract_env.content_of(second) is None
    assert not contract_env.contract_folder_exists(contract.id)  # 폴더째 지워진다(AC33)


async def test_delete_contract_keeps_other_contracts_and_the_deal_files(
    contract_env: ContractEnv,
) -> None:
    """삭제는 같은 Deal의 다른 계약과 Deal 첨부를 건드리지 않는다.

    테스트 코드: LC-058
    """
    # given: 첨부가 있는 계약 C1·C2와 Deal 첨부 파일
    code = await contract_env.open_deal()
    target = await contract_env.seed_contract(code, status="ended")
    sibling = await contract_env.seed_contract(code)
    gone = await contract_env.seed_file(target, name="gone.pdf")
    kept = await contract_env.seed_file(sibling, name="kept.pdf", data=b"sibling")
    deal_file = await contract_env.seed_deal_file(code)

    # when: BOSS(admin)가 C1을 삭제한다
    await contract_env.delete.execute(target.id, BOSS)

    # then: C1 파일·폴더만 사라지고 C2와 Deal 첨부는 그대로다
    assert [c.id for c in await contract_env.contracts_of(code)] == [sibling.id]
    assert contract_env.content_of(gone) is None
    assert not contract_env.contract_folder_exists(target.id)
    assert contract_env.content_of(kept) == b"sibling"  # 다른 계약 폴더는 그대로
    assert contract_env.contract_folder_exists(sibling.id)
    assert contract_env.content_of(deal_file) == b"deal"  # Deal 첨부(Deal 폴더)도 그대로


async def test_delete_contract_survives_a_file_cleanup_failure(contract_env: ContractEnv) -> None:
    """폴더 삭제가 실패해도 계약 삭제는 성공한다.

    테스트 코드: LC-062
    """
    # given: 첨부가 있는 계약과 폴더 삭제가 실패하는 저장소
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    await contract_env.seed_file(contract)
    contract_env.storage.fail_deletes = True

    # when: BOSS(admin)가 삭제한다
    await contract_env.delete.execute(contract.id, BOSS)  # DB가 정본이다

    # then: 계약이 0건이다
    assert await contract_env.contracts_of(code) == []


async def test_delete_contract_without_storage_settings_still_removes_the_rows(
    contract_env: ContractEnv,
) -> None:
    """저장 위치 설정이 없어도 계약·첨부 행은 지워지고 파일은 둔다.

    테스트 코드: LC-062
    """
    # given: 첨부가 있는 계약과 저장 위치 설정 없음
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    attachment = await contract_env.seed_file(contract)
    await contract_env.remove_storage_settings()

    # when: BOSS(admin)가 삭제한다
    await contract_env.delete.execute(contract.id, BOSS)

    # then: 첨부 행은 없고 디스크 파일은 그대로다
    assert await contract_env.all_file_rows() == []
    assert contract_env.content_of(attachment) == b"hello"  # 위치를 몰라 파일은 둔다


async def test_deleting_the_renewed_row_clears_the_link_of_its_successor(
    contract_env: ContractEnv,
) -> None:
    """갱신 원본을 지우면 후속 계약의 원본 연결이 비워진다.

    테스트 코드: LC-060
    """
    # given: 발급(신규) 계약 P를 갱신해 생긴 계약 N
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(code, status="issued_new")
    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)

    # when: BOSS(admin)가 P를 삭제한다
    await contract_env.delete.execute(previous.id, BOSS)

    (renewal,) = await contract_env.contracts_of(code)
    # then: N은 남고 renewed_from_id가 None이다
    assert renewal.renewed_from_id is None
