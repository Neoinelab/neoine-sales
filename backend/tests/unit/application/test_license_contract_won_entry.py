"""Won 진입 자동 생성(AC6).

Deal 등록·폼 수정·인라인 변경·Action 등록 어느 경로든 Won이 되고 그 Deal에 계약이 하나도 없으면
같은 트랜잭션에서 미발급 계약 1건을 만든다. 이미 있으면(종료 포함) 만들지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import DealChangeInput
from app.application.deal_action.inputs import StatusChangeInput
from app.domain.common.errors import InvalidValueError
from app.domain.license_contract.values import ContractFields, ContractStatus, InspectionCycle
from tests.factories import make_register_input
from tests.factories_deal import make_patch
from tests.unit.application.license_contract_env import CLOSING, KIM, PARK

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv

EMPTY_FIELDS = ContractFields(tech_owner="", inspection=InspectionCycle.NONE, note="")


async def test_register_deal_as_won_creates_not_issued_contract(contract_env: ContractEnv) -> None:
    """Won으로 등록한 Deal에는 미발급 계약 1건이 자동으로 생긴다.

    테스트 코드: LC-001
    """
    # when: Status contract_completed, Forecast won으로 Deal을 등록한다
    code = await contract_env.won_deal(KIM)

    (contract,) = await contract_env.contracts_of(code)
    # then: 계약 1건이 미발급이고 기간 없음, 빈 칸 기본값, 등록자·수정자는 KIM이다
    assert contract.status is ContractStatus.NOT_ISSUED
    assert (contract.term, contract.license_start, contract.license_end) == (None, None, None)
    assert contract.fields == EMPTY_FIELDS
    assert contract.renewed_from_id is None
    assert contract.created_by == contract.updated_by == KIM.user_id


async def test_register_deal_not_won_creates_no_contract(contract_env: ContractEnv) -> None:
    """Won이 아닌 Deal을 등록하면 계약이 생기지 않는다.

    테스트 코드: LC-002
    """
    # when: Won이 아닌 Deal을 등록한다
    code = await contract_env.open_deal()

    # then: 그 Deal의 계약은 0건이다
    assert await contract_env.contracts_of(code) == []


async def test_registering_the_contract_is_in_the_same_transaction_as_the_deal(
    contract_env: ContractEnv,
) -> None:
    """계약 자동 생성은 Deal 등록과 같은 트랜잭션(커밋 1번)이다."""
    # given: 등록 전 커밋 횟수
    before = contract_env.uow.commits

    # when: Won Deal을 등록한다
    await contract_env.won_deal(KIM)

    # then: 커밋이 한 번만 늘었다
    assert contract_env.uow.commits == before + 1


async def test_update_deal_to_won_creates_contract_when_none(contract_env: ContractEnv) -> None:
    """계약이 없는 Deal을 폼 수정으로 Won으로 바꾸면 미발급 계약이 생긴다.

    테스트 코드: LC-003
    """
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()

    # when: Deal 폼 수정으로 Status·Forecast를 Won으로 바꾼다
    await contract_env.env.update.execute(
        code, make_patch(status_key="contract_completed", forecast_key="won"), PARK
    )

    (contract,) = await contract_env.contracts_of(code)
    # then: 계약 1건이 미발급이고 등록자는 요청자 PARK다
    assert contract.status is ContractStatus.NOT_ISSUED
    assert contract.created_by == PARK.user_id


async def test_update_deal_to_won_skips_when_contract_exists(contract_env: ContractEnv) -> None:
    """종료 계약만 있는 Deal을 다시 Won으로 바꿔도 새 계약은 생기지 않는다.

    테스트 코드: LC-004
    """
    # given: 종료 계약 1건만 있는 Won이 아닌 Deal
    code = await contract_env.open_deal()
    ended = await contract_env.seed_contract(code, status="ended")

    # when: Deal 폼 수정으로 Won으로 바꾼다
    await contract_env.env.update.execute(
        code, make_patch(status_key="contract_completed", forecast_key="won"), KIM
    )

    # then: 계약은 기존 종료 계약 1건 그대로다
    assert [c.id for c in await contract_env.contracts_of(code)] == [ended.id]


async def test_update_deal_without_a_won_change_creates_nothing(contract_env: ContractEnv) -> None:
    """Won과 무관한 폼 수정은 계약을 만들지 않는다."""
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()

    # when: 이름만 바꾸는 폼 수정을 한다
    await contract_env.env.update.execute(code, make_patch(name="이름만 변경"), KIM)

    # then: 계약은 여전히 0건이다
    assert await contract_env.contracts_of(code) == []


async def test_update_deal_that_stays_won_creates_no_second_contract(
    contract_env: ContractEnv,
) -> None:
    """Won을 유지하는 폼 수정은 두 번째 계약을 만들지 않는다.

    테스트 코드: LC-004
    """
    # given: 계약 1건이 있는 Won Deal
    code = await contract_env.won_deal(KIM)

    # when: 이름만 바꾸는 폼 수정을 한다
    await contract_env.env.update.execute(code, make_patch(name="이름 변경"), KIM)

    # then: 계약은 1건 그대로다
    assert len(await contract_env.contracts_of(code)) == 1


async def test_apply_change_forecast_won_creates_contract(contract_env: ContractEnv) -> None:
    """인라인 변경으로 Forecast를 won으로 바꾸면 미발급 계약이 생긴다.

    테스트 코드: LC-003
    """
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()
    change = DealChangeInput(field="forecast_key", value="won", resolution=CLOSING)

    # when: 인라인 변경으로 Forecast를 won으로 바꾼다
    await contract_env.env.apply.execute(code, change, KIM)

    (contract,) = await contract_env.contracts_of(code)
    # then: 계약 1건이 미발급이고 등록자는 요청자 KIM이다
    assert contract.status is ContractStatus.NOT_ISSUED
    assert contract.created_by == KIM.user_id


async def test_apply_change_status_contract_completed_creates_contract(
    contract_env: ContractEnv,
) -> None:
    """인라인 변경으로 Status를 contract_completed로 바꾸면 계약이 생긴다.

    테스트 코드: LC-003
    """
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()
    change = DealChangeInput(field="status_key", value="contract_completed", resolution=CLOSING)

    # when: 인라인 변경으로 Status를 contract_completed로 바꾼다
    await contract_env.env.apply.execute(code, change, KIM)

    # then: 계약이 1건 생긴다
    assert len(await contract_env.contracts_of(code)) == 1


async def test_apply_change_that_does_not_reach_won_creates_nothing(
    contract_env: ContractEnv,
) -> None:
    """Won에 닿지 않는 인라인 변경은 계약을 만들지 않는다."""
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()
    change = DealChangeInput(field="forecast_key", value="commit")

    # when: Forecast를 commit으로 바꾼다
    await contract_env.env.apply.execute(code, change, KIM)

    # then: 계약은 여전히 0건이다
    assert await contract_env.contracts_of(code) == []


async def test_register_action_status_change_to_won_creates_contract(
    contract_env: ContractEnv,
) -> None:
    """Action 등록의 Status 변경으로 Won이 되면 미발급 계약이 생긴다.

    테스트 코드: LC-003
    """
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()
    change = StatusChangeInput(field="forecast_key", value="won", resolution=CLOSING)
    contract_env.clock.advance(60)

    # when: Forecast를 won으로 바꾸는 status_changes와 함께 Action을 등록한다
    await contract_env.register_action.execute(code, make_register_input((change,)), KIM)

    (contract,) = await contract_env.contracts_of(code)
    # then: 계약 1건이 미발급이고 등록자는 KIM이다
    assert contract.status is ContractStatus.NOT_ISSUED
    assert contract.created_by == KIM.user_id


async def test_register_action_with_two_changes_that_end_at_won_creates_one_contract(
    contract_env: ContractEnv,
) -> None:
    """여러 단계 변경이 처음과 끝만 비교해 Won이 되면 계약은 1건 생긴다.

    테스트 코드: LC-003
    """
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()
    first = StatusChangeInput(field="status_key", value="contract_completed", resolution=CLOSING)
    second = StatusChangeInput(field="forecast_key", value="won")
    contract_env.clock.advance(60)

    # when: Status→Forecast 두 단계 변경(끝이 Won)으로 Action을 등록한다
    await contract_env.register_action.execute(code, make_register_input((first, second)), KIM)

    # then: 계약이 정확히 1건이다
    assert len(await contract_env.contracts_of(code)) == 1


async def test_register_action_without_status_change_creates_nothing(
    contract_env: ContractEnv,
) -> None:
    """상태 변경이 없는 Action 등록은 계약을 만들지 않는다."""
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()
    contract_env.clock.advance(60)

    # when: status_changes 없이 Action을 등록한다
    await contract_env.register_action.execute(code, make_register_input(action="미팅"), KIM)

    # then: 계약은 여전히 0건이다
    assert await contract_env.contracts_of(code) == []


async def test_won_then_left_with_keep_then_won_again_keeps_the_single_contract(
    contract_env: ContractEnv,
) -> None:
    """유지로 남긴 계약이 있는 Deal을 다시 Won으로 바꿔도 계약은 1건이다.

    테스트 코드: LC-004
    """
    # given: Won을 벗어날 때 유지로 남긴 미발급 계약 1건이 있는 Deal
    code = await contract_env.won_deal(KIM)
    (first,) = await contract_env.contracts_of(code)
    await contract_env.leave_won_by_change(code, KIM)  # 유지(기본)

    change = DealChangeInput(field="forecast_key", value="won", resolution=CLOSING)
    # when: 인라인 변경으로 다시 Won으로 바꾼다
    await contract_env.env.apply.execute(code, change, KIM)

    # then: 계약은 처음의 1건 그대로다
    assert [c.id for c in await contract_env.contracts_of(code)] == [first.id]


async def test_a_rejected_won_change_creates_no_contract(contract_env: ContractEnv) -> None:
    """Won 전환이 거절되면 Deal은 그대로이고 계약도 생기지 않는다.

    테스트 코드: LC-005
    """
    # given: 계약이 없는 Won이 아닌 Deal
    code = await contract_env.open_deal()
    change = DealChangeInput(field="forecast_key", value="won")  # 매출 확인(resolution) 없음

    # when: 매출 확인(resolution) 없이 Forecast를 won으로 바꾼다
    with pytest.raises(InvalidValueError):
        await contract_env.env.apply.execute(code, change, KIM)

    # then: InvalidValueError, 계약 0건, Forecast는 pipeline 그대로
    assert await contract_env.contracts_of(code) == []
    assert await contract_env.forecast_of(code) == "pipeline"
