"""계약 첨부 유스케이스(AC20·AC21): Deal 첨부와 같은 규칙, 이력·Deal 수정 시각은 건드리지 않는다."""

from typing import TYPE_CHECKING

import pytest
from app.domain.license_contract.errors import (
    ContractAttachmentNotFoundError,
    LicenseContractNotFoundError,
)

from app.application.attachment.inputs import UploadOutcomeKind
from app.application.storage.errors import StorageUnavailableError
from app.domain.attachment.errors import (
    AttachmentDeleteForbiddenError,
    AttachmentNameTakenError,
    AttachmentReplaceForbiddenError,
)
from app.domain.attachment.values import OnExists
from app.domain.common.errors import InvalidValueError
from app.domain.deal.code import DealCode
from tests.support.expect import raises_with
from tests.support.ids import MISSING_ID
from tests.unit.application.license_contract_env import BOSS, GONE_SALES, KIM, PARK, VIEWER

if TYPE_CHECKING:
    from app.domain.license_contract.entities import LicenseContract

    from tests.unit.application.license_contract_env import ContractEnv

DELETE_FORBIDDEN = "본인이 올린 파일만 삭제할 수 있습니다."
REPLACE_FORBIDDEN = "본인이 올린 파일만 교체할 수 있습니다."
UPLOAD_UNAVAILABLE = "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."


async def _contract(contract_env: ContractEnv) -> LicenseContract:
    code = await contract_env.open_deal()
    return await contract_env.seed_contract(code)


async def test_upload_new_file_stores_row_and_disk_file_under_the_deal_directory(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)

    outcome = await contract_env.put_file(contract.id, KIM, "계약서.pdf", b"content")

    assert outcome.kind is UploadOutcomeKind.UPLOADED
    attachment = outcome.attachment
    assert attachment.contract_id == contract.id
    assert attachment.deal_code == contract.deal_code
    assert (attachment.file_name.value, attachment.size, attachment.uploaded_by) == (
        "계약서.pdf",
        7,
        KIM.user_id,
    )
    assert contract_env.content_of(attachment) == b"content"
    assert [a.id for a in await contract_env.files_of(contract.id)] == [attachment.id]


