"""Action 저장의 FK 경계(PostgreSQL): 제약 위반이 도메인 오류로 바뀐다(500 아님).

Action은 `deal_code`로 Deal에 속하고 Deal을 지우면 함께 지워진다(CASCADE). 담당자는 users 행을
가리키고, 등록 시점 Status/Forecast key는 codes(kind, key)를 복합 FK로 가리킨다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.action_type.errors import ActionTypeInUseError
from app.domain.common.errors import InvalidReferenceError
from app.domain.deal.errors import DealNotFoundError
from app.domain.user.value_objects import UserId
from app.infra.db.action_type_repository import SqlActionTypeRepository
from app.infra.db.contact_repository import SqlContactRepository
from app.infra.db.deal_action_repository import SqlDealActionRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import make_deal, make_deal_action, make_deal_code, make_sync
from tests.factories_action_type import attach_catalog_type, make_type_ref
from tests.factories_contact import make_customer
from tests.support.database import rolled_back_session
from tests.support.ids import new_id
from tests.support.user_ids import ACTOR_ID, OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.deal.entities import Deal
    from app.domain.deal_action.entities import DealAction

pytestmark = pytest.mark.integration


async def _deal(session: AsyncSession) -> Deal:
    customer = make_customer()
    await SqlContactRepository(session).add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID, ACTOR_ID)
    deal = make_deal(customer_id=customer.id)
    await SqlDealRepository(session).add(deal)
    return deal


async def _action(session: AsyncSession, **overrides: Any) -> DealAction:  # noqa: ANN401
    """유형이 DB의 시드 유형을 가리키는 Action(시드 id는 무작위라 이름으로 맞춘다)."""
    action = make_deal_action(**overrides)
    await attach_catalog_type(SqlActionTypeRepository(session), action)
    return action


async def test_add_for_missing_deal_raises_deal_not_found(test_database_url: URL) -> None:
    """없는 Deal에 Action을 저장하면 Deal 없음 오류가 난다."""
    async with rolled_back_session(test_database_url) as session:
        # given: Deal은 없고 수행자만 있는 DB
        repository = SqlDealActionRepository(session)
        await ensure_users(SqlUserRepository(session), ACTOR_ID)

        # when·then: 없는 Deal 코드의 Action을 저장하면 Deal 없음 오류가 난다
        with pytest.raises(DealNotFoundError):
            await repository.add(await _action(session, deal_code=make_deal_code("ZZZZ")))


async def test_add_after_the_deal_is_physically_deleted_raises_deal_not_found(
    test_database_url: URL,
) -> None:
    """Deal을 물리 삭제한 뒤 Action을 저장하면 Deal 없음 오류가 난다."""
    async with rolled_back_session(test_database_url) as session:
        # given: 물리 삭제한 Deal
        deal = await _deal(session)
        await SqlDealRepository(session).delete(deal.id)

        # when·then: 삭제된 Deal의 Action을 저장하면 Deal 없음 오류가 난다
        with pytest.raises(DealNotFoundError):
            await SqlDealActionRepository(session).add(await _action(session, deal_code=deal.id))


async def test_add_with_a_missing_actor_user_raises_invalid_reference(
    test_database_url: URL,
) -> None:
    """없는 수행자로 Action을 저장하면 잘못된 참조 오류가 난다."""
    async with rolled_back_session(test_database_url) as session:
        # given: Deal은 있고 존재하지 않는 수행자 id
        deal = await _deal(session)

        # when: 그 수행자로 Action을 저장한다
        with pytest.raises(InvalidReferenceError) as caught:
            await SqlDealActionRepository(session).add(
                await _action(session, deal_code=deal.id, actor_user_id=UserId(new_id()))
            )

        # then: 오류가 "사용자"를 가리킨다
        assert caught.value.entity == "사용자"


@pytest.mark.parametrize(
    ("snapshot", "entity", "key"),
    [
        (make_sync(status_key="no_such_status"), "Status 코드", "no_such_status"),
        (make_sync(forecast_key="no_such_forecast"), "Forecast 코드", "no_such_forecast"),
    ],
)
async def test_add_with_an_unknown_snapshot_code_names_which_code_is_missing(
    test_database_url: URL, snapshot: object, entity: str, key: str
) -> None:
    """없는 Status·Forecast 코드 스냅숏은 어느 코드가 없는지 오류에 담긴다."""
    async with rolled_back_session(test_database_url) as session:
        # given: Deal은 있고 스냅숏 코드 하나가 없는 Action
        deal = await _deal(session)

        # when: 저장한다
        with pytest.raises(InvalidReferenceError) as caught:
            await SqlDealActionRepository(session).add(
                await _action(session, deal_code=deal.id, snapshot=snapshot)
            )

        # then: 오류가 해당 코드 종류와 key를 가리킨다
        assert (caught.value.entity, caught.value.identifier) == (entity, key)


async def test_the_session_stays_usable_after_a_reference_error(test_database_url: URL) -> None:
    """참조 오류가 난 뒤에도 같은 세션으로 계속 저장할 수 있다."""
    async with rolled_back_session(test_database_url) as session:
        # given: Deal이 있는 세션
        deal = await _deal(session)
        repository = SqlDealActionRepository(session)
        # when: 없는 Forecast 코드의 Action 저장이 참조 오류로 거절된다
        with pytest.raises(InvalidReferenceError):
            await repository.add(
                await _action(session, deal_code=deal.id, snapshot=make_sync(forecast_key="nope"))
            )

        # when: 같은 세션에서 올바른 Action을 저장한다
        action = await _action(session, deal_code=deal.id)
        await repository.add(action)

        # then: 그 Action을 읽을 수 있다
        assert (await repository.get(action.id)).id == action.id


async def test_add_with_an_unknown_action_type_names_the_type(test_database_url: URL) -> None:
    """없는 유형으로 저장하면 오류가 그 유형을 가리킨다."""
    async with rolled_back_session(test_database_url) as session:
        # given: Deal은 있고 존재하지 않는 유형 참조
        deal = await _deal(session)
        missing = make_type_ref("ZZ 없는 유형")

        # when: 그 유형의 Action을 저장한다
        with pytest.raises(InvalidReferenceError) as caught:
            await SqlDealActionRepository(session).add(
                make_deal_action(deal_code=deal.id, action_type=missing)
            )

        # then: 오류가 "Action 유형"과 유형 id를 가리킨다
        assert (caught.value.entity, caught.value.identifier) == ("Action 유형", missing.id)


async def test_deleting_a_type_used_by_an_action_is_refused_by_the_database(
    test_database_url: URL,
) -> None:
    """FK RESTRICT: 유형 삭제가 도메인 오류(ActionTypeInUseError)로 바뀐다(500 아님)."""
    async with rolled_back_session(test_database_url) as session:
        # given: Action이 쓰는 유형
        deal = await _deal(session)
        action = await _action(session, deal_code=deal.id)
        await SqlDealActionRepository(session).add(action)
        types = SqlActionTypeRepository(session)

        # when: 그 유형을 삭제한다
        with pytest.raises(ActionTypeInUseError) as caught:
            await types.delete(action.content.action_type.id)

        # then: 사용 중 오류가 사용 건수 1을 담는다
        assert caught.value.usage == 1
