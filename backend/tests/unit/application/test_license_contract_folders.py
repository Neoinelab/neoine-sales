"""계약 첨부의 저장 폴더와 정리(AC32~AC35).

계약 첨부는 `<저장 위치>/license-contracts/<계약 id>/<key>`에 저장되고 Deal 첨부는 계속
`<저장 위치>/<deal_code>/<key>`다. 계약 삭제 세 경로(admin 삭제, Won 이탈 삭제, Deal 삭제)는 커밋 뒤
그 계약 폴더를 통째로 지운다. 첨부 하나를 지울 때는 파일만 지우고 폴더는 남긴다.
"""

import logging
from typing import TYPE_CHECKING

import pytest

from app.application.license_contract.delete_license_contract import DeleteLicenseContract
from app.domain.license_contract.errors import LicenseContractNotFoundError
from tests.fakes.commit_failure import COMMIT_FAILED, commit_failing_factory
from tests.fakes.file_storage import BytesSource, contract_location, deal_location
from tests.support.expect import raises_with
from tests.unit.application.license_contract_env import BOSS, KIM, ROOT_PATH

if TYPE_CHECKING:
    from app.domain.license_contract.entities import LicenseContract
    from tests.unit.application.license_contract_env import ContractEnv


def _folder(contract: LicenseContract) -> str:
    return f"{ROOT_PATH}/license-contracts/{int(contract.id)}"


async def _contract(contract_env: ContractEnv) -> LicenseContract:
    code = await contract_env.open_deal()
    return await contract_env.seed_contract(code)


# ---- 저장 위치 (AC32) ----


async def test_upload_saves_the_file_under_the_contract_folder(contract_env: ContractEnv) -> None:
    """계약 첨부는 `<저장 위치>/license-contracts/<계약 id>/<key>`에 저장된다.

    테스트 코드: LC-063
    """
    # given: 미발급 계약
    contract = await _contract(contract_env)

    # when: KIM이 a.pdf를 올린다
    outcome = await contract_env.put_file(contract.id, KIM, "a.pdf", b"content")

    key = outcome.attachment.storage_key
    stored = contract_env.storage.contents_of(
        contract_env.root, contract_location(contract.id, key)
    )
    # then: 계약 폴더 위치에서 내용을 읽을 수 있고 폴더에 그 키 하나뿐이다
    assert stored == b"content"
    assert contract_env.storage.entries(_folder(contract)) == [key]


async def test_upload_does_not_create_the_deal_folder(contract_env: ContractEnv) -> None:
    """계약 첨부 업로드는 Deal 폴더를 만들지 않는다.

    테스트 코드: LC-063
    """
    # given: 미발급 계약
    contract = await _contract(contract_env)

    # when: 첨부를 올린다
    await contract_env.put_file(contract.id, KIM)

    # then: Deal 폴더가 없고 저장 위치 아래에는 license-contracts뿐이다
    assert not contract_env.deal_folder_exists(contract.deal_code.value)
    assert contract_env.storage.entries(ROOT_PATH) == ["license-contracts"]


async def test_each_contract_has_its_own_folder(contract_env: ContractEnv) -> None:
    """계약마다 자기 id 폴더를 쓴다."""
    # given: 같은 Deal의 계약 둘
    code = await contract_env.open_deal()
    first = await contract_env.seed_contract(code, status="ended")
    second = await contract_env.seed_contract(code)

    await contract_env.put_file(first.id, KIM, "a.pdf", b"one")
    # when: 각 계약에 a.pdf를 올린다
    await contract_env.put_file(second.id, KIM, "a.pdf", b"two")

    # then: 폴더가 서로 다르고 각 폴더에 파일 1개씩이다
    assert len(contract_env.storage.entries(_folder(first))) == 1
    assert len(contract_env.storage.entries(_folder(second))) == 1
    assert _folder(first) != _folder(second)


async def test_deal_attachments_keep_the_deal_folder(contract_env: ContractEnv) -> None:
    """Deal 첨부는 계속 Deal 폴더에 있고 계약 첨부와 섞이지 않는다.

    테스트 코드: LC-063
    """
    # given: Deal 첨부가 있는 Deal과 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    deal_file = await contract_env.seed_deal_file(code)
    # when: 계약에 첨부를 올린다
    await contract_env.put_file(contract.id, KIM)

    stored = contract_env.storage.contents_of(
        contract_env.root, deal_location(deal_file.deal_code, deal_file.storage_key)
    )
    # then: Deal 첨부는 Deal 폴더에 그대로고 그 폴더에는 그 키뿐이다
    assert stored == b"deal"
    assert contract_env.storage.entries(f"{ROOT_PATH}/{code}") == [deal_file.storage_key]