async def test_upload_does_not_write_deal_history_or_touch_the_deal(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    code = contract.deal_code
    history_before = await contract_env.env.history_rows(code.value)
    updated_before = (await contract_env.uow.deals.get(code)).updated_at

    await contract_env.put_file(contract.id, KIM)

    assert await contract_env.env.history_rows(code.value) == history_before
    assert (await contract_env.uow.deals.get(code)).updated_at == updated_before


async def test_upload_same_name_ask_raises_file_exists(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    with pytest.raises(AttachmentNameTakenError):
        await contract_env.put_file(contract.id, KIM, "a.pdf", b"new")

    assert contract_env.content_of(first) == b"old"
    assert len(await contract_env.files_of(contract.id)) == 1
    assert contract_env.storage.file_count() == 1  # 새로 쓴 임시 파일은 남기지 않는다


async def test_upload_same_name_skip_returns_skipped_and_leaves_no_new_file(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    outcome = await contract_env.put_file(
        contract.id, PARK, "a.pdf", b"new", on_exists=OnExists.SKIP
    )

    assert outcome.kind is UploadOutcomeKind.SKIPPED
    assert outcome.attachment is None
    assert contract_env.content_of(first) == b"old"
    assert contract_env.storage.file_count() == 1


async def test_upload_replace_deletes_old_file_after_commit(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    outcome = await contract_env.put_file(
        contract.id, KIM, "a.pdf", b"newer", on_exists=OnExists.REPLACE
    )

    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert outcome.attachment.id == first.id
    assert outcome.attachment.storage_key != first.storage_key
    assert contract_env.content_of(first) is None
    assert contract_env.content_of(outcome.attachment) == b"newer"
    assert contract_env.storage.file_count() == 1


async def test_upload_replace_by_another_sales_is_forbidden(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    with raises_with(AttachmentReplaceForbiddenError, REPLACE_FORBIDDEN):
        await contract_env.put_file(contract.id, PARK, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    assert contract_env.content_of(first) == b"old"
    assert contract_env.storage.file_count() == 1


async def test_upload_replace_by_admin_is_allowed(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")

    outcome = await contract_env.put_file(
        contract.id, BOSS, "a.pdf", b"new", on_exists=OnExists.REPLACE
    )

    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert outcome.attachment.uploaded_by == BOSS.user_id


async def test_same_name_in_another_contract_is_a_new_file(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    first = await contract_env.seed_contract(code, status="ended")
    second = await contract_env.seed_contract(code)
    await contract_env.put_file(first.id, KIM, "a.pdf", b"one")

    outcome = await contract_env.put_file(second.id, KIM, "a.pdf", b"two")

    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert contract_env.storage.file_count() == 2


async def test_upload_without_storage_settings_raises_unavailable(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    await contract_env.remove_storage_settings()

    with raises_with(StorageUnavailableError, UPLOAD_UNAVAILABLE):
        await contract_env.put_file(contract.id, KIM)

    assert await contract_env.files_of(contract.id) == []
    assert contract_env.storage.file_count() == 0


async def test_upload_to_a_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.put_file(MISSING_ID, KIM)  # type: ignore[arg-type]

    assert contract_env.storage.file_count() == 0


@pytest.mark.parametrize("name", ["virus.exe", "run.bat"])
async def test_upload_blocked_extension_is_rejected(contract_env: ContractEnv, name: str) -> None:
    contract = await _contract(contract_env)

    with pytest.raises(InvalidValueError):
        await contract_env.put_file(contract.id, KIM, name)

    assert contract_env.storage.file_count() == 0


async def test_upload_description_over_100_chars_is_rejected(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)

    with pytest.raises(InvalidValueError):
        await contract_env.put_file(contract.id, KIM, description="가" * 101)


async def test_upload_without_a_file_part_is_rejected(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)

    with pytest.raises(InvalidValueError):
        await contract_env.put_file(contract.id, KIM, None)


async def test_upload_is_allowed_on_an_ended_contract(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    ended = await contract_env.seed_contract(code, status="ended")

    outcome = await contract_env.put_file(ended.id, KIM)

    assert outcome.kind is UploadOutcomeKind.UPLOADED


async def test_list_files_returns_newest_first(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM, "old.pdf")
    await contract_env.put_file(contract.id, KIM, "new.pdf")

    listed = await contract_env.list_files.execute(contract.id)

    assert [a.file_name.value for a in listed] == ["new.pdf", "old.pdf"]


async def test_list_files_of_a_missing_contract_raises_not_found(
    contract_env: ContractEnv,
) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.list_files.execute(MISSING_ID)  # type: ignore[arg-type]


async def test_download_opens_the_stored_content(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"payload")).attachment

    found, opened = await contract_env.download.execute(attachment.id)

    assert found.id == attachment.id
    assert b"".join([chunk async for chunk in opened.chunks]) == b"payload"
    assert opened.size == len(b"payload")


async def test_download_without_storage_settings_raises_unavailable(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment
    await contract_env.remove_storage_settings()

    with pytest.raises(StorageUnavailableError):
        await contract_env.download.execute(attachment.id)


async def test_download_missing_attachment_raises_not_found(contract_env: ContractEnv) -> None:
    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_env.download.execute(MISSING_ID)  # type: ignore[arg-type]


async def test_delete_file_by_uploader_removes_row_and_disk_file(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment

    await contract_env.delete_file.execute(attachment.id, KIM)

    assert await contract_env.files_of(contract.id) == []
    assert contract_env.content_of(attachment) is None


async def test_delete_file_by_another_sales_is_forbidden(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment

    with raises_with(AttachmentDeleteForbiddenError, DELETE_FORBIDDEN):
        await contract_env.delete_file.execute(attachment.id, PARK)

    assert contract_env.content_of(attachment) == b"hello"


async def test_delete_file_by_admin_and_for_a_resigned_sales_file(
    contract_env: ContractEnv,
) -> None:
    contract = await _contract(contract_env)
    resigned_file = await contract_env.seed_file(contract, GONE_SALES, "gone.pdf")
    admin_target = (await contract_env.put_file(contract.id, KIM, "kim.pdf")).attachment

    await contract_env.delete_file.execute(resigned_file.id, PARK)  # 퇴사한 sales의 파일은 sales도
    await contract_env.delete_file.execute(admin_target.id, BOSS)

    assert await contract_env.files_of(contract.id) == []


async def test_delete_file_by_read_only_user_is_forbidden(contract_env: ContractEnv) -> None:
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment

    with pytest.raises(AttachmentDeleteForbiddenError):
        await contract_env.delete_file.execute(attachment.id, VIEWER)


async def test_delete_missing_file_is_not_found_before_the_permission_check(
    contract_env: ContractEnv,
) -> None:
    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_env.delete_file.execute(MISSING_ID, VIEWER)  # type: ignore[arg-type]


async def test_deleting_a_deal_removes_its_contracts_attachment_rows_and_files(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    attachment = await contract_env.seed_file(contract)
    from app.application.deal.delete_deal import DeleteDeal  # noqa: PLC0415

    delete_deal = DeleteDeal(contract_env.uow_factory, contract_env.clock, contract_env.storage)
    await delete_deal.execute(code, code, BOSS)

    assert DealCode(code) not in contract_env.uow.deals._items
    assert await contract_env.all_file_rows() == []
    assert await contract_env.contracts_of(code) == []
    assert contract_env.content_of(attachment) is None  # Deal 디렉터리 정리로 지워진다
