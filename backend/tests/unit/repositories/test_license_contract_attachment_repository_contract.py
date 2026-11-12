"""LicenseContractAttachmentRepository 계약: Fake와 SQL 구현에 같은 테스트.

Deal 첨부 저장소와 같은 규칙에 소속이 계약이다. 같은 이름은 계약 안에서만 겹침을 막는다.
"""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from app.domain.attachment.errors import AttachmentNameTakenError
from app.domain.attachment.values import FileName
from app.domain.common.errors import InvalidReferenceError
from app.domain.license_contract.attachment import ContractAttachment
from app.domain.license_contract.errors import (
    ContractAttachmentNotFoundError,
    LicenseContractNotFoundError,
)
from app.domain.license_contract.values import ContractAttachmentId, LicenseContractId
from tests.factories import NOW, later
from tests.factories_license_contract import make_contract, make_contract_attachment
from tests.support.ids import new_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.license_contract_case import ContractCase

KIM = uid("lca-repo-kim")
PARK = uid("lca-repo-park")


async def test_add_and_get_round_trip_keeps_every_field(contract_case: ContractCase) -> None:
    """첨부를 저장하고 읽으면 모든 필드가 그대로다."""
    # given: 계약과 모든 필드가 채워진 첨부
    contract = await contract_case.contract(await contract_case.deal())
    attachment = await contract_case.attach(
        contract,
        "견적서.pdf",
        description="최종본",
        size=1_234,
        mime="application/pdf",
        storage_key="a" * 32,
        uploaded_by=KIM,
        now=NOW,
    )

    # when: 저장하고 읽는다
    stored = await contract_case.files.get(attachment.id)

    # then: 이름·설명·크기·MIME·키·업로더·시각이 같다
    assert isinstance(stored, ContractAttachment)
    assert stored.id == attachment.id
    assert (stored.contract_id, stored.deal_code) == (contract.id, contract.deal_code)
    assert stored.file_name == FileName.parse("견적서.pdf")
    assert (stored.description, stored.size, stored.mime) == ("최종본", 1_234, "application/pdf")
    assert (stored.storage_key, stored.uploaded_by) == ("a" * 32, KIM)
    assert stored.uploaded_at == NOW


async def test_get_missing_raises_not_found(contract_case: ContractCase) -> None:
    """없는 첨부를 읽으면 ContractAttachmentNotFoundError다.

    테스트 코드: LC-029
    """
    # when: 없는 id로 읽는다
    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_case.files.get(ContractAttachmentId(new_id()))
    # then: ContractAttachmentNotFoundError


async def test_add_to_a_missing_contract_raises_contract_not_found(
    contract_case: ContractCase,
) -> None:
    """없는 계약에 첨부를 저장하면 LicenseContractNotFoundError다.

    테스트 코드: LC-029
    """
    # given: 저장되지 않은 계약
    ghost = make_contract(deal_code=(await contract_case.deal()).id)

    # when: 그 계약의 첨부를 저장한다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.files.add(make_contract_attachment(ghost))
    # then: LicenseContractNotFoundError


async def test_add_with_a_missing_uploader_raises_invalid_reference(
    contract_case: ContractCase,
) -> None:
    """없는 업로더로 저장하면 InvalidReferenceError다."""
    # given: 계약
    contract = await contract_case.contract(await contract_case.deal())

    # when: 없는 사용자가 올린 첨부를 저장한다
    with pytest.raises(InvalidReferenceError):
        await contract_case.files.add(
            make_contract_attachment(contract, uploaded_by=uid("lca-never-created"))
        )
    # then: InvalidReferenceError


async def test_the_same_name_in_the_same_contract_is_rejected_and_the_session_stays_usable(
    contract_case: ContractCase,
) -> None:
    """같은 계약의 같은 이름은 거절되고 이후 저장을 이어갈 수 있다.

    테스트 코드: LC-064
    """
    # given: a.pdf가 있는 계약
    contract = await contract_case.contract(await contract_case.deal())
    await contract_case.attach(contract, "a.pdf")

    # when: a.pdf를 다시 저장한 뒤 b.pdf를 저장한다
    with pytest.raises(AttachmentNameTakenError):
        await contract_case.files.add(make_contract_attachment(contract, name="a.pdf"))

    other = await contract_case.attach(contract, "b.pdf")  # 이어서 저장된다
    # then: AttachmentNameTakenError, b.pdf는 저장된다
    assert other.file_name.value == "b.pdf"


async def test_names_are_case_sensitive_and_scoped_to_the_contract(
    contract_case: ContractCase,
) -> None:
    """이름은 대소문자를 구분하고 계약마다 따로 고유하다.

    테스트 코드: LC-064
    """
    # given: 계약 둘
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal)
    # when: a.pdf·A.pdf를 첫 계약에, a.pdf를 둘째 계약에 저장한다
    await contract_case.attach(first, "a.pdf")

    await contract_case.attach(first, "A.pdf")
    await contract_case.attach(second, "a.pdf")  # 다른 계약은 같은 이름이 가능하다

    # then: 모두 저장된다
    assert len(list(await contract_case.files.list_by_contract(first.id))) == 2
    assert len(list(await contract_case.files.list_by_contract(second.id))) == 1


