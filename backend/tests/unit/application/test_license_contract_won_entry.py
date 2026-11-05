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
    code = await contract_env.won_deal(KIM)

    (contract,) = await contract_env.contracts_of(code)
    assert contract.status is ContractStatus.NOT_ISSUED
    assert (contract.term, contract.license_start, contract.license_end) == (None, None, None)
    assert contract.fields == EMPTY_FIELDS
    assert contract.renewed_from_id is None
    assert contract.created_by == contract.updated_by == KIM.user_id


async def test_register_deal_not_won_creates_no_contract(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()

    assert await contract_env.contracts_of(code) == []


async def test_registering_the_contract_is_in_the_same_transaction_as_the_deal(
    contract_env: ContractEnv,
) -> None:
    before = contract_env.uow.commits

    await contract_env.won_deal(KIM)

    assert contract_env.uow.commits == before + 1


async def test_update_deal_to_won_creates_contract_when_none(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()

    await contract_env.env.update.execute(
        code, make_patch(status_key="contract_completed", forecast_key="won"), PARK
    )

    (contract,) = await contract_env.contracts_of(code)
    assert contract.status is ContractStatus.NOT_ISSUED
    assert contract.created_by == PARK.user_id


async def test_update_deal_to_won_skips_when_contract_exists(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    ended = await contract_env.seed_contract(code, status="ended")

    await contract_env.env.update.execute(
        code, make_patch(status_key="contract_completed", forecast_key="won"), KIM
    )

    assert [c.id for c in await contract_env.contracts_of(code)] == [ended.id]


async def test_update_deal_without_a_won_change_creates_nothing(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()

    await contract_env.env.update.execute(code, make_patch(name="이름만 변경"), KIM)

    assert await contract_env.contracts_of(code) == []


async def test_update_deal_that_stays_won_creates_no_second_contract(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal(KIM)

    await contract_env.env.update.execute(code, make_patch(name="이름 변경"), KIM)

    assert len(await contract_env.contracts_of(code)) == 1


async def test_apply_change_forecast_won_creates_contract(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    change = DealChangeInput(field="forecast_key", value="won", resolution=CLOSING)

    await contract_env.env.apply.execute(code, change, KIM)

    (contract,) = await contract_env.contracts_of(code)
    assert contract.status is ContractStatus.NOT_ISSUED
    assert contract.created_by == KIM.user_id


async def test_apply_change_status_contract_completed_creates_contract(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    change = DealChangeInput(field="status_key", value="contract_completed", resolution=CLOSING)

    await contract_env.env.apply.execute(code, change, KIM)

    assert len(await contract_env.contracts_of(code)) == 1


async def test_apply_change_that_does_not_reach_won_creates_nothing(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    change = DealChangeInput(field="forecast_key", value="commit")

    await contract_env.env.apply.execute(code, change, KIM)

    assert await contract_env.contracts_of(code) == []


async def test_register_action_status_change_to_won_creates_contract(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    change = StatusChangeInput(field="forecast_key", value="won", resolution=CLOSING)
    contract_env.clock.advance(60)

    await contract_env.register_action.execute(code, make_register_input((change,)), KIM)

    (contract,) = await contract_env.contracts_of(code)
    assert contract.status is ContractStatus.NOT_ISSUED
    assert contract.created_by == KIM.user_id


async def test_register_action_with_two_changes_that_end_at_won_creates_one_contract(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    first = StatusChangeInput(field="status_key", value="contract_completed", resolution=CLOSING)
    second = StatusChangeInput(field="forecast_key", value="won")
    contract_env.clock.advance(60)

    await contract_env.register_action.execute(code, make_register_input((first, second)), KIM)

    assert len(await contract_env.contracts_of(code)) == 1


async def test_register_action_without_status_change_creates_nothing(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    contract_env.clock.advance(60)

    await contract_env.register_action.execute(code, make_register_input(action="미팅"), KIM)

    assert await contract_env.contracts_of(code) == []


async def test_won_then_left_with_keep_then_won_again_keeps_the_single_contract(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal(KIM)
    (first,) = await contract_env.contracts_of(code)
    await contract_env.leave_won_by_change(code, KIM)  # 유지(기본)

    change = DealChangeInput(field="forecast_key", value="won", resolution=CLOSING)
    await contract_env.env.apply.execute(code, change, KIM)

    assert [c.id for c in await contract_env.contracts_of(code)] == [first.id]


async def test_a_rejected_won_change_creates_no_contract(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    change = DealChangeInput(field="forecast_key", value="won")  # 매출 확인(resolution) 없음

    with pytest.raises(InvalidValueError):
        await contract_env.env.apply.execute(code, change, KIM)

    assert await contract_env.contracts_of(code) == []
    assert await contract_env.forecast_of(code) == "pipeline"