async def test_renewal_uses_a_new_folder_and_the_previous_files_stay(
    contract_env: ContractEnv,
) -> None:
    """갱신으로 생긴 새 계약은 새 폴더를 쓰고 이전 파일은 이전 폴더에 남는다.

    테스트 코드: LC-052
    """
    # given: 첨부 old.pdf가 있는 발급(신규) 계약 P
    code = await contract_env.won_deal_without_contract(KIM)
    previous = await contract_env.seed_contract(code, status="issued_new")
    old_file = (await contract_env.put_file(previous.id, KIM, "old.pdf", b"old")).attachment
    from datetime import date  # noqa: PLC0415

    # when: P를 갱신하고 새 계약 N에 new.pdf를 올린다
    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)
    (renewal,) = [c for c in await contract_env.contracts_of(code) if c.id != previous.id]

    new_file = (await contract_env.put_file(renewal.id, KIM, "new.pdf", b"new")).attachment

    # then: P·N의 파일과 폴더 목록이 각각 하나씩 그대로다
    assert contract_env.content_of(old_file) == b"old"
    assert contract_env.content_of(new_file) == b"new"
    assert contract_env.storage.entries(_folder(previous)) == [old_file.storage_key]
    assert contract_env.storage.entries(_folder(renewal)) == [new_file.storage_key]


async def test_download_reads_from_the_contract_folder(contract_env: ContractEnv) -> None:
    """다운로드는 계약 폴더에서 읽는다.

    테스트 코드: LC-074
    """
    # given: payload를 올린 계약 첨부
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"payload")).attachment

    # when: 다운로드한다
    _, opened = await contract_env.download.execute(attachment.id)

    # then: 올린 바이트가 그대로 온다
    assert b"".join([chunk async for chunk in opened.chunks]) == b"payload"


async def test_download_does_not_fall_back_to_the_deal_folder(contract_env: ContractEnv) -> None:
    """계약 폴더에 파일이 없으면 Deal 폴더의 같은 키 파일을 대신 주지 않는다.

    테스트 코드: LC-075
    """
    # given: 계약 폴더의 파일을 지우고 Deal 폴더에만 같은 키 파일이 있다
    from app.domain.attachment.errors import AttachmentContentMissingError  # noqa: PLC0415

    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"payload")).attachment
    await contract_env.storage.delete(
        contract_env.root, contract_location(contract.id, attachment.storage_key)
    )
    await contract_env.storage.save(  # 옛 위치(<deal_code>/<key>)에만 같은 키의 파일이 있다
        contract_env.root,
        deal_location(contract.deal_code, attachment.storage_key),
        BytesSource(b"old"),
        max_bytes=10,
    )

    # when: 다운로드한다
    with pytest.raises(AttachmentContentMissingError):
        await contract_env.download.execute(attachment.id)
    # then: AttachmentContentMissingError


async def test_replace_swaps_the_file_inside_the_same_contract_folder(
    contract_env: ContractEnv,
) -> None:
    """교체는 같은 계약 폴더 안에서 파일만 바꾼다.

    테스트 코드: LC-066
    """
    # given: a.pdf(old)가 올라간 계약
    from app.domain.attachment.values import OnExists  # noqa: PLC0415

    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    # when: a.pdf(new)를 replace로 올린다
    replaced = (
        await contract_env.put_file(contract.id, KIM, "a.pdf", b"new", on_exists=OnExists.REPLACE)
    ).attachment

    # then: 폴더에는 새 키뿐이고 키가 바뀌었다
    assert contract_env.storage.entries(_folder(contract)) == [replaced.storage_key]
    assert replaced.storage_key != first.storage_key


# ---- 첨부 하나 삭제 (AC34) ----


