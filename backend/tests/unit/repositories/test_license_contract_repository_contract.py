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
    """계약을 저장하고 읽으면 모든 필드가 그대로다."""
    # given: Deal과 모든 필드가 채워진 발급(신규) 계약
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
    # when: 저장하고 다시 읽는다
    await contract_case.add(contract)

    stored = await contract_case.repository.get(contract.id)

    # then: id·Deal·상태·기간·칸·등록자·시각이 같다
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
    assert stored.ended_on is None
    assert (stored.created_by, stored.updated_by) == (KIM, KIM)
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


async def test_a_not_issued_contract_has_no_period_columns(contract_case: ContractCase) -> None:
    """미발급 계약은 기간 칸이 모두 비어 있다."""
    # given: 미발급 계약
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal)

    # when: 읽는다
    stored = await contract_case.repository.get(contract.id)

    # then: 기간 네 칸이 None이다
    assert stored.status is ContractStatus.NOT_ISSUED
    assert (stored.term, stored.license_start, stored.license_end) == (None, None, None)


async def test_an_ended_contract_keeps_its_end_date_and_period(contract_case: ContractCase) -> None:
    """종료 계약은 종료일과 기간을 가진다."""
    # given: 시작일이 있는 종료 계약
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal, status="ended", start=date(2026, 1, 1))

    # when: 읽는다
    stored = await contract_case.repository.get(contract.id)

    # then: 상태 ended, ended_on(날짜), 종료일이 그대로다
    assert stored.status is ContractStatus.ENDED
    assert stored.ended_on == NOW.astimezone().date()
    assert stored.license_end == date(2026, 12, 31)


async def test_a_deal_can_have_many_contracts(contract_case: ContractCase) -> None:
    """한 Deal에 계약이 여러 개 있을 수 있다."""
    # given: Deal
    deal = await contract_case.deal()
    # when: 종료·갱신·미발급 계약 3건을 저장한다
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal, status="issued_renewal", renewed_from=first.id)
    third = await contract_case.contract(deal)

    # then: 건수 3이고 모두 검색된다
    assert await contract_case.repository.count_of_deal(deal.id) == 3
    assert {first.id, second.id, third.id} == set(await contract_case.row_ids())


async def test_renewed_from_id_is_stored(contract_case: ContractCase) -> None:
    """갱신 원본 id가 저장된다."""
    # given: 종료 계약 하나
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    # when: 그것을 원본으로 하는 갱신 계약을 저장한다
    second = await contract_case.contract(deal, status="issued_renewal", renewed_from=first.id)

    # then: renewed_from_id가 원본 id다
    assert (await contract_case.repository.get(second.id)).renewed_from_id == first.id


async def test_add_with_a_taken_id_raises_already_exists(contract_case: ContractCase) -> None:
    """이미 있는 id로 저장하면 AlreadyExistsError다."""
    # given: 계약 하나
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")

    # when: 같은 id로 다시 저장한다
    with pytest.raises(AlreadyExistsError):
        await contract_case.add(make_contract(deal_code=deal.id, entity_id=first.id))
    # then: AlreadyExistsError


async def test_add_to_a_missing_deal_raises_deal_not_found(contract_case: ContractCase) -> None:
    """없는 Deal에 계약을 저장하면 DealNotFoundError다."""
    # when: 없는 Deal 코드로 저장한다
    with pytest.raises(DealNotFoundError):
        await contract_case.add(make_contract(deal_code=make_deal_code("ZZ99")))
    # then: DealNotFoundError


async def test_add_with_a_missing_user_raises_invalid_reference(
    contract_case: ContractCase,
) -> None:
    """없는 사용자를 등록자로 저장하면 InvalidReferenceError다."""
    # given: 없는 사용자가 등록자인 계약
    deal = await contract_case.deal()
    ghost = make_contract(deal_code=deal.id, by=uid("lcr-ghost"))

    # when: 저장한다
    with pytest.raises(InvalidReferenceError):
        await contract_case.repository.add(ghost)  # 사용자 행을 만들지 않고 바로 저장한다
    # then: InvalidReferenceError


async def test_get_missing_raises_not_found(contract_case: ContractCase) -> None:
    """없는 계약을 읽으면 LicenseContractNotFoundError다.

    테스트 코드: LC-029
    """
    # when: 없는 id로 읽는다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.repository.get(LicenseContractId(new_id()))
    # then: LicenseContractNotFoundError


