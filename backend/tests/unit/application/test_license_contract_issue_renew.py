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
    """미발급 계약을 발급하면 발급(신규)가 되고 시작일·기간·계산된 종료일이 저장된다.

    테스트 코드: LC-039
    """
    # given: Won Deal의 미발급 계약(등록자 KIM)
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    data = contract_env.issue_input(date(2026, 1, 31), 1, "month", tech_owner="이기술")

    # when: PARK가 시작일 2026-01-31, 1개월로 발급한다
    await contract_env.issue.execute(contract.id, data, PARK)

    stored = await contract_env.stored(contract.id)
    # then: 발급(신규), 종료일 2026-02-28, 수정자는 PARK, 등록자는 KIM 그대로
    assert stored.status is ContractStatus.ISSUED_NEW
    assert stored.license_start == date(2026, 1, 31)
    assert stored.license_end == date(2026, 2, 28)
    assert stored.term == LicenseTerm(amount=1, unit=TermUnit.MONTH)
    assert stored.updated_by == PARK.user_id
    assert stored.created_by == KIM.user_id


async def test_issue_applies_the_contract_fields_sent_with_it(contract_env: ContractEnv) -> None:
    """발급 요청에 담긴 계약 칸이 함께 저장된다.

    테스트 코드: LC-039
    """
    # given: Won Deal의 미발급 계약
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    data = contract_env.issue_input(tech_owner="이기술", inspection="quarterly", note="메모")

    # when: 기술담당·점검주기·Note와 함께 발급한다
    await contract_env.issue.execute(contract.id, data, KIM)

    # then: 계약 칸이 요청값으로 저장된다
    assert (await contract_env.stored(contract.id)).fields == ContractFields(
        tech_owner="이기술", inspection=InspectionCycle.QUARTERLY, note="메모"
    )


@pytest.mark.parametrize("status", ["issued_new", "issued_renewal", "ended"])
async def test_issue_non_not_issued_raises_transition_error(
    contract_env: ContractEnv, status: str
) -> None:
    """미발급이 아닌 계약은 발급할 수 없고 상태가 바뀌지 않는다.

    테스트 코드: LC-041
    """
    # given: Won Deal의 발급(신규·갱신)·종료 계약
    code = await contract_env.won_deal_without_contract()
    contract = await contract_env.seed_contract(code, status=status)

    # when: 발급한다
    with raises_with(ContractTransitionError, NOT_ISSUED_ONLY):
        await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)

    # then: ContractTransitionError 문구, 상태는 그대로
    assert (await contract_env.stored(contract.id)).status is ContractStatus(status)


async def test_issue_when_deal_has_other_issued_raises_already_issued(
    contract_env: ContractEnv,
) -> None:
    """같은 Deal에 다른 발급 계약이 있으면 발급할 수 없다.

    테스트 코드: LC-042
    """
    # given: 발급(신규) 계약과 미발급 계약이 있는 Won Deal
    code = await contract_env.won_deal_without_contract()
    await contract_env.seed_contract(code, status="issued_new")
    waiting = await contract_env.seed_contract(code)

    # when: 미발급 계약을 발급한다
    with raises_with(LicenseAlreadyIssuedError, ALREADY_ISSUED):
        await contract_env.issue.execute(waiting.id, contract_env.issue_input(), KIM)

    stored = await contract_env.stored(waiting.id)
    # then: LicenseAlreadyIssuedError 문구, 미발급 그대로
    assert stored.status is ContractStatus.NOT_ISSUED
    assert stored.license_start is None


async def test_issue_is_allowed_when_the_other_contract_is_ended(
    contract_env: ContractEnv,
) -> None:
    """같은 Deal의 다른 계약이 종료 상태면 발급할 수 있다.

    테스트 코드: LC-042
    """
    # given: 종료 계약과 미발급 계약이 있는 Won Deal
    code = await contract_env.won_deal_without_contract()
    await contract_env.seed_contract(code, status="ended")
    waiting = await contract_env.seed_contract(code)

    # when: 미발급 계약을 발급한다
    await contract_env.issue.execute(waiting.id, contract_env.issue_input(), KIM)

    # then: 발급(신규)가 된다
    assert (await contract_env.stored(waiting.id)).status is ContractStatus.ISSUED_NEW


async def test_issue_in_another_deal_is_not_blocked(contract_env: ContractEnv) -> None:
    """다른 Deal의 발급 계약은 발급을 막지 않는다.

    테스트 코드: LC-042
    """
    # given: 다른 Deal에는 발급 계약이, 이 Deal에는 미발급 계약이 있다
    other_code = await contract_env.won_deal_without_contract()
    await contract_env.seed_contract(other_code, status="issued_new")
    code = await contract_env.won_deal_without_contract()
    waiting = await contract_env.seed_contract(code)

    # when: 이 Deal의 미발급 계약을 발급한다
    await contract_env.issue.execute(waiting.id, contract_env.issue_input(), KIM)

    # then: 발급(신규)가 된다
    assert (await contract_env.stored(waiting.id)).status is ContractStatus.ISSUED_NEW


