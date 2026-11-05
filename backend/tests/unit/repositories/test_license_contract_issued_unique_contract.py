"""한 Deal에 발급 상태 계약은 하나뿐(AC3): Fake와 SQL(부분 유니크 인덱스)이 같은 오류를 낸다."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.license_contract.errors import LicenseAlreadyIssuedError
from app.domain.license_contract.values import ContractStatus, LicenseTerm, TermUnit
from tests.factories import later
from tests.factories_license_contract import make_contract
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from tests.unit.repositories.license_contract_case import ContractCase

MESSAGE = "이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다."


@pytest.mark.parametrize("existing", ["issued_new", "issued_renewal"])
@pytest.mark.parametrize("incoming", ["issued_new", "issued_renewal"])
async def test_partial_unique_rejects_second_issued_for_deal(
    contract_case: ContractCase,
    existing: str,
    incoming: str,
) -> None:
    deal = await contract_case.deal()
    await contract_case.contract(deal, status=existing)

    with raises_with(LicenseAlreadyIssuedError, MESSAGE):
        await contract_case.add(make_contract(deal_code=deal.id, status=incoming))


async def test_the_transaction_stays_usable_after_the_unique_violation(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="issued_new")
    with pytest.raises(LicenseAlreadyIssuedError):
        await contract_case.add(make_contract(deal_code=deal.id, status="issued_renewal"))

    assert await contract_case.repository.count_of_deal(deal.id) == 1
    waiting = await contract_case.contract(deal)  # 미발급 계약은 이어서 저장된다
    assert set(await contract_case.row_ids()) == {first.id, waiting.id}


async def test_update_to_an_issued_status_is_rejected_while_another_is_issued(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    await contract_case.contract(deal, status="issued_new")
    waiting = await contract_case.contract(deal)
    stored = await contract_case.repository.get(waiting.id)
    stored.issue(
        start=date(2027, 1, 1),
        term=LicenseTerm(1, TermUnit.YEAR),
        by=stored.updated_by,
        now=later(),
    )
    assert stored.status is ContractStatus.ISSUED_NEW

    with pytest.raises(LicenseAlreadyIssuedError):
        await contract_case.repository.update(stored)


async def test_ended_and_not_issued_contracts_do_not_count(contract_case: ContractCase) -> None:
    deal = await contract_case.deal()
    await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal)
    await contract_case.contract(deal)

    issued = await contract_case.contract(deal, status="issued_new")

    found = await contract_case.repository.issued_of_deal(deal.id)
    assert found is not None
    assert found.id == issued.id
    assert await contract_case.repository.count_of_deal(deal.id) == 5


async def test_two_deals_may_each_have_an_issued_contract(contract_case: ContractCase) -> None:
    first = await contract_case.deal()
    second = await contract_case.deal()

    await contract_case.contract(first, status="issued_new")
    await contract_case.contract(second, status="issued_new")

    assert await contract_case.total(status=ContractStatus.ISSUED_NEW) == 2


async def test_renewal_order_end_the_previous_then_add_the_new_succeeds(
    contract_case: ContractCase,
) -> None:
    deal = await contract_case.deal()
    previous = await contract_case.contract(deal, status="issued_new")
    stored = await contract_case.repository.get(previous.id)
    stored.end(by=stored.updated_by, now=later())
    await contract_case.repository.update(stored)

    renewal = await contract_case.contract(deal, status="issued_renewal", renewed_from=previous.id)

    issued = await contract_case.repository.issued_of_deal(deal.id)
    assert issued is not None
    assert issued.id == renewal.id