async def test_get_row_carries_the_deal_values_and_attachment_count(
    contract_case: ContractCase,
) -> None:
    """행 조회는 Deal 값과 첨부 수를 함께 돌려준다.

    테스트 코드: LC-028
    """
    # given: 첨부 2개가 있는 계약
    deal = await contract_case.deal(
        customer="넥스트", product="ERP", vendor="SAP", partner="한빛", owner="lcr-owner"
    )
    contract = await contract_case.contract(deal)
    await contract_case.attach(contract, "a.pdf")
    await contract_case.attach(contract, "b.pdf")

    # when: 행을 읽는다
    row = await contract_case.repository.get_row(contract.id)

    # then: Deal 값과 첨부 수 2가 담긴다
    assert row.contract.id == contract.id
    assert row.attachment_count == 2
    assert row.deal.deal_code == deal.id
    assert row.deal.deal_name == deal.details.name
    assert (row.deal.customer, row.deal.product, row.deal.partner) == ("넥스트", "ERP", "한빛")
    assert row.deal.vendor is not None
    assert row.deal.vendor.name == "SAP"
    assert row.deal.owner_user_id == uid("lcr-owner")


async def test_get_row_without_a_partner_has_none(contract_case: ContractCase) -> None:
    """파트너가 없는 Deal의 행은 파트너가 None이고 Vendor는 Deal의 Vendor다.

    테스트 코드: LC-028
    """
    # given: Vendor SAP이고 파트너가 없는 Deal의 계약
    deal = await contract_case.deal(vendor="SAP", partner=None)
    contract = await contract_case.contract(deal)

    # when: 행을 읽는다
    row = await contract_case.repository.get_row(contract.id)

    # then: vendor는 SAP, partner는 None, 첨부 수 0
    assert row.deal.vendor is not None
    assert row.deal.vendor.name == "SAP"
    assert row.deal.partner is None
    assert row.attachment_count == 0


async def test_get_row_missing_raises_not_found(contract_case: ContractCase) -> None:
    """없는 계약의 행 조회는 LicenseContractNotFoundError다.

    테스트 코드: LC-029
    """
    # when: 없는 id로 행을 읽는다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.repository.get_row(LicenseContractId(new_id()))
    # then: LicenseContractNotFoundError


async def test_update_saves_status_period_fields_and_audit_columns(
    contract_case: ContractCase,
) -> None:
    """수정은 상태·기간·칸·수정자·시각을 저장한다."""
    # given: 계약과 수정자 사용자
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal, by=KIM)
    await contract_case.user("lcr-park")  # 수정자 행(FK)
    stored = await contract_case.repository.get(contract.id)
    stored.issue(start=date(2026, 3, 1), term=LicenseTerm(2, TermUnit.YEAR), by=PARK, now=later())
    stored.revise(
        fields=ContractFields("새 담당", InspectionCycle.MONTHLY, "새 메모"), by=PARK, now=later(5)
    )

    # when: 발급·칸 수정한 계약을 저장한다
    await contract_case.repository.update(stored)

    # then: 다시 읽은 값에 반영돼 있다
    saved = await contract_case.repository.get(contract.id)
    assert saved.status is ContractStatus.ISSUED_NEW
    assert saved.term == LicenseTerm(2, TermUnit.YEAR)
    assert (saved.license_start, saved.license_end) == (date(2026, 3, 1), date(2028, 2, 29))
    assert saved.fields == ContractFields("새 담당", InspectionCycle.MONTHLY, "새 메모")
    assert (saved.updated_by, saved.updated_at) == (PARK, later(5))
    assert (saved.created_by, saved.created_at) == (KIM, NOW)


async def test_update_saves_the_end_date_of_an_ended_contract(contract_case: ContractCase) -> None:
    """종료한 계약을 저장하면 종료일이 남는다."""
    # given: 발급(신규) 계약
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal, status="issued_new")
    await contract_case.user("lcr-kim")  # 수정자 행(FK)
    stored = await contract_case.repository.get(contract.id)
    stored.end(by=KIM, now=later())

    # when: 종료해 저장한다
    await contract_case.repository.update(stored)

    # then: 상태 ended와 ended_on(요청의 업무 날짜)이 저장된다
    saved = await contract_case.repository.get(contract.id)
    assert saved.status is ContractStatus.ENDED
    assert saved.ended_on == later().astimezone().date()