async def test_issue_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    """없는 계약 id를 발급하면 404다.

    테스트 코드: LC-043
    """
    # when: 없는 계약 id로 발급한다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.issue.execute(MISSING_ID, contract_env.issue_input(), KIM)  # type: ignore[arg-type]
    # then: LicenseContractNotFoundError


async def test_renew_creates_a_new_row_and_ends_the_previous_one(
    contract_env: ContractEnv,
) -> None:
    """갱신하면 이전 계약은 종료되고 새 발급(갱신) 계약이 생긴다.

    테스트 코드: LC-049
    """
    # given: 종료일 2026-12-31인 Won Deal의 발급(신규) 계약
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(
        code, status="issued_new", tech_owner="이전", start=date(2026, 1, 1)
    )
    data = contract_env.issue_input(date(2027, 1, 1), 2, "year", tech_owner="새 담당", note="갱신")

    # when: PARK가 2027-01-01부터 2년, 새 담당·메모로 갱신한다
    await contract_env.renew.execute(previous.id, data, PARK)

    ended = await contract_env.stored(previous.id)
    # then: 이전은 종료(기간 유지), 새 행은 갱신·원본 연결·기간·칸·등록자 PARK
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
    """갱신을 거듭해도 발급 상태 계약은 Deal당 1건이다.

    테스트 코드: LC-049
    """
    # given: Won Deal의 발급(신규) 계약
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(code, status="issued_new")

    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)
    (second,) = [c for c in await contract_env.contracts_of(code) if c.status.is_issued]
    # when: 두 번 연속 갱신한다
    await contract_env.renew.execute(second.id, contract_env.issue_input(date(2028, 1, 1)), KIM)

    contracts = await contract_env.contracts_of(code)
    # then: 계약 3건 중 발급 상태는 발급(갱신) 1건뿐이다
    assert len(contracts) == 3
    assert [c.status for c in contracts if c.status.is_issued] == [ContractStatus.ISSUED_RENEWAL]
    assert sorted(c.status.value for c in contracts) == ["ended", "ended", "issued_renewal"]


@pytest.mark.parametrize("status", ["not_issued", "ended"])
async def test_renew_not_issued_or_ended_raises(contract_env: ContractEnv, status: str) -> None:
    """미발급·종료 계약은 갱신할 수 없고 새 행도 생기지 않는다.

    테스트 코드: LC-050
    """
    # given: Won Deal의 미발급 또는 종료 계약
    code = await contract_env.won_deal_without_contract()
    contract = await contract_env.seed_contract(code, status=status)

    # when: 갱신한다
    with raises_with(ContractTransitionError, ISSUED_ONLY):
        await contract_env.renew.execute(contract.id, contract_env.issue_input(), KIM)

    # then: ContractTransitionError 문구, 계약은 1건 그대로
    assert len(await contract_env.contracts_of(code)) == 1
    assert (await contract_env.stored(contract.id)).status is ContractStatus(status)


async def test_renew_leaves_the_attachments_on_the_previous_contract(
    contract_env: ContractEnv,
) -> None:
    """갱신해도 첨부는 이전 계약에 남고 새 계약에는 없다.

    테스트 코드: LC-052
    """
    # given: 첨부 1개가 있는 발급(신규) 계약
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(code, status="issued_new")
    attachment = await contract_env.seed_file(previous)

    # when: 갱신한다
    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)

    # then: 이전 계약 첨부 목록은 그대로, 새 계약 첨부는 0개
    assert [a.id for a in await contract_env.files_of(previous.id)] == [attachment.id]
    (renewal,) = [c for c in await contract_env.contracts_of(code) if c.id != previous.id]
    assert await contract_env.files_of(renewal.id) == []


async def test_renew_commits_once_so_both_changes_land_together(
    contract_env: ContractEnv,
) -> None:
    """갱신은 이전 종료와 새 행 추가를 커밋 1번으로 함께 저장한다."""
    # given: 발급(신규) 계약과 현재 커밋 횟수
    code = await contract_env.won_deal_without_contract()
    previous = await contract_env.seed_contract(code, status="issued_new")
    before = contract_env.uow.commits

    # when: 갱신한다
    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)

    # then: 커밋이 한 번만 늘었다
    assert contract_env.uow.commits == before + 1


async def test_contract_changes_do_not_touch_the_deal(contract_env: ContractEnv) -> None:
    """발급은 Deal History와 Deal 수정 시각을 바꾸지 않는다.

    테스트 코드: LC-035
    """
    # given: Won Deal의 미발급 계약, 처음의 이력과 수정 시각
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    history_before = await contract_env.env.history_rows(code)
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    updated_before = (await contract_env.uow.deals.get(DealCode(code))).updated_at
    contract_env.clock.advance(3600)

    # when: 한 시간 뒤 발급한다
    await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)

    # then: Deal 이력과 수정 시각은 그대로다
    assert await contract_env.env.history_rows(code) == history_before
    assert (await contract_env.uow.deals.get(DealCode(code))).updated_at == updated_before
