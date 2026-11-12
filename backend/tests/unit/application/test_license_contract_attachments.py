"""계약 첨부 유스케이스: Deal 첨부와 같은 규칙, 이력·Deal 수정 시각은 건드리지 않는다."""

from typing import TYPE_CHECKING

import pytest

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
from app.domain.license_contract.errors import (
    ContractAttachmentNotFoundError,
    LicenseContractNotFoundError,
)
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


async def test_upload_new_file_stores_row_and_disk_file_in_the_contract_folder(
    contract_env: ContractEnv,
) -> None:
    """새 파일을 올리면 첨부 행과 디스크 파일이 생기고 목록에 보인다.

    테스트 코드: LC-063
    """
    # given: 저장 위치가 있는 미발급 계약
    contract = await _contract(contract_env)

    # when: KIM이 계약서.pdf(7바이트)를 올린다
    outcome = await contract_env.put_file(contract.id, KIM, "계약서.pdf", b"content")

    # then: uploaded, 첨부의 계약·Deal·이름·크기·업로더, 디스크 내용, 목록 확인
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
    """첨부 업로드는 Deal History와 Deal 수정 시각을 바꾸지 않는다.

    테스트 코드: LC-035
    """
    # given: 계약, 처음의 Deal 이력과 수정 시각
    contract = await _contract(contract_env)
    code = contract.deal_code
    history_before = await contract_env.env.history_rows(code.value)
    updated_before = (await contract_env.uow.deals.get(code)).updated_at

    # when: 첨부를 올린다
    await contract_env.put_file(contract.id, KIM)

    # then: Deal 이력과 수정 시각은 그대로다
    assert await contract_env.env.history_rows(code.value) == history_before
    assert (await contract_env.uow.deals.get(code)).updated_at == updated_before


async def test_upload_same_name_ask_raises_file_exists(contract_env: ContractEnv) -> None:
    """같은 이름을 기본(ask)으로 올리면 file-exists 오류이고 새 파일이 남지 않는다.

    테스트 코드: LC-064
    """
    # given: a.pdf(old)가 올라가 있는 계약
    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    # when: a.pdf(new)를 on_exists 없이 올린다
    with pytest.raises(AttachmentNameTakenError):
        await contract_env.put_file(contract.id, KIM, "a.pdf", b"new")

    # then: AttachmentNameTakenError, 내용 old, 첨부 1개, 디스크 파일 1개
    assert contract_env.content_of(first) == b"old"
    assert len(await contract_env.files_of(contract.id)) == 1
    assert contract_env.storage.file_count() == 1  # 새로 쓴 임시 파일은 남기지 않는다


async def test_upload_same_name_skip_returns_skipped_and_leaves_no_new_file(
    contract_env: ContractEnv,
) -> None:
    """같은 이름을 skip으로 올리면 아무것도 바뀌지 않는다.

    테스트 코드: LC-065
    """
    # given: a.pdf(old)가 올라가 있는 계약
    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    # when: PARK가 a.pdf를 skip으로 올린다
    outcome = await contract_env.put_file(
        contract.id, PARK, "a.pdf", b"new", on_exists=OnExists.SKIP
    )

    # then: skipped, attachment 없음, 내용 old, 디스크 파일 1개
    assert outcome.kind is UploadOutcomeKind.SKIPPED
    assert outcome.attachment is None
    assert contract_env.content_of(first) == b"old"
    assert contract_env.storage.file_count() == 1


async def test_upload_replace_deletes_old_file_after_commit(contract_env: ContractEnv) -> None:
    """replace로 올리면 같은 첨부 id의 내용이 바뀌고 이전 파일이 지워진다.

    테스트 코드: LC-066
    """
    # given: KIM이 올린 a.pdf(old)가 있는 계약
    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    # when: KIM이 a.pdf(newer)를 replace로 올린다
    outcome = await contract_env.put_file(
        contract.id, KIM, "a.pdf", b"newer", on_exists=OnExists.REPLACE
    )

    # then: replaced, 같은 id, 새 키, 이전 파일 없음, 새 내용, 파일 1개
    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert outcome.attachment.id == first.id
    assert outcome.attachment.storage_key != first.storage_key
    assert contract_env.content_of(first) is None
    assert contract_env.content_of(outcome.attachment) == b"newer"
    assert contract_env.storage.file_count() == 1


