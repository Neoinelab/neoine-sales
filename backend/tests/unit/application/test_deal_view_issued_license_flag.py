"""Deal 조회 DTO가 `has_issued_license_contract`를 그대로 전달한다(AC28)."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from tests.unit.application.license_contract_env import BOSS, KIM

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv


async def _flag_of_detail(contract_env: ContractEnv, code: str) -> bool:
    return (await contract_env.env.get.execute(code)).item.has_issued_license_contract


async def _flag_of_list(contract_env: ContractEnv, code: str) -> bool:
    page = await contract_env.env.list.execute(DealQuery(limit=200))
    (view,) = [v for v in page.items if v.item.deal.id.value == code]
    return view.item.has_issued_license_contract


@pytest.mark.parametrize("read", [_flag_of_detail, _flag_of_list])
async def test_flag_is_false_without_contracts_and_with_only_a_waiting_contract(
    contract_env: ContractEnv, read: object
) -> None:
    bare = await contract_env.won_deal_without_contract(KIM)
    waiting = await contract_env.won_deal(KIM)  # 자동 생성된 미발급 계약 하나

    assert await read(contract_env, bare) is False  # type: ignore[operator]
    assert await read(contract_env, waiting) is False  # type: ignore[operator]


@pytest.mark.parametrize("read", [_flag_of_detail, _flag_of_list])
@pytest.mark.parametrize("status", ["issued_new", "issued_renewal"])
async def test_flag_is_true_with_an_issued_contract(
    contract_env: ContractEnv, read: object, status: str
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    await contract_env.seed_contract(code, status=status)

    assert await read(contract_env, code) is True  # type: ignore[operator]


@pytest.mark.parametrize("read", [_flag_of_detail, _flag_of_list])
async def test_flag_is_false_after_the_issued_contract_ends(
    contract_env: ContractEnv, read: object
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    issued = await contract_env.seed_contract(code, status="issued_new")
    await contract_env.end.execute(issued.id, KIM)

    assert await read(contract_env, code) is False  # type: ignore[operator]


async def test_flag_stays_true_after_renewal_creates_the_new_issued_row(
    contract_env: ContractEnv,
) -> None:
    from datetime import date  # noqa: PLC0415

    code = await contract_env.won_deal_without_contract(KIM)
    previous = await contract_env.seed_contract(code, status="issued_new")
    await contract_env.renew.execute(previous.id, contract_env.issue_input(date(2027, 1, 1)), KIM)

    assert await _flag_of_detail(contract_env, code) is True


async def test_flag_follows_an_admin_delete_of_the_issued_contract(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.won_deal_without_contract(KIM)
    issued = await contract_env.seed_contract(code, status="issued_new")
    await contract_env.delete.execute(issued.id, BOSS)

    assert await _flag_of_detail(contract_env, code) is False


async def test_flag_belongs_to_each_deal_separately(contract_env: ContractEnv) -> None:
    with_issued = await contract_env.won_deal_without_contract(KIM)
    await contract_env.seed_contract(with_issued, status="issued_new")
    without = await contract_env.won_deal(KIM)

    assert await _flag_of_detail(contract_env, with_issued) is True
    assert await _flag_of_detail(contract_env, without) is False