async def test_find_by_name_returns_the_attachment_or_none(contract_case: ContractCase) -> None:
    """이름으로 찾으면 첨부 또는 None을 돌려준다."""
    # given: a.pdf가 있는 계약
    contract = await contract_case.contract(await contract_case.deal())
    attachment = await contract_case.attach(contract, "a.pdf")

    # when: 이름으로 찾는다
    found = await contract_case.files.find_by_name(contract.id, FileName.parse("a.pdf"))

    # then: 있는 이름은 그 첨부, 없는 이름은 None이다
    assert found is not None
    assert found.id == attachment.id
    assert await contract_case.files.find_by_name(contract.id, FileName.parse("b.pdf")) is None
    assert (
        await contract_case.files.find_by_name(LicenseContractId(new_id()), FileName.parse("a.pdf"))
        is None
    )


async def test_list_by_contract_is_newest_first_then_by_id_descending(
    contract_case: ContractCase,
) -> None:
    """계약의 첨부 목록은 최신 업로드 순이고 같으면 id 내림차순이다.

    테스트 코드: LC-074
    """
    # given: 시각이 다르거나 같은 첨부들
    contract = await contract_case.contract(await contract_case.deal())
    old = await contract_case.attach(contract, "old.pdf", now=NOW)
    tie_a = await contract_case.attach(contract, "tie-a.pdf", now=later(60))
    tie_b = await contract_case.attach(contract, "tie-b.pdf", now=later(60))
    newest = await contract_case.attach(contract, "new.pdf", now=NOW + timedelta(hours=1))

    # when: 목록을 읽는다
    listed = await contract_case.files.list_by_contract(contract.id)

    # then: 최신 순, 같은 시각은 id 내림차순
    assert [a.id for a in listed] == [
        newest.id,
        *sorted([tie_a.id, tie_b.id], reverse=True),
        old.id,
    ]


async def test_list_by_contract_lists_only_that_contract(contract_case: ContractCase) -> None:
    """첨부 목록은 그 계약의 첨부만 담는다."""
    # given: 첨부가 하나씩 있는 계약 둘
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal)
    mine = await contract_case.attach(first, "mine.pdf")
    await contract_case.attach(second, "other.pdf")

    # when: 한 계약의 목록을 읽는다
    actual = [a.id for a in await contract_case.files.list_by_contract(first.id)]
    # then: 그 계약의 첨부만 온다
    assert actual == [mine.id]


async def test_update_saves_only_the_content_fields(contract_case: ContractCase) -> None:
    """수정은 내용 필드만 저장하고 이름은 바꾸지 않는다.

    테스트 코드: LC-066
    """
    # given: 첨부 하나
    contract = await contract_case.contract(await contract_case.deal())
    attachment = await contract_case.attach(contract, "a.pdf", uploaded_by=KIM)
    stored = await contract_case.files.get(attachment.id)
    stored.replace(
        description="새 설명",
        size=99,
        mime="text/plain",
        storage_key="b" * 32,
        uploaded_by=await contract_case.user("lca-repo-park"),
        now=later(),
    )
    stored.file_name = FileName.parse("renamed.pdf")  # 이름은 불변이라 저장되지 않는다

    # when: 내용과 이름을 바꿔 수정 저장한다
    await contract_case.files.update(stored)

    # then: 내용 필드만 바뀌고 이름은 그대로다
    saved = await contract_case.files.get(attachment.id)
    assert (saved.description, saved.size, saved.mime) == ("새 설명", 99, "text/plain")
    assert (saved.storage_key, saved.uploaded_by, saved.uploaded_at) == ("b" * 32, PARK, later())
    assert saved.updated_at == later()
    assert saved.file_name.value == "a.pdf"
    assert saved.contract_id == contract.id


async def test_update_missing_raises_not_found(contract_case: ContractCase) -> None:
    """없는 첨부를 수정하면 ContractAttachmentNotFoundError다.

    테스트 코드: LC-029
    """
    # given: 계약
    contract = await contract_case.contract(await contract_case.deal())

    # when: 저장되지 않은 첨부를 수정한다
    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_case.files.update(make_contract_attachment(contract))
    # then: ContractAttachmentNotFoundError


async def test_delete_removes_only_that_row(contract_case: ContractCase) -> None:
    """삭제는 그 행만 지운다.

    테스트 코드: LC-076
    """
    # given: 첨부 둘이 있는 계약
    contract = await contract_case.contract(await contract_case.deal())
    gone = await contract_case.attach(contract, "gone.pdf")
    kept = await contract_case.attach(contract, "kept.pdf")

    # when: 하나를 삭제한다
    await contract_case.files.delete(gone.id)

    # then: 다른 첨부는 남는다
    assert [a.id for a in await contract_case.files.list_by_contract(contract.id)] == [kept.id]


async def test_delete_missing_raises_not_found(contract_case: ContractCase) -> None:
    """없는 첨부를 삭제하면 ContractAttachmentNotFoundError다.

    테스트 코드: LC-029
    """
    # when: 없는 id를 삭제한다
    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_case.files.delete(ContractAttachmentId(new_id()))
    # then: ContractAttachmentNotFoundError