async def test_upload_replace_by_another_sales_is_forbidden(contract_env: ContractEnv) -> None:
    """다른 sales는 남의 파일을 교체할 수 없다.

    테스트 코드: LC-066
    """
    # given: KIM이 올린 a.pdf(old)가 있는 계약
    contract = await _contract(contract_env)
    first = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")).attachment

    # when: PARK가 a.pdf를 replace로 올린다
    with raises_with(AttachmentReplaceForbiddenError, REPLACE_FORBIDDEN):
        await contract_env.put_file(contract.id, PARK, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    # then: AttachmentReplaceForbiddenError 문구, 내용 old 그대로
    assert contract_env.content_of(first) == b"old"
    assert contract_env.storage.file_count() == 1


async def test_upload_replace_by_admin_is_allowed(contract_env: ContractEnv) -> None:
    """admin은 남의 파일도 교체할 수 있고 업로더가 admin으로 바뀐다.

    테스트 코드: LC-066
    """
    # given: KIM이 올린 a.pdf가 있는 계약
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM, "a.pdf", b"old")

    # when: BOSS(admin)가 a.pdf를 replace로 올린다
    outcome = await contract_env.put_file(
        contract.id, BOSS, "a.pdf", b"new", on_exists=OnExists.REPLACE
    )

    # then: replaced, 업로더는 BOSS
    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert outcome.attachment.uploaded_by == BOSS.user_id


async def test_same_name_in_another_contract_is_a_new_file(contract_env: ContractEnv) -> None:
    """다른 계약의 같은 이름은 새 파일로 올라간다."""
    # given: 같은 Deal의 계약 둘 중 첫 계약에 a.pdf
    code = await contract_env.open_deal()
    first = await contract_env.seed_contract(code, status="ended")
    second = await contract_env.seed_contract(code)
    await contract_env.put_file(first.id, KIM, "a.pdf", b"one")

    # when: 둘째 계약에 같은 이름 a.pdf를 올린다
    outcome = await contract_env.put_file(second.id, KIM, "a.pdf", b"two")

    # then: uploaded이고 디스크 파일이 2개다
    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert contract_env.storage.file_count() == 2


async def test_upload_without_storage_settings_raises_unavailable(
    contract_env: ContractEnv,
) -> None:
    """저장 위치 설정이 없으면 업로드가 거절되고 아무것도 생기지 않는다.

    테스트 코드: LC-068
    """
    # given: 저장 위치 설정을 지운 상태의 계약
    contract = await _contract(contract_env)
    await contract_env.remove_storage_settings()

    # when: 파일을 올린다
    with raises_with(StorageUnavailableError, UPLOAD_UNAVAILABLE):
        await contract_env.put_file(contract.id, KIM)

    # then: StorageUnavailableError 문구, 첨부·디스크 파일 없음
    assert await contract_env.files_of(contract.id) == []
    assert contract_env.storage.file_count() == 0


async def test_upload_to_a_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    """없는 계약에 올리면 404이고 디스크 파일이 남지 않는다.

    테스트 코드: LC-029
    """
    # when: 없는 계약 id에 올린다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.put_file(MISSING_ID, KIM)  # type: ignore[arg-type]

    # then: LicenseContractNotFoundError, 디스크 파일 0개
    assert contract_env.storage.file_count() == 0


@pytest.mark.parametrize("name", ["virus.exe", "run.bat"])
async def test_upload_blocked_extension_is_rejected(contract_env: ContractEnv, name: str) -> None:
    """차단 확장자 파일은 올릴 수 없다.

    테스트 코드: LC-067
    """
    # given: 계약
    contract = await _contract(contract_env)

    # when: virus.exe 또는 run.bat를 올린다
    with pytest.raises(InvalidValueError):
        await contract_env.put_file(contract.id, KIM, name)

    # then: InvalidValueError, 디스크 파일 0개
    assert contract_env.storage.file_count() == 0


