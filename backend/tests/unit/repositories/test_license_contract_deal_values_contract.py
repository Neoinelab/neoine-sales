"""계약 행은 Deal의 현재 값을 읽는다(Q1).

Deal의 고객·Vendor·Solution·파트너·Owner를 바꾸면 계약 행의 값도 바뀐다. 계약에는 그 값을
저장하지 않는다. Fake와 SQL 구현에 같은 테스트.
"""

from typing import TYPE_CHECKING

from app.application.ports.license_contract_repository import LicenseContractQuery
from tests.factories import NOW, later, make_deal_details
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.license_contract_case import ContractCase


async def test_search_row_reflects_current_deal_values(contract_case: ContractCase) -> None:
    """계약 행은 Deal의 현재 값(고객·제품·파트너·Vendor·담당)을 보여 준다.

    테스트 코드: LC-028
    """
    # given: 이전 값의 Deal과 계약, 새 담당·Vendor·고객·파트너
    deal = await contract_case.deal(
        customer="이전고객",
        solution="이전제품",
        vendor="SAP",
        partner="이전파트너",
        owner="lcv-old",
    )
    contract = await contract_case.contract(deal)
    new_owner = await contract_case.user("lcv-new", "새담당")
    new_vendor = await contract_case.deal_case.new_vendor("Oracle")
    new_customer = await contract_case.deal_case.new_contact(
        company="새고객", name="새담당자", email="new@lcv.example"
    )
    from app.domain.contact.values import ContactKind  # noqa: PLC0415

    new_partner = await contract_case.deal_case.new_contact(
        ContactKind.PARTNER, company="새파트너", name="새파트너담당", email="np@lcv.example"
    )
    stored = await contract_case.deals.get(deal.id)
    # when: Deal 값을 바꾸고 계약 행을 읽는다
    await contract_case.deal_case.revise(
        deal.id,
        details=make_deal_details(
            owner_user_id=new_owner, vendor_id=new_vendor.id, solution="새제품"
        ),
        customer_id=new_customer.id,
    )
    await contract_case.deal_case.replace_partner(deal.id, new_partner.id, later())

    # then: 행과 검색 조건이 새 Deal 값을 따른다
    row = await contract_case.repository.get_row(contract.id)

    assert stored.details.solution == "이전제품"
    assert row.deal.customer == "새고객"
    assert row.deal.product == "새제품"
    assert row.deal.partner == "새파트너"
    assert row.deal.vendor is not None
    assert row.deal.vendor.name == "Oracle"
    assert row.deal.owner_user_id == new_owner
    assert (await contract_case.row_ids(customer="새고객")) == [contract.id]
    assert (await contract_case.row_ids(customer="이전고객")) == []
    assert (await contract_case.row_ids(owner_user_id=new_owner)) == [contract.id]
    assert (await contract_case.row_ids(owner_user_id=uid("lcv-old"))) == []


async def test_removing_the_partner_empties_it_and_changing_the_vendor_shows_the_new_name(
    contract_case: ContractCase,
) -> None:
    """파트너 연결을 끊으면 계약 행의 파트너가 비고 Vendor를 바꾸면 새 Vendor 이름이 보인다.

    테스트 코드: LC-028
    """
    # given: Vendor와 파트너가 있는 Deal의 계약
    deal = await contract_case.deal(vendor="SAP", partner="파트너")
    contract = await contract_case.contract(deal)
    # when: 파트너 연결을 끊고 Vendor를 Oracle로 바꾼다
    oracle = await contract_case.deal_case.new_vendor("Oracle")
    await contract_case.deal_case.replace_partner(deal.id, None, NOW)
    await contract_case.deal_case.revise(
        deal.id,
        details=make_deal_details(owner_user_id=deal.details.owner_user_id, vendor_id=oracle.id),
    )

    # then: 행의 파트너는 None이고 Vendor는 Oracle이다
    row = await contract_case.repository.get_row(contract.id)

    assert row.deal.partner is None
    assert row.deal.vendor is not None
    assert row.deal.vendor.name == "Oracle"


async def test_contract_row_deal_is_won_reflects_the_current_forecast(
    contract_case: ContractCase,
) -> None:
    """계약 행의 Won 여부는 Deal의 현재 Forecast를 따른다.

    테스트 코드: LC-028
    """
    # given: Won·Open·Lost Deal의 계약
    from tests.factories import make_sync  # noqa: PLC0415

    won = await contract_case.deal(forecast_key="won")
    open_deal = await contract_case.deal()
    lost = await contract_case.deal(forecast_key="lost")
    won_contract = await contract_case.contract(won)
    open_contract = await contract_case.contract(open_deal)
    lost_contract = await contract_case.contract(lost)

    # when: 행을 읽고 Forecast를 바꾼 뒤 다시 읽는다
    assert (await contract_case.repository.get_row(won_contract.id)).deal.is_won is True
    assert (await contract_case.repository.get_row(open_contract.id)).deal.is_won is False
    assert (await contract_case.repository.get_row(lost_contract.id)).deal.is_won is False
    rows = await contract_case.repository.search(LicenseContractQuery(limit=200))
    listed = {r.contract.id: r.deal.is_won for r in rows}
    assert listed == {won_contract.id: True, open_contract.id: False, lost_contract.id: False}

    await contract_case.deal_case.revise(open_deal.id, sync=make_sync("contract_completed", "won"))
    await contract_case.deal_case.revise(won.id, sync=make_sync("poc_completed", "commit"))

    # then: Won만 true이고 바뀐 Forecast가 반영된다
    assert (await contract_case.repository.get_row(open_contract.id)).deal.is_won is True
    assert (await contract_case.repository.get_row(won_contract.id)).deal.is_won is False
