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
    """인라인 변경으로 삭제를 골라 Won을 벗어나면 그 Deal의 계약과 계약 폴더만 지워진다.

    테스트 코드: LC-006
    """
    # given: 계약 2건(첨부 포함)과 Deal 첨부가 있는 Won Deal
    code, _, deal_file = await _won_with_files(contract_env)
    contract_ids = [c.id for c in await contract_env.contracts_of(code)]
    assert len(contract_ids) == 2
    assert all(contract_env.contract_folder_exists(i) for i in contract_ids)

    # when: delete_license_contracts=true로 Forecast를 commit으로 바꾼다
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    # then: 계약·첨부 행과 계약 폴더가 없고 Deal 첨부는 남으며 Forecast는 commit이다
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
    """Deal 폼 수정으로 삭제를 골라 Won을 벗어나면 계약이 지워진다.

    테스트 코드: LC-006
    """
    # given: 계약 2건(첨부 포함)과 Deal 첨부가 있는 Won Deal
    code, _, _ = await _won_with_files(contract_env)

    # when: delete_license_contracts=true로 폼 수정한다
    await contract_env.leave_won_by_form(code, KIM, delete_contracts=True)

    # then: 계약·첨부 행이 없고 Deal 첨부 파일만 남는다
    assert await contract_env.contracts_of(code) == []
    assert await contract_env.all_file_rows() == []
    assert contract_env.storage.file_count() == 1


async def test_register_action_leave_won_with_delete_removes_contracts(
    contract_env: ContractEnv,
) -> None:
    """Action 등록으로 삭제를 골라 Won을 벗어나면 계약이 지워진다.

    테스트 코드: LC-006
    """
    # given: 계약 2건(첨부 포함)과 Deal 첨부가 있는 Won Deal
    code, _, _ = await _won_with_files(contract_env)

    # when: delete_license_contracts=true로 Action을 등록한다
    await contract_env.leave_won_by_action(code, KIM, delete_contracts=True)

    # then: 계약·첨부 행이 없고 Deal 첨부 파일만 남는다
    assert await contract_env.contracts_of(code) == []
    assert await contract_env.all_file_rows() == []
    assert contract_env.storage.file_count() == 1


@pytest.mark.parametrize("flag", [None, False])
@pytest.mark.parametrize("path", ["change", "form", "action"])
async def test_leave_won_without_the_flag_keeps_contracts_and_files(
    contract_env: ContractEnv, path: str, flag: bool | None
) -> None:
    """삭제를 고르지 않았거나 false면 세 경로 모두 계약과 파일이 그대로다.

    테스트 코드: LC-007
    """
    # given: 계약 2건(첨부 포함)이 있는 Won Deal
    code, contents, _ = await _won_with_files(contract_env)
    leave = {
        "change": contract_env.leave_won_by_change,
        "form": contract_env.leave_won_by_form,
        "action": contract_env.leave_won_by_action,
    }[path]

    # when: 플래그 없이(또는 false로) Won을 벗어난다
    await leave(code, KIM, delete_contracts=flag)

    # then: Forecast는 commit이지만 계약·첨부 행·파일은 그대로다
    assert len(await contract_env.contracts_of(code)) == 2
    assert len(await contract_env.all_file_rows()) == 2
    assert contract_env.storage.file_count() == 3
    assert await contract_env.forecast_of(code) == "commit"
    assert contents == [b"first", b"second"]


async def test_update_deal_leave_won_without_flag_keeps_contracts(
    contract_env: ContractEnv,
) -> None:
    """삭제 값을 생략한 폼 수정은 계약을 남긴다.

    테스트 코드: LC-007
    """
    # given: 계약 1건이 있는 Won Deal
    code = await contract_env.won_deal(KIM)

    # when: 플래그 없이 폼 수정으로 Won을 벗어난다
    await contract_env.leave_won_by_form(code, KIM)

    # then: 계약은 1건 그대로다
    assert len(await contract_env.contracts_of(code)) == 1


async def test_delete_flag_ignored_when_not_leaving_won(contract_env: ContractEnv) -> None:
    """Won이 아닌 Deal에서는 삭제 값을 보내도 무시된다.

    테스트 코드: LC-007
    """
    # given: 계약과 첨부가 남은 Won이 아닌 Deal
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status="ended")  # Won 아닌 Deal에 남은 계약
    await contract_env.seed_file(contract)
    change = DealChangeInput(field="forecast_key", value="commit", delete_license_contracts=True)

    # when: delete_license_contracts=true로 Won이 아닌 상태로 바꾼다
    await contract_env.env.apply.execute(code, change, KIM)  # 오류 없음

    # then: 오류 없이 계약·첨부 행·파일이 그대로다
    assert [c.id for c in await contract_env.contracts_of(code)] == [contract.id]
    assert len(await contract_env.all_file_rows()) == 1
    assert contract_env.storage.file_count() == 1


