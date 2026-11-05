"""LicenseContractAttachmentRepository 계약(AC20·AC21·AC22): Fake와 SQL 구현에 같은 테스트.

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

    stored = await contract_case.files.get(attachment.id)

    assert isinstance(stored, ContractAttachment)
    assert stored.id == attachment.id
    assert (stored.contract_id, stored.deal_code) == (contract.id, contract.deal_code)
    assert stored.file_name == FileName.parse("견적서.pdf")
    assert (stored.description, stored.size, stored.mime) == ("최종본", 1_234, "application/pdf")
    assert (stored.storage_key, stored.uploaded_by) == ("a" * 32, KIM)
    assert stored.uploaded_at == NOW


async def test_get_missing_raises_not_found(contract_case: ContractCase) -> None:
    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_case.files.get(ContractAttachmentId(new_id()))


async def test_add_to_a_missing_contract_raises_contract_not_found(
    contract_case: ContractCase,
) -> None:
    ghost = make_contract(deal_code=(await contract_case.deal()).id)

    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.files.add(make_contract_attachment(ghost))


async def test_add_with_a_missing_uploader_raises_invalid_reference(
    contract_case: ContractCase,
) -> None:
    contract = await contract_case.contract(await contract_case.deal())

    with pytest.raises(InvalidReferenceError):
        await contract_case.files.add(
            make_contract_attachment(contract, uploaded_by=uid("lca-never-created"))
        )


async def test_the_same_name_in_the_same_contract_is_rejected_and_the_session_stays_usable(
    contract_case: ContractCase,
) -> None:
    contract = await contract_case.contract(await contract_case.deal())
    await contract_case.attach(contract, "a.pdf")

    with pytest.raises(AttachmentNameTakenError):
        await contract_case.files.add(make_contract_attachment(contract, name="a.pdf"))

    other = await contract_case.attach(contract, "b.pdf")  # 이어서 저장된다
    assert other.file_name.value == "b.pdf"


async def test_names_are_case_sensitive_and_scoped_to_the_contract(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal)
    await contract_case.attach(first, "a.pdf")

    await contract_case.attach(first, "A.pdf")
    await contract_case.attach(second, "a.pdf")  # 다른 계약은 같은 이름이 가능하다

    assert len(list(await contract_case.files.list_by_contract(first.id))) == 2
    assert len(list(await contract_case.files.list_by_contract(second.id))) == 1


async def test_find_by_name_returns_the_attachment_or_none(contract_case: ContractCase) -> None:
    contract = await contract_case.contract(await contract_case.deal())
    attachment = await contract_case.attach(contract, "a.pdf")

    found = await contract_case.files.find_by_name(contract.id, FileName.parse("a.pdf"))

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
    contract = await contract_case.contract(await contract_case.deal())
    old = await contract_case.attach(contract, "old.pdf", now=NOW)
    tie_a = await contract_case.attach(contract, "tie-a.pdf", now=later(60))
    tie_b = await contract_case.attach(contract, "tie-b.pdf", now=later(60))
    newest = await contract_case.attach(contract, "new.pdf", now=NOW + timedelta(hours=1))

    listed = await contract_case.files.list_by_contract(contract.id)

    assert [a.id for a in listed] == [
        newest.id,
        *sorted([tie_a.id, tie_b.id], reverse=True),
        old.id,
    ]


async def test_list_by_contract_lists_only_that_contract(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal)
    mine = await contract_case.attach(first, "mine.pdf")
    await contract_case.attach(second, "other.pdf")

    assert [a.id for a in await contract_case.files.list_by_contract(first.id)] == [mine.id]


async def test_update_saves_only_the_content_fields(contract_case: ContractCase) -> None:
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

    await contract_case.files.update(stored)

    saved = await contract_case.files.get(attachment.id)
    assert (saved.description, saved.size, saved.mime) == ("새 설명", 99, "text/plain")
    assert (saved.storage_key, saved.uploaded_by, saved.uploaded_at) == ("b" * 32, PARK, later())
    assert saved.updated_at == later()
    assert saved.file_name.value == "a.pdf"
    assert saved.contract_id == contract.id


async def test_update_missing_raises_not_found(contract_case: ContractCase) -> None:
    contract = await contract_case.contract(await contract_case.deal())

    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_case.files.update(make_contract_attachment(contract))


async def test_delete_removes_only_that_row(contract_case: ContractCase) -> None:
    contract = await contract_case.contract(await contract_case.deal())
    gone = await contract_case.attach(contract, "gone.pdf")
    kept = await contract_case.attach(contract, "kept.pdf")

    await contract_case.files.delete(gone.id)

    assert [a.id for a in await contract_case.files.list_by_contract(contract.id)] == [kept.id]


async def test_delete_missing_raises_not_found(contract_case: ContractCase) -> None:
    with pytest.raises(ContractAttachmentNotFoundError):
        await contract_case.files.delete(ContractAttachmentId(new_id()))
