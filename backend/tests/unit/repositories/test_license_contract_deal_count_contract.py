"""Deal 쪽의 계약 건수(AC9·AC21): 목록·상세 행의 license_contract_count와 deletion_impact.

Fake와 SQL 구현에 같은 테스트. 건수는 그 Deal의 계약 수(종료 포함)다.
"""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealDeletionImpact, DealQuery
from tests.factories import later

if TYPE_CHECKING:
    from tests.unit.repositories.license_contract_case import ContractCase


async def test_deal_list_item_has_license_contract_count(contract_case: ContractCase) -> None:
    """Deal 목록·단건 항목은 그 Deal의 계약 건수를 담는다.

    테스트 코드: LC-030
    """
    # given: 계약 2건·0건·1건인 Deal
    with_two = await contract_case.deal(customer="둘")
    without = await contract_case.deal(customer="없음")
    other = await contract_case.deal(customer="하나")
    await contract_case.contract(with_two, status="ended")
    await contract_case.contract(with_two)
    await contract_case.contract(other)

    # when: Deal을 조회한다
    item_with_two = await contract_case.deals.get_item(with_two.id)
    item_without = await contract_case.deals.get_item(without.id)
    listed = await contract_case.deals.search(DealQuery(limit=200))

    # then: Deal마다 계약 건수가 다르다
    assert item_with_two.license_contract_count == 2
    assert item_without.license_contract_count == 0
    assert {item.deal.id: item.license_contract_count for item in listed} == {
        with_two.id: 2,
        without.id: 0,
        other.id: 1,
    }


async def test_deletion_impact_counts_license_contracts(contract_case: ContractCase) -> None:
    """삭제 영향은 그 Deal의 계약 건수만 센다.

    테스트 코드: LC-079
    """
    # given: 계약 2건(첨부 1개)인 Deal과 다른 Deal
    deal = await contract_case.deal()
    other = await contract_case.deal()
    first = await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal)
    await contract_case.contract(other)
    await contract_case.attach(first)

    # when: 삭제 영향을 읽는다
    impact = await contract_case.deals.deletion_impact(deal.id)

    # then: 계약 건수 2, 계약 첨부는 Deal 첨부에 세지 않는다
    assert impact == DealDeletionImpact(
        history_count=impact.history_count,
        action_count=0,
        attachment_count=0,  # 계약 첨부는 Deal 첨부 건수에 섞이지 않는다
        license_contract_count=2,
    )


async def test_deletion_impact_without_contracts_is_zero(contract_case: ContractCase) -> None:
    """계약이 없는 Deal의 삭제 영향 계약 건수는 0이다.

    테스트 코드: LC-079
    """
    # given: 계약 없는 Deal
    deal = await contract_case.deal()

    # when: 삭제 영향을 읽는다
    license_contract_count = (
        await contract_case.deals.deletion_impact(deal.id)
    ).license_contract_count
    # then: 계약 건수 0
    assert license_contract_count == 0


async def test_deal_list_item_has_issued_license_contract_flag(contract_case: ContractCase) -> None:
    """Deal 항목의 발급 여부는 발급 상태 계약이 있을 때만 true다.

    테스트 코드: LC-030
    """
    # given: 계약 없음·미발급·발급·갱신·종료 계약뿐인 Deal들
    none = await contract_case.deal(customer="계약없음")
    waiting = await contract_case.deal(customer="미발급")
    issued = await contract_case.deal(customer="발급")
    renewed = await contract_case.deal(customer="갱신")
    ended = await contract_case.deal(customer="종료")
    await contract_case.contract(waiting)
    await contract_case.contract(issued, status="issued_new")
    await contract_case.contract(renewed, status="ended")
    await contract_case.contract(renewed, status="issued_renewal")
    await contract_case.contract(ended, status="ended")

    # when: Deal 목록을 읽는다
    flags = {
        item.deal.id: item.has_issued_license_contract
        for item in await contract_case.deals.search(DealQuery(limit=200))
    }

    # then: 발급·갱신 계약이 있는 Deal만 true다
    assert flags == {
        none.id: False,
        waiting.id: False,
        issued.id: True,
        renewed.id: True,
        ended.id: False,
    }
    for deal, expected in ((none, False), (issued, True), (ended, False)):
        assert (await contract_case.deals.get_item(deal.id)).has_issued_license_contract is expected


async def test_the_flag_turns_false_when_the_issued_contract_ends_or_is_deleted(
    contract_case: ContractCase,
) -> None:
    """발급 계약이 종료되거나 삭제되면 Deal의 발급 여부가 false가 된다.

    테스트 코드: LC-030
    """
    # given: 발급(신규) 계약이 있는 Deal(처음엔 true)
    deal = await contract_case.deal()
    contract = await contract_case.contract(deal, status="issued_new")
    assert (await contract_case.deals.get_item(deal.id)).has_issued_license_contract is True

    ended = await contract_case.repository.get(contract.id)
    ended.end(by=contract.updated_by, now=later(1))
    # when: 계약을 종료하고, 이어 삭제한다
    await contract_case.repository.update(ended)
    # then: 단계마다 발급 여부가 false다
    assert (await contract_case.deals.get_item(deal.id)).has_issued_license_contract is False

    await contract_case.repository.delete(contract.id)
    assert (await contract_case.deals.get_item(deal.id)).has_issued_license_contract is False


async def test_the_flag_belongs_to_each_deal_separately(contract_case: ContractCase) -> None:
    """발급 여부는 Deal마다 따로다.

    테스트 코드: LC-030
    """
    # given: 발급 계약이 있는 Deal과 미발급 계약뿐인 Deal
    with_issued = await contract_case.deal()
    other = await contract_case.deal()
    await contract_case.contract(with_issued, status="issued_new")
    await contract_case.contract(other)

    # when: 각 Deal을 조회한다
    has_issued_license_contract = (
        await contract_case.deals.get_item(with_issued.id)
    ).has_issued_license_contract
    # then: 각각 true, false다
    assert has_issued_license_contract is True
    assert (await contract_case.deals.get_item(other.id)).has_issued_license_contract is False