async def test_upload_description_over_100_chars_is_rejected(contract_env: ContractEnv) -> None:
    """설명이 100자를 넘으면 올릴 수 없다.

    테스트 코드: LC-067
    """
    # given: 계약
    contract = await _contract(contract_env)

    # when: 설명 101자로 올린다
    with pytest.raises(InvalidValueError):
        await contract_env.put_file(contract.id, KIM, description="가" * 101)
    # then: InvalidValueError


async def test_upload_without_a_file_part_is_rejected(contract_env: ContractEnv) -> None:
    """파일 없이 올릴 수 없다.

    테스트 코드: LC-067
    """
    # given: 계약
    contract = await _contract(contract_env)

    # when: 파일 파트 없이 올린다
    with pytest.raises(InvalidValueError):
        await contract_env.put_file(contract.id, KIM, None)
    # then: InvalidValueError


async def test_upload_is_allowed_on_an_ended_contract(contract_env: ContractEnv) -> None:
    """종료된 계약에도 첨부를 올릴 수 있다.

    테스트 코드: LC-063
    """
    # given: 종료 계약
    code = await contract_env.open_deal()
    ended = await contract_env.seed_contract(code, status="ended")

    # when: 첨부를 올린다
    outcome = await contract_env.put_file(ended.id, KIM)

    # then: uploaded다
    assert outcome.kind is UploadOutcomeKind.UPLOADED


async def test_list_files_returns_newest_first(contract_env: ContractEnv) -> None:
    """첨부 목록은 최신 업로드 순이다.

    테스트 코드: LC-074
    """
    # given: old.pdf를 먼저, new.pdf를 나중에 올린 계약
    contract = await _contract(contract_env)
    await contract_env.put_file(contract.id, KIM, "old.pdf")
    await contract_env.put_file(contract.id, KIM, "new.pdf")

    # when: 첨부 목록을 읽는다
    listed = await contract_env.list_files.execute(contract.id)

    # then: new.pdf, old.pdf 순이다
    assert [a.file_name.value for a in listed] == ["new.pdf", "old.pdf"]


async def test_list_files_of_a_missing_contract_raises_not_found(
    contract_env: ContractEnv,
) -> None:
    """없는 계약의 첨부 목록은 404다.

    테스트 코드: LC-029
    """
    # when: 없는 계약 id의 첨부 목록을 읽는다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.list_files.execute(MISSING_ID)  # type: ignore[arg-type]
    # then: LicenseContractNotFoundError


async def test_download_opens_the_stored_content(contract_env: ContractEnv) -> None:
    """다운로드는 저장된 내용을 그대로 돌려준다.

    테스트 코드: LC-074
    """
    # given: payload를 올린 첨부
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM, "a.pdf", b"payload")).attachment

    # when: 다운로드한다
    found, opened = await contract_env.download.execute(attachment.id)

    # then: 같은 첨부와 정확한 바이트·크기
    assert found.id == attachment.id
    assert b"".join([chunk async for chunk in opened.chunks]) == b"payload"
    assert opened.size == len(b"payload")


async def test_download_without_storage_settings_raises_unavailable(
    contract_env: ContractEnv,
) -> None:
    """저장 위치 설정이 없으면 다운로드는 StorageUnavailableError다.

    테스트 코드: LC-075
    """
    # given: 첨부를 올린 뒤 저장 위치 설정을 지웠다
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment
    await contract_env.remove_storage_settings()

    # when: 다운로드한다
    with pytest.raises(StorageUnavailableError):
        await contract_env.download.execute(attachment.id)
    # then: StorageUnavailableError


async def test_download_missing_attachment_raises_not_found(contract_env: ContractEnv) -> None:
    """없는 첨부를 내려받으면 404다.

    테스트 코드: LC-029
    """
    # when: 없는 첨부 id로 다운로드한다
    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_env.download.execute(MISSING_ID)  # type: ignore[arg-type]
    # then: ContractAttachmentNotFoundError