async def test_update_does_not_change_the_deal_or_the_renewal_link_or_the_creator(
    contract_case: ContractCase,
) -> None:
    """수정은 Deal·갱신 원본·등록자를 바꾸지 않는다."""
    # given: 다른 Deal과 원본 후보가 있는 계약
    deal = await contract_case.deal()
    other = await contract_case.deal()
    origin = await contract_case.contract(deal, status="ended")
    contract = await contract_case.contract(deal, by=KIM)
    stored = await contract_case.repository.get(contract.id)
    stored.deal_code = other.id  # 불변 필드를 바꿔 넘겨도 저장되지 않는다
    stored.renewed_from_id = origin.id
    stored.created_by = PARK
    stored.revise(fields=ContractFields("x", InspectionCycle.NONE, ""), by=KIM, now=later())

    # when: 불변 필드를 바꿔 수정 저장한다
    await contract_case.repository.update(stored)

    # then: Deal·원본 연결·등록자는 그대로, 칸만 바뀐다
    saved = await contract_case.repository.get(contract.id)
    assert saved.deal_code == deal.id
    assert saved.renewed_from_id is None
    assert saved.created_by == KIM
    assert saved.fields.tech_owner == "x"


async def test_update_missing_raises_not_found(contract_case: ContractCase) -> None:
    """없는 계약을 수정하면 LicenseContractNotFoundError다."""
    # given: Deal
    deal = await contract_case.deal()

    # when: 저장된 적 없는 계약을 수정한다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.repository.update(make_contract(deal_code=deal.id))
    # then: LicenseContractNotFoundError


async def test_delete_removes_the_contract_and_its_attachment_rows(
    contract_case: ContractCase,
) -> None:
    """계약을 삭제하면 그 계약의 첨부 행도 지워진다.

    테스트 코드: LC-058
    """
    # given: 첨부가 있는 계약과 다른 계약
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal)
    sibling = await contract_case.contract(deal, status="ended")
    attachment = await contract_case.attach(contract)
    kept = await contract_case.attach(sibling, "kept.pdf")

    # when: 계약을 삭제한다
    await contract_case.repository.delete(contract.id)

    # then: 다른 계약과 그 첨부만 남는다
    assert await contract_case.row_ids() == [sibling.id]
    assert list(await contract_case.files.list_by_contract(contract.id)) == []
    assert [a.id for a in await contract_case.files.list_by_contract(sibling.id)] == [kept.id]
    assert attachment.id != kept.id


async def test_delete_clears_the_renewal_link_of_the_successor(
    contract_case: ContractCase,
) -> None:
    """원본을 삭제하면 후속 계약의 원본 연결이 비워진다.

    테스트 코드: LC-060
    """
    # given: 원본 계약과 그 갱신 계약
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal, status="issued_renewal", renewed_from=first.id)

    # when: 원본을 삭제한다
    await contract_case.repository.delete(first.id)

    # then: 후속 계약의 renewed_from_id가 None이다
    assert (await contract_case.repository.get(second.id)).renewed_from_id is None


async def test_delete_missing_raises_not_found(contract_case: ContractCase) -> None:
    """없는 계약을 삭제하면 LicenseContractNotFoundError다.

    테스트 코드: LC-029
    """
    # when: 없는 id를 삭제한다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_case.repository.delete(LicenseContractId(new_id()))
    # then: LicenseContractNotFoundError


async def test_count_of_deal_counts_only_that_deal(contract_case: ContractCase) -> None:
    """Deal별 계약 건수는 그 Deal의 계약만 센다."""
    # given: 계약 2건인 Deal, 1건인 Deal
    deal = await contract_case.deal()
    other = await contract_case.deal()
    await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal)
    await contract_case.contract(other)

    # when: Deal별 건수를 센다
    result = await contract_case.repository.count_of_deal(deal.id)
    # then: 2, 1, 없는 Deal은 0이다
    assert result == 2
    assert await contract_case.repository.count_of_deal(other.id) == 1
    assert await contract_case.repository.count_of_deal(make_deal_code("NONE")) == 0


async def test_delete_of_deal_removes_only_that_deals_contracts_and_attachment_rows(
    contract_case: ContractCase,
) -> None:
    """Deal의 계약 일괄 삭제는 그 Deal의 계약과 첨부 행만 지운다.

    테스트 코드: LC-080
    """
    # given: 계약 2건(첨부 포함)인 Deal과 다른 Deal의 계약
    deal = await contract_case.deal()
    other = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    second = await contract_case.contract(deal)
    outside = await contract_case.contract(other)
    await contract_case.attach(first, "a.pdf")
    await contract_case.attach(second, "b.pdf")
    kept = await contract_case.attach(outside, "c.pdf")

    # when: 그 Deal의 계약을 일괄 삭제한다
    removed = await contract_case.repository.delete_of_deal(deal.id)

    # then: 삭제 건수 2, 다른 Deal의 계약·첨부는 그대로다
    assert removed == 2
    assert await contract_case.repository.count_of_deal(deal.id) == 0
    assert await contract_case.row_ids() == [outside.id]
    assert [a.id for a in await contract_case.files.list_by_contract(first.id)] == []
    assert [a.id for a in await contract_case.files.list_by_contract(outside.id)] == [kept.id]