async def test_delete_file_removes_only_the_file_and_keeps_the_contract_folder(
    contract_env: ContractEnv,
) -> None:
    """첨부 하나를 지우면 그 파일만 지워지고 계약 폴더는 남는다.

    테스트 코드: LC-076
    """
    # given: a.pdf·b.pdf가 있는 계약
    contract = await _contract(contract_env)
    doomed = (await contract_env.put_file(contract.id, KIM, "a.pdf")).attachment
    kept = (await contract_env.put_file(contract.id, KIM, "b.pdf", b"kept")).attachment

    # when: a.pdf를 지운다
    await contract_env.delete_file.execute(doomed.id, KIM)

    # then: a.pdf만 없고 b.pdf와 폴더는 그대로다
    assert contract_env.content_of(doomed) is None
    assert contract_env.content_of(kept) == b"kept"
    assert contract_env.contract_folder_exists(contract.id)


async def test_deleting_the_last_file_keeps_the_empty_contract_folder(
    contract_env: ContractEnv,
) -> None:
    """마지막 첨부를 지워도 빈 계약 폴더는 남는다.

    테스트 코드: LC-076
    """
    # given: 첨부 1개만 있는 계약
    contract = await _contract(contract_env)
    only = (await contract_env.put_file(contract.id, KIM)).attachment

    # when: 그 첨부를 지운다
    await contract_env.delete_file.execute(only.id, KIM)

    # then: 계약 폴더는 있고 비어 있다
    assert contract_env.contract_folder_exists(contract.id)
    assert contract_env.storage.entries(_folder(contract)) == []


# ---- admin 계약 삭제 (AC33) ----


async def test_admin_delete_removes_the_contract_folder_after_commit(
    contract_env: ContractEnv,
) -> None:
    """admin 삭제는 커밋 뒤 계약 폴더를 통째로 지운다.

    테스트 코드: LC-058
    """
    # given: 첨부 2개가 있는 계약
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM, "a.pdf")
    await contract_env.put_file(contract.id, KIM, "b.pdf")

    # when: BOSS(admin)가 계약을 삭제한다
    await contract_env.delete.execute(contract.id, BOSS)

    # then: 계약 폴더와 파일이 없다
    assert not contract_env.contract_folder_exists(contract.id)
    assert contract_env.storage.file_count() == 0


async def test_admin_delete_with_a_failed_commit_keeps_the_folder(
    contract_env: ContractEnv,
) -> None:
    """커밋이 실패하면 폴더를 지우지 않는다.

    테스트 코드: LC-062
    """
    # given: 첨부가 있는 계약과 커밋이 실패하는 UoW
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment
    broken = DeleteLicenseContract(commit_failing_factory(contract_env.uow), contract_env.storage)

    # when: admin이 삭제한다
    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(contract.id, BOSS)

    # then: RuntimeError, 파일과 계약이 그대로다
    assert contract_env.content_of(attachment) == b"hello"
    assert len(await contract_env.contracts_of(contract.deal_code.value)) == 1


async def test_admin_delete_by_a_forbidden_actor_keeps_the_folder(
    contract_env: ContractEnv,
) -> None:
    """권한 거절로 끝난 삭제는 폴더를 지우지 않는다.

    테스트 코드: LC-062, LC-059
    """
    # given: 첨부가 있는 계약
    from app.domain.license_contract.errors import ContractDeleteForbiddenError  # noqa: PLC0415

    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM)

    # when: KIM(sales)이 삭제한다
    with pytest.raises(ContractDeleteForbiddenError):
        await contract_env.delete.execute(contract.id, KIM)

    # then: ContractDeleteForbiddenError, 계약 폴더 그대로
    assert contract_env.contract_folder_exists(contract.id)


async def test_admin_delete_without_storage_settings_leaves_the_folder(
    contract_env: ContractEnv,
) -> None:
    """저장 위치 설정이 없으면 계약은 지우고 폴더는 건드리지 않는다.

    테스트 코드: LC-062
    """
    # given: 첨부가 있는 계약과 저장 위치 설정 없음
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM)
    await contract_env.remove_storage_settings()

    # when: admin이 삭제한다
    await contract_env.delete.execute(contract.id, BOSS)

    # then: 계약은 없고 폴더는 남는다
    assert await contract_env.contracts_of(contract.deal_code.value) == []
    assert contract_env.contract_folder_exists(contract.id)  # 위치를 몰라 건드리지 않는다