async def test_delete_file_by_uploader_removes_row_and_disk_file(
    contract_env: ContractEnv,
) -> None:
    """업로더가 지우면 행과 디스크 파일이 모두 없어진다.

    테스트 코드: LC-076
    """
    # given: KIM이 올린 첨부
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment

    # when: KIM이 삭제한다
    await contract_env.delete_file.execute(attachment.id, KIM)

    # then: 첨부 행과 디스크 내용이 없다
    assert await contract_env.files_of(contract.id) == []
    assert contract_env.content_of(attachment) is None


async def test_delete_file_by_another_sales_is_forbidden(contract_env: ContractEnv) -> None:
    """다른 sales는 남의 첨부를 지울 수 없다.

    테스트 코드: LC-077
    """
    # given: KIM이 올린 첨부
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment

    # when: PARK가 삭제한다
    with raises_with(AttachmentDeleteForbiddenError, DELETE_FORBIDDEN):
        await contract_env.delete_file.execute(attachment.id, PARK)

    # then: AttachmentDeleteForbiddenError 문구, 파일 내용 그대로
    assert contract_env.content_of(attachment) == b"hello"


async def test_delete_file_by_admin_and_for_a_resigned_sales_file(
    contract_env: ContractEnv,
) -> None:
    """admin은 모든 파일을, sales는 퇴사한 sales의 파일을 지울 수 있다.

    테스트 코드: LC-077
    """
    # given: 퇴사한 sales가 올린 파일과 KIM이 올린 파일
    contract = await _contract(contract_env)
    resigned_file = await contract_env.seed_file(contract, GONE_SALES, "gone.pdf")
    admin_target = (await contract_env.put_file(contract.id, KIM, "kim.pdf")).attachment

    # when: PARK가 퇴사자 파일을, BOSS(admin)가 KIM 파일을 지운다
    await contract_env.delete_file.execute(resigned_file.id, PARK)  # 퇴사한 sales의 파일은 sales도
    await contract_env.delete_file.execute(admin_target.id, BOSS)

    # then: 첨부 행이 모두 없다
    assert await contract_env.files_of(contract.id) == []


async def test_delete_file_by_read_only_user_is_forbidden(contract_env: ContractEnv) -> None:
    """user는 첨부를 지울 수 없다.

    테스트 코드: LC-077
    """
    # given: KIM이 올린 첨부
    contract = await _contract(contract_env)
    attachment = (await contract_env.put_file(contract.id, KIM)).attachment

    # when: VIEWER(user)가 삭제한다
    with pytest.raises(AttachmentDeleteForbiddenError):
        await contract_env.delete_file.execute(attachment.id, VIEWER)
    # then: AttachmentDeleteForbiddenError


async def test_delete_missing_file_is_not_found_before_the_permission_check(
    contract_env: ContractEnv,
) -> None:
    """없는 첨부는 권한 판정보다 먼저 404다.

    테스트 코드: LC-029
    """
    # when: VIEWER(user)가 없는 첨부 id를 삭제한다
    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_env.delete_file.execute(MISSING_ID, VIEWER)  # type: ignore[arg-type]
    # then: ContractAttachmentNotFoundError(403이 아님)


async def test_deleting_a_deal_removes_its_contracts_attachment_rows_and_files(
    contract_env: ContractEnv,
) -> None:
    """Deal을 삭제하면 그 Deal의 계약·첨부 행과 파일이 지워진다.

    테스트 코드: LC-080
    """
    # given: 첨부가 있는 Won Deal의 계약
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    attachment = await contract_env.seed_file(contract)
    from app.application.deal.delete_deal import DeleteDeal  # noqa: PLC0415

    delete_deal = DeleteDeal(contract_env.uow_factory, contract_env.clock, contract_env.storage)
    # when: BOSS(admin)가 Deal을 삭제한다
    await delete_deal.execute(code, code, BOSS)

    # then: Deal·계약·첨부 행이 없고 디스크 파일도 없다
    assert DealCode(code) not in contract_env.uow.deals._items
    assert await contract_env.all_file_rows() == []
    assert await contract_env.contracts_of(code) == []
    assert contract_env.content_of(attachment) is None  # Deal 디렉터리 정리로 지워진다
