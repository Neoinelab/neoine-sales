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
    await contract_case.deal_case.revise(
        deal.id,
        details=make_deal_details(
            owner_user_id=new_owner, vendor_id=new_vendor.id, solution="새제품"
        ),
        customer_id=new_customer.id,
    )
    await contract_case.deal_case.replace_partner(deal.id, new_partner.id, later())

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


async def test_removing_the_partner_and_vendor_shows_them_as_empty(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal(vendor="SAP", partner="파트너")
    contract = await contract_case.contract(deal)
    await contract_case.deal_case.replace_partner(deal.id, None, NOW)
    await contract_case.deal_case.revise(
        deal.id, details=make_deal_details(owner_user_id=deal.details.owner_user_id, vendor_id=None)
    )

    row = await contract_case.repository.get_row(contract.id)

    assert row.deal.partner is None
    assert row.deal.vendor is None


async def test_contract_row_deal_is_won_reflects_the_current_forecast(
    contract_case: ContractCase,
) -> None:
    from tests.factories import make_sync  # noqa: PLC0415

    won = await contract_case.deal(forecast_key="won")
    open_deal = await contract_case.deal()
    lost = await contract_case.deal(forecast_key="lost")
    won_contract = await contract_case.contract(won)
    open_contract = await contract_case.contract(open_deal)
    lost_contract = await contract_case.contract(lost)

    assert (await contract_case.repository.get_row(won_contract.id)).deal.is_won is True
    assert (await contract_case.repository.get_row(open_contract.id)).deal.is_won is False
    assert (await contract_case.repository.get_row(lost_contract.id)).deal.is_won is False
    rows = await contract_case.repository.search(LicenseContractQuery(limit=200))
    listed = {r.contract.id: r.deal.is_won for r in rows}
    assert listed == {won_contract.id: True, open_contract.id: False, lost_contract.id: False}

    await contract_case.deal_case.revise(open_deal.id, sync=make_sync("contract_completed", "won"))
    await contract_case.deal_case.revise(won.id, sync=make_sync("poc_completed", "commit"))

    assert (await contract_case.repository.get_row(open_contract.id)).deal.is_won is True
    assert (await contract_case.repository.get_row(won_contract.id)).deal.is_won is False