async def test_admin_delete_survives_a_folder_cleanup_failure_and_logs_a_warning(
    contract_env: ContractEnv, caplog: pytest.LogCaptureFixture
) -> None:
    """폴더 삭제가 실패해도 삭제는 성공하고 경고 로그가 남는다.

    테스트 코드: LC-062
    """
    # given: 첨부가 있는 계약과 폴더 삭제가 실패하는 저장소
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM)
    contract_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    # when: admin이 삭제한다
    await contract_env.delete.execute(contract.id, BOSS)

    # then: 계약은 없고 WARNING 로그가 있다
    assert await contract_env.contracts_of(contract.deal_code.value) == []
    assert [r for r in caplog.records if r.levelno == logging.WARNING]


# ---- Won 이탈 삭제 (AC33) ----


async def test_won_exit_delete_removes_every_contract_folder_of_the_deal_only(
    contract_env: ContractEnv,
) -> None:
    """Won 이탈 삭제는 그 Deal의 모든 계약 폴더만 지운다.

    테스트 코드: LC-006
    """
    # given: 계약 둘(각 첨부)과 Deal 첨부, 다른 Deal의 계약 첨부
    code = await contract_env.won_deal_without_contract(KIM)
    first = await contract_env.seed_contract(code)
    second = await contract_env.seed_contract(code, status="ended")
    other_code = await contract_env.won_deal_without_contract(KIM)
    outsider = await contract_env.seed_contract(other_code)
    await contract_env.put_file(first.id, KIM, "a.pdf")
    await contract_env.put_file(second.id, KIM, "b.pdf")
    outsider_file = (await contract_env.put_file(outsider.id, KIM, "c.pdf", b"mine")).attachment
    deal_file = await contract_env.seed_deal_file(code)

    # when: delete_license_contracts=true로 Won을 벗어난다
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    # then: 두 계약 폴더는 없고 다른 Deal의 파일과 Deal 첨부는 그대로다
    assert not contract_env.contract_folder_exists(first.id)
    assert not contract_env.contract_folder_exists(second.id)
    assert contract_env.content_of(outsider_file) == b"mine"
    assert contract_env.content_of(deal_file) == b"deal"


async def test_won_exit_keep_leaves_the_folders(contract_env: ContractEnv) -> None:
    """유지를 고르면 계약 폴더가 남는다.

    테스트 코드: LC-007
    """
    # given: 첨부가 있는 계약
    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)

    # when: delete_license_contracts=false로 Won을 벗어난다
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=False)

    # then: 계약 폴더가 그대로다
    assert contract_env.contract_folder_exists(contract.id)


async def test_won_exit_delete_without_storage_settings_leaves_the_folders(
    contract_env: ContractEnv,
) -> None:
    """저장 위치 설정이 없으면 Won 이탈 삭제도 폴더를 건드리지 않는다.

    테스트 코드: LC-062
    """
    # given: 첨부가 있는 계약과 저장 위치 설정 없음
    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)
    await contract_env.remove_storage_settings()

    # when: 삭제를 골라 Won을 벗어난다
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    # then: 계약은 없고 폴더는 남는다
    assert await contract_env.contracts_of(code) == []
    assert contract_env.contract_folder_exists(contract.id)


async def test_won_exit_delete_survives_a_folder_cleanup_failure_and_logs_a_warning(
    contract_env: ContractEnv, caplog: pytest.LogCaptureFixture
) -> None:
    """폴더 삭제 실패에도 Won 이탈 삭제는 성공하고 경고 로그가 남는다.

    테스트 코드: LC-062
    """
    # given: 첨부가 있는 계약과 폴더 삭제가 실패하는 저장소
    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)
    contract_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    # when: 폼 수정으로 삭제를 골라 Won을 벗어난다
    await contract_env.leave_won_by_form(code, KIM, delete_contracts=True)

    # then: Forecast는 commit이고 WARNING 로그가 있다
    assert await contract_env.forecast_of(code) == "commit"
    assert [r for r in caplog.records if r.levelno == logging.WARNING]


# ---- Deal 삭제 (AC33) ----


