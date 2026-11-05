"""발급·갱신(AC3·AC4·AC12·AC13): 발급 상태는 Deal당 최대 하나이고 종료일은 서버가 계산한다.

발급·갱신은 Won인 Deal에서만 된다(AC27). 그 규칙은 test_license_contract_won_required.py."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.license_contract.errors import (
    ContractTransitionError,
    LicenseAlreadyIssuedError,
    LicenseContractNotFoundError,
)
from app.domain.license_contract.values import (
    ContractFields,
    ContractStatus,
    InspectionCycle,
    LicenseTerm,
    TermUnit,
)
from tests.support.expect import raises_with
from tests.support.ids import MISSING_ID
from tests.unit.application.license_contract_env import KIM, PARK

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv

ALREADY_ISSUED = "이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다."
NOT_ISSUED_ONLY = "미발급 계약만 발급할 수 있습니다."
ISSUED_ONLY = "발급 상태 계약만 갱신할 수 있습니다."


async def test_issue_not_issued_contract_stores_period_and_computed_end(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    data = contract_env.issue_input(date(2026, 1, 31), 1, "month", tech_owner="이기술")

    await contract_env.issue.execute(contract.id, data, PARK)

    stored = await contract_env.stored(contract.id)
    assert stored.status is ContractStatus.ISSUED_NEW
    assert stored.license_start == date(2026, 1, 31)
    assert stored.license_end == date(2026, 2, 28)
    assert stored.term == LicenseTerm(amount=1, unit=TermUnit.MONTH)
    assert stored.updated_by == PARK.user_id
    assert stored.created_by == KIM.user_id


async def test_issue_applies_the_contract_fields_sent_with_it(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    data = contract_env.issue_input(tech_owner="이기술", inspection="quarterly", note="메모")

    await contract_env.issue.execute(contract.id, data, KIM)

    assert (await contract_env.stored(contract.id)).fields == ContractFields(
        tech_owner="이기술", inspection=InspectionCycle.QUARTERLY, note="메모"
    )


@pytest.mark.parametrize("status", ["issued_new", "issued_renewal", "ended"])
async def test_issue_non_not_issued_raises_transition_error(
    contract_env: ContractEnv, status: str
) -> None:
    code = await contract_env.won_deal_without_contract()
    contract = await contract_env.seed_contract(code, status=status)

    with raises_with(ContractTransitionError, NOT_ISSUED_ONLY):
        await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)

    assert (await contract_env.stored(contract.id)).status is ContractStatus(status)


async def test_issue_when_deal_has_other_issued_raises_already_issued(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract()
    await contract_env.seed_contract(code, status="issued_new")
    waiting = await contract_env.seed_contract(code)

    with raises_with(LicenseAlreadyIssuedError, ALREADY_ISSUED):
        await contract_env.issue.execute(waiting.id, contract_env.issue_input(), KIM)

    stored = await contract_env.stored(waiting.id)
    assert stored.status is ContractStatus.NOT_ISSUED
    assert stored.license_start is None


async def test_issue_is_allowed_when_the_other_contract_is_ended(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract()
    await contract_env.seed_contract(code, status="ended")
    waiting = await contract_env.seed_contract(code)

    await contract_env.issue.execute(waiting.id, contract_env.issue_input(), KIM)

    assert (await contract_env.stored(waiting.id)).status is ContractStatus.ISSUED_NEW


async def test_issue_in_another_deal_is_not_blocked(contract_env: ContractEnv) -> None:
    other_code = await contract_env.won_deal_without_contract()
    await contract_env.seed_contract(other_code, status="issued_new")
    code = await contract_env.won_deal_without_contract()
    waiting = await contract_env.seed_contract(code)

    await contract_env.issue.execute(waiting.id, contract_env.issue_input(), KIM)

    assert (await contract_env.stored(waiting.id)).status is ContractStatus.ISSUED_NEW


async def test_issue_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.issue.execute(MISSING_ID, contract_env.issue_input(), KIM)  # type: ignore[arg-type]


async def test_renew_creates_a_new_row_and_ends_the_previous_one(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(
        code, status="issued_new", tech_owner="이전", start=date(2026, 1, 1)
    )
    data = contract_env.issue_input(date(2027, 1, 1), 2, "year", tech_owner="새 담당", note="갱신")

    await contract_env.renew.execute(previous.id, data, PARK)

    ended = await contract_env.stored(previous.id)
    assert ended.status is ContractStatus.ENDED
    assert ended.ended_at == contract_env.clock.now()
    assert (ended.license_start, ended.license_end) == (date(2026, 1, 1), date(2026, 12, 31))
    (renewal,) = [c for c in await contract_env.contracts_of(code) if c.id != previous.id]
    assert renewal.status is ContractStatus.ISSUED_RENEWAL
    assert renewal.renewed_from_id == previous.id
    assert (renewal.license_start, renewal.license_end) == (date(2027, 1, 1), date(2028, 12, 31))
    assert renewal.fields.tech_owner == "새 담당"
    assert renewal.fields.note == "갱신"
    assert renewal.created_by == renewal.updated_by == PARK.user_id


async def test_renew_keeps_single_issued_per_deal(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(code, status="issued_new")

    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)
    (second,) = [c for c in await contract_env.contracts_of(code) if c.status.is_issued]
    await contract_env.renew.execute(second.id, contract_env.issue_input(date(2028, 1, 1)), KIM)

    contracts = await contract_env.contracts_of(code)
    assert len(contracts) == 3
    assert [c.status for c in contracts if c.status.is_issued] == [ContractStatus.ISSUED_RENEWAL]
    assert sorted(c.status.value for c in contracts) == ["ended", "ended", "issued_renewal"]


@pytest.mark.parametrize("status", ["not_issued", "ended"])
async def test_renew_not_issued_or_ended_raises(contract_env: ContractEnv, status: str) -> None:
    code = await contract_env.won_deal_without_contract()
    contract = await contract_env.seed_contract(code, status=status)

    with raises_with(ContractTransitionError, ISSUED_ONLY):
        await contract_env.renew.execute(contract.id, contract_env.issue_input(), KIM)

    assert len(await contract_env.contracts_of(code)) == 1
    assert (await contract_env.stored(contract.id)).status is ContractStatus(status)


async def test_renew_leaves_the_attachments_on_the_previous_contract(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(code, status="issued_new")
    attachment = await contract_env.seed_file(previous)

    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)

    assert [a.id for a in await contract_env.files_of(previous.id)] == [attachment.id]
    (renewal,) = [c for c in await contract_env.contracts_of(code) if c.id != previous.id]
    assert await contract_env.files_of(renewal.id) == []


async def test_renew_commits_once_so_both_changes_land_together(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(code, status="issued_new")
    before = contract_env.uow.commits

    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)

    assert contract_env.uow.commits == before + 1


async def test_contract_changes_do_not_touch_the_deal(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    history_before = await contract_env.env.history_rows(code)
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    updated_before = (await contract_env.uow.deals.get(DealCode(code))).updated_at
    contract_env.clock.advance(3600)

    await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)

    assert await contract_env.env.history_rows(code) == history_before
    assert (await contract_env.uow.deals.get(DealCode(code))).updated_at == updated_before
