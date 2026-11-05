"""발급·갱신은 Won인 Deal에서만 된다(AC27).

Won이 아닌 Deal의 계약을 발급하거나 갱신하면 409(InvalidStateError)이고 계약은 바뀌지 않는다. 검사
순서는 404(계약 없음) -> 409 Won 아님 -> 409 전이 불가 -> 409 이미 발급이다. 계약 칸 수정·종료·
첨부·admin 삭제는 Deal 상태와 무관하게 된다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.license_contract.errors import LicenseContractNotFoundError
from app.domain.license_contract.values import ContractFields, ContractStatus, InspectionCycle
from tests.support.expect import raises_with
from tests.support.ids import MISSING_ID
from tests.unit.application.license_contract_env import BOSS, KIM

if TYPE_CHECKING:
    from app.domain.common.errors import InvalidStateError
    from tests.unit.application.license_contract_env import ContractEnv

DEAL_NOT_WON = "Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다."
NEW_FIELDS = ContractFields(tech_owner="이기술", inspection=InspectionCycle.YEARLY, note="메모")


def _requires_won() -> type[InvalidStateError]:
    from app.domain.license_contract.errors import LicenseRequiresWonError  # noqa: PLC0415

    return LicenseRequiresWonError


async def test_issue_on_a_non_won_deal_raises_requires_won_and_changes_nothing(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)

    with raises_with(_requires_won(), DEAL_NOT_WON):
        await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)

    stored = await contract_env.stored(contract.id)
    assert stored.status is ContractStatus.NOT_ISSUED
    assert stored.license_start is None


async def test_issue_on_a_lost_deal_raises_requires_won(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal(forecast_key="lost")
    contract = await contract_env.seed_contract(code)

    with raises_with(_requires_won(), DEAL_NOT_WON):
        await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)


async def test_renew_on_a_non_won_deal_raises_requires_won_and_adds_no_row(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    issued = await contract_env.seed_contract(code, status="issued_new")

    with raises_with(_requires_won(), DEAL_NOT_WON):
        await contract_env.renew.execute(issued.id, contract_env.issue_input(), KIM)

    assert [c.id for c in await contract_env.contracts_of(code)] == [issued.id]
    assert (await contract_env.stored(issued.id)).status is ContractStatus.ISSUED_NEW


async def test_the_won_check_comes_before_the_transition_and_already_issued_checks(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    await contract_env.seed_contract(code, status="issued_new")
    waiting = await contract_env.seed_contract(code)
    ended = await contract_env.seed_contract(code, status="ended")

    with raises_with(_requires_won(), DEAL_NOT_WON):  # 이미 발급이 있어도 Won 아님이 먼저
        await contract_env.issue.execute(waiting.id, contract_env.issue_input(), KIM)
    with raises_with(_requires_won(), DEAL_NOT_WON):  # 종료 계약이어도 Won 아님이 먼저
        await contract_env.issue.execute(ended.id, contract_env.issue_input(), KIM)
    with raises_with(_requires_won(), DEAL_NOT_WON):
        await contract_env.renew.execute(ended.id, contract_env.issue_input(), KIM)


async def test_missing_contract_is_not_found_before_the_won_check(
    contract_env: ContractEnv,
) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.issue.execute(MISSING_ID, contract_env.issue_input(), KIM)  # type: ignore[arg-type]
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.renew.execute(MISSING_ID, contract_env.issue_input(), KIM)  # type: ignore[arg-type]


async def test_a_contract_kept_after_leaving_won_cannot_be_issued_until_won_again(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=False)  # 유지

    with raises_with(_requires_won(), DEAL_NOT_WON):
        await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)

    from app.application.deal.inputs import DealChangeInput  # noqa: PLC0415
    from tests.unit.application.license_contract_env import CLOSING  # noqa: PLC0415

    again = DealChangeInput(field="forecast_key", value="won", resolution=CLOSING)
    await contract_env.env.apply.execute(code, again, KIM)
    await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)

    assert (await contract_env.stored(contract.id)).status is ContractStatus.ISSUED_NEW


async def test_end_and_update_on_a_non_won_deal_are_allowed(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    issued = await contract_env.seed_contract(code, status="issued_new")
    waiting = await contract_env.seed_contract(code)

    await contract_env.update.execute(waiting.id, NEW_FIELDS, KIM)
    await contract_env.end.execute(issued.id, KIM)

    assert (await contract_env.stored(waiting.id)).fields == NEW_FIELDS
    assert (await contract_env.stored(issued.id)).status is ContractStatus.ENDED


async def test_attachments_and_admin_delete_on_a_non_won_deal_are_allowed(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code, status="issued_new")

    outcome = await contract_env.put_file(contract.id, KIM)
    await contract_env.delete_file.execute(outcome.attachment.id, KIM)
    await contract_env.delete.execute(contract.id, BOSS)

    assert await contract_env.contracts_of(code) == []
