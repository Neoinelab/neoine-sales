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
    contract = await _contract(contract_env)

    outcome = await contract_env.put_file(contract.id, KIM, "a.pdf", b"content")

    key = outcome.attachment.storage_key
    stored = contract_env.storage.contents_of(
        contract_env.root, contract_location(contract.id, key)
    )
    assert stored == b"content"
    assert contract_env.storage.entries(_folder(contract)) == [key]


async def test_upload_does_not_create_the_deal_folder(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)

    await contract_env.put_file(contract.id, KIM)

    assert not contract_env.deal_folder_exists(contract.deal_code.value)
    assert contract_env.storage.entries(ROOT_PATH) == ["license-contracts"]


async def test_each_contract_has_its_own_folder(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    first = await contract_env.seed_contract(code, status="ended")
    second = await contract_env.seed_contract(code)

    await contract_env.put_file(first.id, KIM, "a.pdf", b"one")
    await contract_env.put_file(second.id, KIM, "a.pdf", b"two")

    assert len(contract_env.storage.entries(_folder(first))) == 1
    assert len(contract_env.storage.entries(_folder(second))) == 1
    assert _folder(first) != _folder(second)


async def test_deal_attachments_keep_the_deal_folder(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    deal_file = await contract_env.seed_deal_file(code)
    await contract_env.put_file(contract.id, KIM)

    stored = contract_env.storage.contents_of(
        contract_env.root, deal_location(deal_file.deal_code, deal_file.storage_key)
    )
    assert stored == b"deal"
    assert contract_env.storage.entries(f"{ROOT_PATH}/{code}") == [deal_file.storage_key]


async def test_renewal_uses_a_new_folder_and_the_previous_files_stay(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    previous = await contract_env.seed_contract(code, status="issued_new")
    old_file = (await contract_env.put_file(previous.id, KIM, "old.pdf", b"old")).attachment
    from datetime import date  # noqa: PLC0415

    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)
    (renewal,) = [c for c in await contract_env.contracts_of(code) if c.id != previous.id]

    new_file = (await contract_env.put_file(renewal.id, KIM, "new.pdf", b"new")).attachment

    assert contract_env.content_of(old_file) == b"old"
    assert contract_env.content_of(new_file) == b"new"
    assert contract_env.storage.entries(_folder(previous)) == [old_file.storage_key]
    assert contract_env.storage.entries(_folder(renewal)) == [new_file.storage_key]


async def test_download_reads_from_the_contract_folder(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"payload")).attachment

    _, opened = await contract_env.download.execute(attachment.id)

    assert b"".join([chunk async for chunk in opened.chunks]) == b"payload"


async def test_download_does_not_fall_back_to_the_deal_folder(contract_env: ContractEnv) -> None:
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

    with pytest.raises(AttachmentContentMissingError):
        await contract_env.download.execute(attachment.id)


async def test_replace_swaps_the_file_inside_the_same_contract_folder(
    contract_env: ContractEnv,
) -> None:
    from app.domain.attachment.values import OnExists  # noqa: PLC0415

    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    replaced = (
        await contract_env.put_file(contract.id, KIM, "a.pdf", b"new", on_exists=OnExists.REPLACE)
    ).attachment

    assert contract_env.storage.entries(_folder(contract)) == [replaced.storage_key]
    assert replaced.storage_key != first.storage_key


# ---- 첨부 하나 삭제 (AC34) ----


async def test_delete_file_removes_only_the_file_and_keeps_the_contract_folder(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    doomed = (await contract_env.put_file(contract.id, KIM, "a.pdf")).attachment
    kept = (await contract_env.put_file(contract.id, KIM, "b.pdf", b"kept")).attachment

    await contract_env.delete_file.execute(doomed.id, KIM)

    assert contract_env.content_of(doomed) is None
    assert contract_env.content_of(kept) == b"kept"
    assert contract_env.contract_folder_exists(contract.id)


async def test_deleting_the_last_file_keeps_the_empty_contract_folder(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    only = (await contract_env.put_file(contract.id, KIM)).attachment

    await contract_env.delete_file.execute(only.id, KIM)

    assert contract_env.contract_folder_exists(contract.id)
    assert contract_env.storage.entries(_folder(contract)) == []


# ---- admin 계약 삭제 (AC33) ----


async def test_admin_delete_removes_the_contract_folder_after_commit(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM, "a.pdf")
    await contract_env.put_file(contract.id, KIM, "b.pdf")

    await contract_env.delete.execute(contract.id, BOSS)

    assert not contract_env.contract_folder_exists(contract.id)
    assert contract_env.storage.file_count() == 0


async def test_admin_delete_with_a_failed_commit_keeps_the_folder(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment
    broken = DeleteLicenseContract(commit_failing_factory(contract_env.uow), contract_env.storage)

    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(contract.id, BOSS)

    assert contract_env.content_of(attachment) == b"hello"
    assert len(await contract_env.contracts_of(contract.deal_code.value)) == 1


async def test_admin_delete_by_a_forbidden_actor_keeps_the_folder(
    contract_env: ContractEnv,
) -> None:
    from app.domain.license_contract.errors import ContractDeleteForbiddenError  # noqa: PLC0415

    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM)

    with pytest.raises(ContractDeleteForbiddenError):
        await contract_env.delete.execute(contract.id, KIM)

    assert contract_env.contract_folder_exists(contract.id)


async def test_admin_delete_without_storage_settings_leaves_the_folder(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM)
    await contract_env.remove_storage_settings()

    await contract_env.delete.execute(contract.id, BOSS)

    assert await contract_env.contracts_of(contract.deal_code.value) == []
    assert contract_env.contract_folder_exists(contract.id)  # 위치를 몰라 건드리지 않는다


async def test_admin_delete_survives_a_folder_cleanup_failure_and_logs_a_warning(
    contract_env: ContractEnv, caplog: pytest.LogCaptureFixture
) -> None:
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM)
    contract_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    await contract_env.delete.execute(contract.id, BOSS)

    assert await contract_env.contracts_of(contract.deal_code.value) == []
    assert [r for r in caplog.records if r.levelno == logging.WARNING]


# ---- Won 이탈 삭제 (AC33) ----


async def test_won_exit_delete_removes_every_contract_folder_of_the_deal_only(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    first = await contract_env.seed_contract(code)
    second = await contract_env.seed_contract(code, status="ended")
    other_code = await contract_env.won_deal_without_contract(KIM)
    outsider = await contract_env.seed_contract(other_code)
    await contract_env.put_file(first.id, KIM, "a.pdf")
    await contract_env.put_file(second.id, KIM, "b.pdf")
    outsider_file = (await contract_env.put_file(outsider.id, KIM, "c.pdf", b"mine")).attachment
    deal_file = await contract_env.seed_deal_file(code)

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    assert not contract_env.contract_folder_exists(first.id)
    assert not contract_env.contract_folder_exists(second.id)
    assert contract_env.content_of(outsider_file) == b"mine"
    assert contract_env.content_of(deal_file) == b"deal"


async def test_won_exit_keep_leaves_the_folders(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=False)

    assert contract_env.contract_folder_exists(contract.id)


async def test_won_exit_delete_without_storage_settings_leaves_the_folders(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)
    await contract_env.remove_storage_settings()

    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)

    assert await contract_env.contracts_of(code) == []
    assert contract_env.contract_folder_exists(contract.id)


async def test_won_exit_delete_survives_a_folder_cleanup_failure_and_logs_a_warning(
    contract_env: ContractEnv, caplog: pytest.LogCaptureFixture
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)
    contract_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    await contract_env.leave_won_by_form(code, KIM, delete_contracts=True)

    assert await contract_env.forecast_of(code) == "commit"
    assert [r for r in caplog.records if r.levelno == logging.WARNING]


# ---- Deal 삭제 (AC33) ----


async def test_deleting_a_deal_removes_the_deal_folder_and_its_contract_folders(
    contract_env: ContractEnv,
) -> None:
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
    await delete_deal.execute(code, code, BOSS)

    assert not contract_env.deal_folder_exists(code)
    assert not contract_env.contract_folder_exists(first.id)
    assert not contract_env.contract_folder_exists(second.id)
    assert contract_env.content_of(outsider_file) == b"o"
    assert contract_env.content_of(other_deal_file) == b"deal"


async def test_deleting_a_deal_without_storage_settings_leaves_the_files(
    contract_env: ContractEnv,
) -> None:
    from app.application.deal.delete_deal import DeleteDeal  # noqa: PLC0415

    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)
    await contract_env.remove_storage_settings()

    await DeleteDeal(contract_env.uow_factory, contract_env.clock, contract_env.storage).execute(
        code, code, BOSS
    )

    assert contract_env.contract_folder_exists(contract.id)


async def test_deleting_a_deal_survives_a_cleanup_failure_and_logs_a_warning(
    contract_env: ContractEnv, caplog: pytest.LogCaptureFixture
) -> None:
    from app.application.deal.delete_deal import DeleteDeal  # noqa: PLC0415
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    await contract_env.put_file(contract.id, KIM)
    contract_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    await DeleteDeal(contract_env.uow_factory, contract_env.clock, contract_env.storage).execute(
        code, code, BOSS
    )

    assert DealCode(code) not in contract_env.uow.deals._items
    assert [r for r in caplog.records if r.levelno == logging.WARNING]


# ---- 업로드 도중 계약 삭제 (AC35, 순차 재현) ----


async def test_upload_when_the_contract_is_deleted_before_recording_removes_its_folder(
    contract_env: ContractEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.put_file(contract.id, KIM)

    assert not contract_env.contract_folder_exists(
        contract.id
    )  # 새로 쓴 파일과 빈 폴더가 남지 않는다
    assert storage.file_count() == 0