async def test_deleting_a_deal_removes_the_deal_folder_and_its_contract_folders(
    contract_env: ContractEnv,
) -> None:
    """Deal 삭제는 Deal 폴더와 그 Deal의 모든 계약 폴더를 지운다.

    테스트 코드: LC-080
    """
    # given: 계약 둘(각 첨부)과 Deal 첨부, 다른 Deal의 계약 첨부·Deal 첨부
    from app.application.deal.delete_deal import DeleteDeal  # noqa: PLC0415

    code = await contract_env.won_deal_without_contract(KIM)
    first = await contract_env.seed_contract(code)
    second = await contract_env.seed_contract(code, status="ended")
    await contract_env.put_file(first.id, KIM)
    await contract_env.put_file(second.id, KIM, "b.pdf")
    await contract_env.seed_deal_file(code)
    other = await contract_env.won_deal_without_contract(KIM)
    outsider = await contract_env.seed_contract(other)
    outsider_file = (await contract_env.put_file(outsider.id, KIM, "o.pdf", b"o")).attachment
    other_deal_file = await contract_env.seed_deal_file(other, name="o-deal.pdf")

    delete_deal = DeleteDeal(contract_env.uow_factory, contract_env.clock, contract_env.storage)
    # when: BOSS(admin)가 Deal을 삭제한다
    await delete_deal.execute(code, code, BOSS)

    # then: Deal 폴더와 계약 폴더 둘이 없고 다른 Deal의 파일은 그대로다
    assert not contract_env.deal_folder_exists(code)
    assert not contract_env.contract_folder_exists(first.id)
    assert not contract_env.contract_folder_exists(second.id)
    assert contract_env.content_of(outsider_file) == b"o"
    assert contract_env.content_of(other_deal_file) == b"deal"


async def test_deleting_a_deal_without_storage_settings_leaves_the_files(
    contract_env: ContractEnv,
) -> None:
    """저장 위치 설정이 없으면 Deal 삭제도 파일을 건드리지 않는다.

    테스트 코드: LC-062
    """
    # given: 첨부가 있는 계약과 저장 위치 설정 없음
    from app.application.deal.delete_deal import DeleteDeal  # noqa: PLC0415

    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)
    await contract_env.remove_storage_settings()

    # when: admin이 Deal을 삭제한다
    await DeleteDeal(contract_env.uow_factory, contract_env.clock, contract_env.storage).execute(
        code, code, BOSS
    )

    # then: 계약 폴더가 그대로다
    assert contract_env.contract_folder_exists(contract.id)


async def test_deleting_a_deal_survives_a_cleanup_failure_and_logs_a_warning(
    contract_env: ContractEnv, caplog: pytest.LogCaptureFixture
) -> None:
    """폴더 삭제 실패에도 Deal 삭제는 성공하고 경고 로그가 남는다.

    테스트 코드: LC-062
    """
    # given: 첨부가 있는 계약과 폴더 삭제가 실패하는 저장소
    from app.application.deal.delete_deal import DeleteDeal  # noqa: PLC0415
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)
    contract_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    # when: admin이 Deal을 삭제한다
    await DeleteDeal(contract_env.uow_factory, contract_env.clock, contract_env.storage).execute(
        code, code, BOSS
    )

    # then: Deal은 없고 WARNING 로그가 있다
    assert DealCode(code) not in contract_env.uow.deals._items
    assert [r for r in caplog.records if r.levelno == logging.WARNING]


# ---- 업로드 도중 계약 삭제 (AC35, 순차 재현) ----


async def test_upload_when_the_contract_is_deleted_before_recording_removes_its_folder(
    contract_env: ContractEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    """업로드 도중 계약이 지워지면 404로 끝나고 계약 폴더가 남지 않는다.

    테스트 코드: LC-069
    """
    # given: 파일 저장 직후 계약이 사라지도록 저장소를 바꾼 상태
    contract = await _contract(contract_env)
    storage = contract_env.storage
    real_save = storage.save

    async def save_then_lose_the_contract(*args: object, **kwargs: object) -> int:
        written = await real_save(*args, **kwargs)  # type: ignore[arg-type]
        await contract_env.uow.license_contracts.delete(
            contract.id
        )  # 파일을 쓴 직후 계약이 사라진다
        return written

    monkeypatch.setattr(storage, "save", save_then_lose_the_contract)

    # when: 첨부를 올린다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.put_file(contract.id, KIM)

    # then: LicenseContractNotFoundError, 계약 폴더와 파일이 없다
    assert not contract_env.contract_folder_exists(
        contract.id
    )  # 새로 쓴 파일과 빈 폴더가 남지 않는다
    assert storage.file_count() == 0
