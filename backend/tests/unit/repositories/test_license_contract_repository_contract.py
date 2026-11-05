"""LicenseContractRepository 계약(AC1·AC2·AC5·AC7·AC21): Fake와 SQL 구현에 같은 테스트.

저장·읽기·수정·삭제·참조 오류와 Deal 단위 연산. 실패하는 호출은 테스트마다 마지막 하나뿐이다
(SQL 트랜잭션; 발급 유니크 위반 뒤 계속 쓰기는 별도 파일에서 확인한다).
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.deal.errors import DealNotFoundError
from app.domain.license_contract.entities import LicenseContract
from app.domain.license_contract.errors import LicenseContractNotFoundError
from app.domain.license_contract.values import (
    ContractFields,
    ContractStatus,
    InspectionCycle,
    LicenseContractId,
    LicenseTerm,
    TermUnit,
)
from tests.factories import NOW, later, make_deal_code
from tests.factories_license_contract import make_contract
from tests.support.ids import new_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.license_contract_case import ContractCase

KIM = uid("lcr-kim")
PARK = uid("lcr-park")


async def test_add_and_get_round_trip_keeps_every_field(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    contract = make_contract(
        deal_code=deal.id,
        status="issued_new",
        start=date(2026, 1, 31),
        amount=1,
        unit="month",
        tech_owner="이기술",
        inspection="semiannual",
        note="여러 줄\n메모",
        by=KIM,
        now=NOW,
    )
    await contract_case.add(contract)

    stored = await contract_case.repository.get(contract.id)

    assert isinstance(stored, LicenseContract)
    assert stored.id == contract.id
    assert stored.deal_code == deal.id
    assert stored.status is ContractStatus.ISSUED_NEW
    assert stored.term == LicenseTerm(amount=1, unit=TermUnit.MONTH)
    assert (stored.license_start, stored.license_end) == (date(2026, 1, 31), date(2026, 2, 28))
    assert stored.fields == ContractFields(
        tech_owner="이기술", inspection=InspectionCycle.SEMIANNUAL, note="여러 줄\n메모"
    )
    assert stored.renewed_from_id is None
    assert stored.ended_at is None
    assert (stored.created_by, stored.updated_by) == (KIM, KIM)
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


async def test_a_not_issued_contract_has_no_period_columns(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal)

    stored = await contract_case.repository.get(contract.id)

    assert stored.status is ContractStatus.NOT_ISSUED
    assert (stored.term, stored.license_start, stored.license_end) == (None, None, None)


async def test_an_ended_contract_keeps_its_end_time_and_period(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal, status="ended", start=date(2026, 1, 1))

    stored = await contract_case.repository.get(contract.id)

    assert stored.status is ContractStatus.ENDED
    assert stored.ended_at == NOW
    assert stored.license_end == date(2026, 12, 31)


async def test_a_deal_can_have_many_contracts(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal, status="issued_renewal", renewed_from=first.id)
    third = await contract_case.contract(deal)

    assert await contract_case.repository.count_of_deal(deal.id) == 3
    assert {first.id, second.id, third.id} == set(await contract_case.row_ids())


async def test_renewed_from_id_is_stored(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal, status="issued_renewal", renewed_from=first.id)

    assert (await contract_case.repository.get(second.id)).renewed_from_id == first.id


async def test_add_with_a_taken_id_raises_already_exists(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")

    with pytest.raises(AlreadyExistsError):
        await contract_case.add(make_contract(deal_code=deal.id, entity_id=first.id))


async def test_add_to_a_missing_deal_raises_deal_not_found(contract_case: ContractCase) -> None:
    with pytest.raises(DealNotFoundError):
        await contract_case.add(make_contract(deal_code=make_deal_code("ZZ99")))


async def test_add_with_a_missing_user_raises_invalid_reference(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    ghost = make_contract(deal_code=deal.id, by=uid("lcr-ghost"))

    with pytest.raises(InvalidReferenceError):
        await contract_case.repository.add(ghost)  # 사용자 행을 만들지 않고 바로 저장한다


async def test_get_missing_raises_not_found(contract_case: ContractCase) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.repository.get(LicenseContractId(new_id()))


async def test_get_row_carries_the_deal_values_and_attachment_count(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal(
        customer="넥스트", solution="ERP", vendor="SAP", partner="한빛", owner="lcr-owner"
    )
    contract = await contract_case.contract(deal)
    await contract_case.attach(contract, "a.pdf")
    await contract_case.attach(contract, "b.pdf")

    row = await contract_case.repository.get_row(contract.id)

    assert row.contract.id == contract.id
    assert row.attachment_count == 2
    assert row.deal.deal_code == deal.id
    assert row.deal.deal_name == deal.details.name
    assert (row.deal.customer, row.deal.product, row.deal.partner) == ("넥스트", "ERP", "한빛")
    assert row.deal.vendor is not None
    assert row.deal.vendor.name == "SAP"
    assert row.deal.owner_user_id == uid("lcr-owner")


async def test_get_row_without_vendor_and_partner_has_none(contract_case: ContractCase) -> None:
    deal = await contract_case.deal(vendor=None, partner=None)
    contract = await contract_case.contract(deal)

    row = await contract_case.repository.get_row(contract.id)

    assert row.deal.vendor is None
    assert row.deal.partner is None
    assert row.attachment_count == 0


async def test_get_row_missing_raises_not_found(contract_case: ContractCase) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.repository.get_row(LicenseContractId(new_id()))


async def test_update_saves_status_period_fields_and_audit_columns(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal, by=KIM)
    await contract_case.user("lcr-park")  # 수정자 행(FK)
    stored = await contract_case.repository.get(contract.id)
    stored.issue(start=date(2026, 3, 1), term=LicenseTerm(2, TermUnit.YEAR), by=PARK, now=later())
    stored.revise(
        fields=ContractFields("새 담당", InspectionCycle.MONTHLY, "새 메모"), by=PARK, now=later(5)
    )

    await contract_case.repository.update(stored)

    saved = await contract_case.repository.get(contract.id)
    assert saved.status is ContractStatus.ISSUED_NEW
    assert saved.term == LicenseTerm(2, TermUnit.YEAR)
    assert (saved.license_start, saved.license_end) == (date(2026, 3, 1), date(2028, 2, 29))
    assert saved.fields == ContractFields("새 담당", InspectionCycle.MONTHLY, "새 메모")
    assert (saved.updated_by, saved.updated_at) == (PARK, later(5))
    assert (saved.created_by, saved.created_at) == (KIM, NOW)


async def test_update_saves_the_end_time_of_an_ended_contract(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal, status="issued_new")
    await contract_case.user("lcr-kim")  # 수정자 행(FK)
    stored = await contract_case.repository.get(contract.id)
    stored.end(by=KIM, now=later())

    await contract_case.repository.update(stored)

    saved = await contract_case.repository.get(contract.id)
    assert saved.status is ContractStatus.ENDED
    assert saved.ended_at == later()


async def test_update_does_not_change_the_deal_or_the_renewal_link_or_the_creator(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    other = await contract_case.deal()
    origin = await contract_case.contract(deal, status="ended")
    contract = await contract_case.contract(deal, by=KIM)
    stored = await contract_case.repository.get(contract.id)
    stored.deal_code = other.id  # 불변 필드를 바꿔 넘겨도 저장되지 않는다
    stored.renewed_from_id = origin.id
    stored.created_by = PARK
    stored.revise(fields=ContractFields("x", InspectionCycle.NONE, ""), by=KIM, now=later())

    await contract_case.repository.update(stored)

    saved = await contract_case.repository.get(contract.id)
    assert saved.deal_code == deal.id
    assert saved.renewed_from_id is None
    assert saved.created_by == KIM
    assert saved.fields.tech_owner == "x"


async def test_update_missing_raises_not_found(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()

    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.repository.update(make_contract(deal_code=deal.id))


async def test_delete_removes_the_contract_and_its_attachment_rows(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal)
    sibling = await contract_case.contract(deal, status="ended")
    attachment = await contract_case.attach(contract)
    kept = await contract_case.attach(sibling, "kept.pdf")

    await contract_case.repository.delete(contract.id)

    assert await contract_case.row_ids() == [sibling.id]
    assert list(await contract_case.files.list_by_contract(contract.id)) == []
    assert [a.id for a in await contract_case.files.list_by_contract(sibling.id)] == [kept.id]
    assert attachment.id != kept.id


async def test_delete_clears_the_renewal_link_of_the_successor(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal, status="issued_renewal", renewed_from=first.id)

    await contract_case.repository.delete(first.id)

    assert (await contract_case.repository.get(second.id)).renewed_from_id is None


async def test_delete_missing_raises_not_found(contract_case: ContractCase) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.repository.delete(LicenseContractId(new_id()))


async def test_count_of_deal_counts_only_that_deal(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    other = await contract_case.deal()
    await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal)
    await contract_case.contract(other)

    assert await contract_case.repository.count_of_deal(deal.id) == 2
    assert await contract_case.repository.count_of_deal(other.id) == 1
    assert await contract_case.repository.count_of_deal(make_deal_code("NONE")) == 0


async def test_delete_of_deal_removes_only_that_deals_contracts_and_attachment_rows(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    other = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal)
    outside = await contract_case.contract(other)
    await contract_case.attach(first, "a.pdf")
    await contract_case.attach(second, "b.pdf")
    kept = await contract_case.attach(outside, "c.pdf")

    removed = await contract_case.repository.delete_of_deal(deal.id)

    assert removed == 2
    assert await contract_case.repository.count_of_deal(deal.id) == 0
    assert await contract_case.row_ids() == [outside.id]
    assert [a.id for a in await contract_case.files.list_by_contract(first.id)] == []
    assert [a.id for a in await contract_case.files.list_by_contract(outside.id)] == [kept.id]


async def test_ids_of_deal_returns_that_deals_contract_ids_ascending(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    other = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended", entity_id=500)
    second = await contract_case.contract(deal, entity_id=300)
    third = await contract_case.contract(deal, status="issued_new", entity_id=400)
    await contract_case.contract(other, entity_id=100)

    ids = await contract_case.repository.ids_of_deal(deal.id)

    assert list(ids) == [second.id, third.id, first.id]


async def test_ids_of_deal_without_contracts_is_empty(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()

    assert list(await contract_case.repository.ids_of_deal(deal.id)) == []
    assert list(await contract_case.repository.ids_of_deal(make_deal_code("NONE"))) == []


async def test_ids_of_deal_reflects_a_deletion(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    gone = await contract_case.contract(deal, entity_id=10)
    kept = await contract_case.contract(deal, entity_id=20)
    await contract_case.repository.delete(gone.id)

    assert list(await contract_case.repository.ids_of_deal(deal.id)) == [kept.id]


async def test_delete_of_deal_without_contracts_returns_zero(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()

    assert await contract_case.repository.delete_of_deal(deal.id) == 0


async def test_issued_of_deal_returns_the_issued_contract_or_none(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    assert await contract_case.repository.issued_of_deal(deal.id) is None
    await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal)
    assert await contract_case.repository.issued_of_deal(deal.id) is None
    issued = await contract_case.contract(deal, status="issued_renewal")

    found = await contract_case.repository.issued_of_deal(deal.id)

    assert found is not None
    assert found.id == issued.id


async def test_deleting_the_deal_removes_its_contracts_and_attachments(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    survivor_deal = await contract_case.deal()
    contract = await contract_case.contract(deal, status="issued_new")
    survivor = await contract_case.contract(survivor_deal)
    await contract_case.attach(contract)

    await contract_case.deals.delete(deal.id)

    assert await contract_case.row_ids() == [survivor.id]
    assert list(await contract_case.files.list_by_contract(contract.id)) == []
