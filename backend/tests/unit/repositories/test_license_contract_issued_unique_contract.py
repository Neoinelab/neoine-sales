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
    """한 Deal에 발급 상태 계약을 하나 더 저장하면 거절된다.

    테스트 코드: LC-042
    """
    # given: 발급 상태 계약이 있는 Deal
    deal = await contract_case.deal()
    await contract_case.contract(deal, status=existing)

    # when: 발급 상태 계약을 하나 더 저장한다
    with raises_with(LicenseAlreadyIssuedError, MESSAGE):
        await contract_case.add(make_contract(deal_code=deal.id, status=incoming))
    # then: LicenseAlreadyIssuedError 문구


async def test_the_transaction_stays_usable_after_the_unique_violation(
    contract_case: ContractCase,
) -> None:
    """중복 발급 거절 뒤에도 같은 트랜잭션에서 저장을 이어갈 수 있다.

    테스트 코드: LC-042
    """
    # given: 발급(신규) 계약이 있는 Deal
    deal = await contract_case.deal()
    first = await contract_case.contract(deal, status="issued_new")
    # when: 중복 발급 저장이 거절된 뒤 미발급 계약을 저장한다
    with pytest.raises(LicenseAlreadyIssuedError):
        await contract_case.add(make_contract(deal_code=deal.id, status="issued_renewal"))

    # then: 계약이 이어서 저장된다
    assert await contract_case.repository.count_of_deal(deal.id) == 1
    waiting = await contract_case.contract(deal)  # 미발급 계약은 이어서 저장된다
    assert set(await contract_case.row_ids()) == {first.id, waiting.id}


async def test_update_to_an_issued_status_is_rejected_while_another_is_issued(
    contract_case: ContractCase,
) -> None:
    """다른 계약이 발급 상태인 동안 수정으로 발급 상태가 되는 것도 거절된다.

    테스트 코드: LC-042
    """
    # given: 발급(신규) 계약과 미발급 계약이 있는 Deal
    deal = await contract_case.deal()
    await contract_case.contract(deal, status="issued_new")
    waiting = await contract_case.contract(deal)
    stored = await contract_case.repository.get(waiting.id)
    # when: 미발급 계약을 발급 상태로 바꿔 저장한다
    stored.issue(
        start=date(2027, 1, 1),
        term=LicenseTerm(1, TermUnit.YEAR),
        by=stored.updated_by,
        now=later(),
    )
    # then: LicenseAlreadyIssuedError
    assert stored.status is ContractStatus.ISSUED_NEW

    with pytest.raises(LicenseAlreadyIssuedError):
        await contract_case.repository.update(stored)


async def test_ended_and_not_issued_contracts_do_not_count(contract_case: ContractCase) -> None:
    """종료·미발급 계약은 발급 유일성에 세지 않는다.

    테스트 코드: LC-042
    """
    # given: 종료 2건, 미발급 2건, 발급 1건인 Deal
    deal = await contract_case.deal()
    await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal, status="ended")
    await contract_case.contract(deal)
    await contract_case.contract(deal)

    issued = await contract_case.contract(deal, status="issued_new")

    # when: Deal의 발급 계약을 조회한다
    found = await contract_case.repository.issued_of_deal(deal.id)
    # then: 발급 계약은 1건이고 전체 계약은 5건이다
    assert found is not None
    assert found.id == issued.id
    assert await contract_case.repository.count_of_deal(deal.id) == 5


async def test_two_deals_may_each_have_an_issued_contract(contract_case: ContractCase) -> None:
    """Deal마다 발급 계약을 하나씩 가질 수 있다.

    테스트 코드: LC-042
    """
    # given: 서로 다른 두 Deal
    first = await contract_case.deal()
    second = await contract_case.deal()

    await contract_case.contract(first, status="issued_new")
    # when: 각 Deal에 발급 계약을 저장한다
    await contract_case.contract(second, status="issued_new")

    # then: 발급 계약이 2건이다
    assert await contract_case.total(status=ContractStatus.ISSUED_NEW) == 2


async def test_renewal_order_end_the_previous_then_add_the_new_succeeds(
    contract_case: ContractCase,
) -> None:
    """이전 계약을 종료한 뒤 새 발급(갱신) 행을 저장하면 성공한다.

    테스트 코드: LC-049
    """
    # given: 발급(신규) 계약이 있는 Deal
    deal = await contract_case.deal()
    previous = await contract_case.contract(deal, status="issued_new")
    stored = await contract_case.repository.get(previous.id)
    # when: 이전 계약을 종료·저장하고 새 갱신 계약을 저장한다
    stored.end(by=stored.updated_by, now=later())
    await contract_case.repository.update(stored)

    renewal = await contract_case.contract(deal, status="issued_renewal", renewed_from=previous.id)

    issued = await contract_case.repository.issued_of_deal(deal.id)
    # then: 발급 계약은 새 갱신 계약 하나다
    assert issued is not None
    assert issued.id == renewal.id