async def test_delete_flag_ignored_when_the_deal_stays_won(contract_env: ContractEnv) -> None:
    """Won을 유지하는 변경은 삭제 값을 무시한다.

    테스트 코드: LC-007
    """
    # given: 계약 1건이 있는 Won Deal
    code = await contract_env.won_deal(KIM)
    change = DealChangeInput(
        field="revenue_amount", value=123_000_000, delete_license_contracts=True
    )

    # when: delete_license_contracts=true로 금액만 바꾼다
    await contract_env.env.apply.execute(code, change, KIM)

    # then: 계약은 1건 그대로다
    assert len(await contract_env.contracts_of(code)) == 1


async def test_delete_flag_ignored_when_entering_won(contract_env: ContractEnv) -> None:
    """Won으로 진입하는 변경은 삭제 값을 무시하고 진입 규칙대로 계약을 만든다.

    테스트 코드: LC-007
    """
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()
    change = DealChangeInput(
        field="forecast_key", value="won", resolution=CLOSING, delete_license_contracts=True
    )

    # when: delete_license_contracts=true로 Won으로 바꾼다
    await contract_env.env.apply.execute(code, change, KIM)

    # then: 미발급 계약 1건이 자동 생성된다
    assert len(await contract_env.contracts_of(code)) == 1  # 진입 규칙대로 자동 생성된다


async def test_leave_won_with_delete_succeeds_when_the_deal_has_no_contract(
    contract_env: ContractEnv,
) -> None:
    """계약이 없는 Won Deal도 삭제를 골라 Won을 벗어날 수 있다."""
    # given: 계약을 모두 지운 Won Deal
    code = await contract_env.won_deal(KIM)
    for contract in await contract_env.contracts_of(code):
        await contract_env.uow.license_contracts.delete(contract.id)

    # when: delete_license_contracts=true로 Won을 벗어난다
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    # then: 요청은 성공하고 Forecast는 commit, 계약은 0건이다
    assert await contract_env.contracts_of(code) == []
    assert await contract_env.forecast_of(code) == "commit"


async def test_leave_won_with_delete_removes_only_this_deals_contracts(
    contract_env: ContractEnv,
) -> None:
    """삭제를 고른 Won 이탈은 다른 Deal의 계약을 건드리지 않는다.

    테스트 코드: LC-006
    """
    # given: 계약이 있는 Won Deal A와 B
    code = await contract_env.won_deal(KIM)
    other = await contract_env.won_deal(KIM)

    # when: A를 delete_license_contracts=true로 Won 밖으로 바꾼다
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    # then: A의 계약은 0건이고 B의 계약은 1건 그대로다
    assert await contract_env.contracts_of(code) == []
    assert len(await contract_env.contracts_of(other)) == 1


async def test_rejected_change_with_delete_flag_keeps_contracts_and_files(
    contract_env: ContractEnv,
) -> None:
    """거절된 Won 이탈 변경은 계약과 파일을 지우지 않는다."""
    # given: 계약 2건(첨부 포함)이 있는 Won Deal
    code, _, _ = await _won_with_files(contract_env)
    change = DealChangeInput(
        field="forecast_key", value="commit", delete_license_contracts=True
    )  # 함께 바꿀 Status 선택이 없어 거절된다

    # when: Status 선택 없이 delete_license_contracts=true로 Forecast를 바꾼다
    with pytest.raises(InvalidValueError):
        await contract_env.env.apply.execute(code, change, KIM)

    # then: InvalidValueError, 계약·행·파일 그대로, Forecast는 won
    assert len(await contract_env.contracts_of(code)) == 2
    assert len(await contract_env.all_file_rows()) == 2
    assert contract_env.storage.file_count() == 3
    assert await contract_env.forecast_of(code) == "won"


async def test_leave_won_with_delete_succeeds_without_storage_settings(
    contract_env: ContractEnv,
) -> None:
    """저장 위치 설정이 없어도 계약 삭제 Won 이탈은 성공하고 파일은 둔다.

    테스트 코드: LC-062
    """
    # given: 계약 2건(첨부 포함)과 저장 위치 설정 없음
    code, _, _ = await _won_with_files(contract_env)
    await contract_env.remove_storage_settings()

    # when: delete_license_contracts=true로 Won을 벗어난다
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    # then: 계약·행은 지워지고 디스크 파일 3개는 그대로다
    assert await contract_env.contracts_of(code) == []
    assert await contract_env.all_file_rows() == []
    assert contract_env.storage.file_count() == 3  # 저장 위치를 몰라 파일은 그대로 둔다


async def test_leave_won_with_delete_survives_a_file_cleanup_failure(
    contract_env: ContractEnv,
) -> None:
    """폴더 삭제가 실패해도 계약 삭제 Won 이탈 요청은 성공한다.

    테스트 코드: LC-062
    """
    # given: 계약 2건(첨부 포함)과 폴더 삭제가 실패하는 저장소
    code, _, _ = await _won_with_files(contract_env)
    contract_env.storage.fail_deletes = True

    # when: delete_license_contracts=true로 Won을 벗어난다
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)  # DB가 정본이다

    # then: 계약은 0건이고 Forecast는 commit이다
    assert await contract_env.contracts_of(code) == []
    assert await contract_env.forecast_of(code) == "commit"