async def test_ids_of_deal_returns_that_deals_contract_ids_ascending(
    contract_case: ContractCase,
) -> None:
    """Deal의 계약 id 목록은 오름차순이다."""
    # given: id가 뒤섞인 계약들과 다른 Deal의 계약
    deal = await contract_case.deal()
    other = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended", entity_id=500)
    second = await contract_case.contract(deal, entity_id=300)
    third = await contract_case.contract(deal, status="issued_new", entity_id=400)
    await contract_case.contract(other, entity_id=100)

    # when: Deal의 계약 id를 읽는다
    ids = await contract_case.repository.ids_of_deal(deal.id)

    # then: 그 Deal의 id만 오름차순으로 온다
    assert list(ids) == [second.id, third.id, first.id]


async def test_ids_of_deal_without_contracts_is_empty(contract_case: ContractCase) -> None:
    """계약이 없는 Deal의 id 목록은 비어 있다."""
    # given: 계약 없는 Deal
    deal = await contract_case.deal()

    # when: 계약 id를 읽는다
    actual = list(await contract_case.repository.ids_of_deal(deal.id))
    # then: 빈 목록이다
    assert actual == []
    assert list(await contract_case.repository.ids_of_deal(make_deal_code("NONE"))) == []


async def test_ids_of_deal_reflects_a_deletion(contract_case: ContractCase) -> None:
    """삭제한 계약은 id 목록에서 빠진다."""
    # given: 계약 둘
    deal = await contract_case.deal()
    gone = await contract_case.contract(deal, entity_id=10)
    kept = await contract_case.contract(deal, entity_id=20)
    # when: 하나를 삭제한다
    await contract_case.repository.delete(gone.id)

    # then: 남은 id만 온다
    assert list(await contract_case.repository.ids_of_deal(deal.id)) == [kept.id]


async def test_delete_of_deal_without_contracts_returns_zero(contract_case: ContractCase) -> None:
    """계약 없는 Deal의 일괄 삭제는 0을 돌려준다."""
    # given: 계약 없는 Deal
    deal = await contract_case.deal()

    # when: 일괄 삭제한다
    result = await contract_case.repository.delete_of_deal(deal.id)
    # then: 0이다
    assert result == 0


async def test_issued_of_deal_returns_the_issued_contract_or_none(
    contract_case: ContractCase,
) -> None:
    """Deal의 발급 계약 조회는 발급 상태 계약 또는 None을 돌려준다.

    테스트 코드: LC-030
    """
    # given: 계약이 없다가 종료·미발급·발급(갱신)이 차례로 생기는 Deal
    deal = await contract_case.deal()
    # when: 발급 계약을 조회한다
    assert await contract_case.repository.issued_of_deal(deal.id) is None
    await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal)
    assert await contract_case.repository.issued_of_deal(deal.id) is None
    issued = await contract_case.contract(deal, status="issued_renewal")

    found = await contract_case.repository.issued_of_deal(deal.id)

    # then: 발급 계약이 생기기 전엔 None, 생긴 뒤엔 그 계약
    assert found is not None
    assert found.id == issued.id


async def test_deleting_the_deal_removes_its_contracts_and_attachments(
    contract_case: ContractCase,
) -> None:
    """Deal을 삭제하면 그 Deal의 계약과 첨부 행이 함께 지워진다.

    테스트 코드: LC-080
    """
    # given: 계약·첨부가 있는 Deal과 다른 Deal의 계약
    deal = await contract_case.deal()
    survivor_deal = await contract_case.deal()
    contract = await contract_case.contract(deal, status="issued_new")
    survivor = await contract_case.contract(survivor_deal)
    await contract_case.attach(contract)

    # when: Deal을 삭제한다
    await contract_case.deals.delete(deal.id)

    # then: 그 Deal의 계약·첨부 행만 사라진다
    assert await contract_case.row_ids() == [survivor.id]
    assert list(await contract_case.files.list_by_contract(contract.id)) == []
