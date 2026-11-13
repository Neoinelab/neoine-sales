"""DeleteDeal: 완료된(Won) Deal은 admin만 지운다(DD-R41) — 판정 순서는 DD-R24."""

import logging
from typing import TYPE_CHECKING

import pytest

from app.application.deal.delete_deal import DeleteDeal
from app.domain.auth.principal import Role
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealCodeMismatchError, DealDeleteForbiddenError
from tests.support.expect import raises_with
from tests.unit.application.license_contract_env import BOSS, KIM, PARK

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv

COMPLETED = "완료된 Deal은 관리자만 삭제할 수 있습니다."
OWNER_ONLY = "본인 Deal 또는 admin만 삭제할 수 있습니다."


def _delete_deal(contract_env: ContractEnv) -> DeleteDeal:
    return DeleteDeal(contract_env.uow_factory, contract_env.clock, contract_env.storage)


@pytest.mark.parametrize("typed", ["correct", "wrong"])
async def test_the_owner_sales_user_cannot_delete_a_completed_deal_and_nothing_is_removed(
    contract_env: ContractEnv, typed: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Owner 영업이 완료된 자기 Deal을 지우면 확인 code와 무관하게 403이고 Deal·계약·폴더가 남는다.

    테스트 코드: DD-118
    """
    from app.domain.deal.errors import DealDeleteCompletedError  # noqa: PLC0415

    # given: KIM이 Owner인 Won Deal(미발급 계약 1건, Deal 폴더 있음)
    code = await contract_env.won_deal(KIM, owner_user_id=KIM.user_id)
    await contract_env.seed_deal_file(code)
    contracts = await contract_env.contracts_of(code)
    assert len(contracts) == 1
    commits = contract_env.uow.commits
    caplog.set_level(logging.INFO)

    # when: KIM이 정확한 code 또는 틀린 code로 지운다
    with raises_with(DealDeleteCompletedError, COMPLETED):
        await _delete_deal(contract_env).execute(code, code if typed == "correct" else typed, KIM)

    # then: Deal·계약·폴더가 남고 커밋도 삭제 로그도 없다
    assert DealCode(code) in contract_env.uow.deals._items
    assert len(await contract_env.contracts_of(code)) == 1
    assert contract_env.deal_folder_exists(code)
    assert contract_env.uow.commits == commits
    assert not [r for r in caplog.records if r.getMessage().startswith("deal deleted")]


async def test_the_completed_refusal_is_an_access_denied_error_for_the_403_mapping(
    contract_env: ContractEnv,
) -> None:
    """완료된 Deal 삭제 거절은 403으로 매핑되는 권한 오류(AccessDeniedError)다.

    테스트 코드: DD-118
    """
    from app.domain.auth.errors import AccessDeniedError  # noqa: PLC0415

    # given: KIM이 Owner인 Won Deal
    code = await contract_env.won_deal(KIM, owner_user_id=KIM.user_id)

    # when: KIM이 지운다
    with pytest.raises(AccessDeniedError) as raised:
        await _delete_deal(contract_env).execute(code, code, KIM)

    # then: 권한 오류이고 "Owner 아님" 오류 클래스와는 다른 사유다
    assert not isinstance(raised.value, DealDeleteForbiddenError)


async def test_an_admin_deletes_a_completed_deal_with_its_contract(
    contract_env: ContractEnv,
) -> None:
    """admin은 완료된 Deal도 지우고 계약이 함께 사라진다.

    테스트 코드: DD-119
    """
    # given: KIM이 Owner인 Won Deal(계약 1건)
    code = await contract_env.won_deal(KIM, owner_user_id=KIM.user_id)
    assert len(await contract_env.contracts_of(code)) == 1

    # when: BOSS(admin)가 정확한 code로 지운다
    await _delete_deal(contract_env).execute(code, code, BOSS)

    # then: Deal과 계약이 없다
    assert DealCode(code) not in contract_env.uow.deals._items
    assert await contract_env.contracts_of(code) == []


@pytest.mark.parametrize(
    ("status_key", "forecast_key"),
    [("price_negotiation", "lost"), ("price_negotiation", "commit"), ("prospecting", "pipeline")],
    ids=["lost", "in-progress-commit", "in-progress-pipeline"],
)
async def test_the_owner_sales_user_still_deletes_a_deal_that_is_not_completed(
    contract_env: ContractEnv, status_key: str, forecast_key: str
) -> None:
    """Owner 영업은 Lost·진행 중 Deal을 지금처럼 지운다.

    테스트 코드: DD-120
    """
    # given: KIM이 Owner인 Lost 또는 진행 중 Deal
    code = await contract_env.open_deal(
        KIM, owner_user_id=KIM.user_id, status_key=status_key, forecast_key=forecast_key
    )

    # when: KIM이 정확한 code로 지운다
    await _delete_deal(contract_env).execute(code, code, KIM)

    # then: Deal이 없다
    assert DealCode(code) not in contract_env.uow.deals._items


async def test_the_owner_sales_user_deletes_a_deal_that_left_won(
    contract_env: ContractEnv,
) -> None:
    """Won이었다가 되돌린 Deal은 완료가 아니라서 Owner 영업이 지운다.

    테스트 코드: DD-120
    """
    # given: Won으로 등록했다가 Forecast를 Won 밖으로 되돌린 KIM의 Deal
    code = await contract_env.won_deal(KIM, owner_user_id=KIM.user_id)
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=True)
    assert await contract_env.forecast_of(code) != "won"

    # when: KIM이 정확한 code로 지운다
    await _delete_deal(contract_env).execute(code, code, KIM)

    # then: Deal이 없다
    assert DealCode(code) not in contract_env.uow.deals._items


@pytest.mark.parametrize("typed", ["correct", "wrong"])
async def test_another_sales_user_gets_the_owner_refusal_before_the_completed_one(
    contract_env: ContractEnv, typed: str
) -> None:
    """다른 영업이 완료된 Deal을 지우면 Owner 문구 403이 먼저이고 Deal이 남는다.

    테스트 코드: DD-121
    """
    # given: KIM이 Owner인 Won Deal과 다른 영업 PARK
    code = await contract_env.won_deal(KIM, owner_user_id=KIM.user_id)
    assert PARK.role is Role.SALES

    # when·then: PARK가 지운다 → "본인 Deal 또는 admin만" 오류다
    with raises_with(DealDeleteForbiddenError, OWNER_ONLY):
        await _delete_deal(contract_env).execute(code, code if typed == "correct" else typed, PARK)
    assert DealCode(code) in contract_env.uow.deals._items


async def test_the_completed_refusal_comes_before_the_confirmation_mismatch(
    contract_env: ContractEnv,
) -> None:
    """admin이 아닌 Owner가 완료된 Deal을 틀린 code로 지우면 422가 아니라 완료 문구 403이다.

    테스트 코드: DD-118
    """
    from app.domain.deal.errors import DealDeleteCompletedError  # noqa: PLC0415

    # given: KIM이 Owner인 Won Deal
    code = await contract_env.won_deal(KIM, owner_user_id=KIM.user_id)

    # when·then: KIM이 틀린 code로 지운다 → 완료 오류이고 code 불일치 오류가 아니다
    with raises_with(DealDeleteCompletedError, COMPLETED):
        await _delete_deal(contract_env).execute(code, "wrong", KIM)


async def test_an_admin_still_gets_the_mismatch_error_for_a_completed_deal(
    contract_env: ContractEnv,
) -> None:
    """admin은 완료 판정을 통과하므로 틀린 code는 기존처럼 422(불일치)이고 Deal이 남는다.

    테스트 코드: DD-119
    """
    # given: Won Deal
    code = await contract_env.won_deal(KIM, owner_user_id=KIM.user_id)

    # when·then: admin이 틀린 code로 지운다 → code 불일치 오류이고 Deal이 남는다
    with raises_with(DealCodeMismatchError, "Deal code가 일치하지 않습니다."):
        await _delete_deal(contract_env).execute(code, "wrong", BOSS)
    assert DealCode(code) in contract_env.uow.deals._items
