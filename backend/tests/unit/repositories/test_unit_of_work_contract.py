"""UnitOfWork 공통 계약: commit한 변경만 남고, 미커밋·예외·commit 이후의 변경은 사라진다.

Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다. SQL 구현은 실제로 commit하므로
테스트가 끝나면 테이블을 비워 다른 테스트에 영향을 주지 않는다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.action_type.errors import ActionTypeNotFoundError
from app.domain.contact.errors import ContactNotFoundError
from app.domain.deal.history import DealHistoryEntry, HistoryCategory, HistoryDraft
from app.domain.deal_action.errors import DealActionNotFoundError
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import later, make_deal, make_deal_action, make_deal_details
from tests.factories_action_type import make_action_type
from tests.factories_contact import make_customer
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.truncate import truncate_business_tables
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.action_type.values import ActionTypeId
    from app.domain.contact.entities import Contact
    from app.domain.deal.code import DealCode
    from app.domain.deal_action.value_objects import DealActionId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def uow_factory(request: pytest.FixtureRequest) -> AsyncIterator[UnitOfWorkFactory]:
    if request.param == "fake":
        shared = FakeUnitOfWork()
        yield lambda: shared
        return
    url = request.getfixturevalue("test_database_url")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await truncate_business_tables(connection)
    finally:
        await engine.dispose()


async def test_committed_changes_are_visible_to_later_units(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """commit한 변경은 이후 작업 단위에서 보인다."""
    # given: 고객 연락처 (커밋 후 조회)
    customer = make_customer()
    # when: 추가하고 commit한다
    async with uow_factory() as uow:
        await uow.contacts.add(customer)
        await uow.commit()

    # when: 새 작업 단위에서 조회한다
    async with uow_factory() as later_uow:
        # then: 추가한 연락처가 보인다
        assert await later_uow.contacts.get(customer.id) == customer


async def test_changes_are_visible_inside_the_unit_before_commit(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """commit 전에도 같은 작업 단위 안에서는 변경이 보인다."""
    # given: 고객 연락처 (커밋 전 조회)
    customer = make_customer()
    # when: 추가만 하고 같은 단위에서 조회한다
    async with uow_factory() as uow:
        await uow.contacts.add(customer)

        # then: 추가한 연락처가 보인다
        assert await uow.contacts.get(customer.id) == customer


async def test_changes_without_commit_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    """commit하지 않은 변경은 버려진다."""
    # given: 고객 연락처 (커밋 없이 종료)
    customer = make_customer()
    # when: 추가만 하고 단위를 끝낸다
    async with uow_factory() as uow:
        await uow.contacts.add(customer)

    # when·then: 새 작업 단위에서 조회하면 연락처 없음 오류다
    async with uow_factory() as later_uow:
        with pytest.raises(ContactNotFoundError):
            await later_uow.contacts.get(customer.id)


async def _add_then_fail(uow_factory: UnitOfWorkFactory, customer: Contact) -> None:
    async with uow_factory() as uow:
        await uow.contacts.add(customer)
        raise RuntimeError("boom")


async def test_an_exception_discards_changes_even_after_add(uow_factory: UnitOfWorkFactory) -> None:
    """추가한 뒤 예외가 나면 변경이 버려진다."""
    # given: 고객 연락처 (추가 뒤 예외)
    customer = make_customer()
    # when·then: 추가 뒤 예외가 나면 그 예외가 전파된다
    with pytest.raises(RuntimeError, match="boom"):
        await _add_then_fail(uow_factory, customer)

    # then: 새 작업 단위에서 조회하면 연락처 없음 오류다
    async with uow_factory() as later_uow:
        with pytest.raises(ContactNotFoundError):
            await later_uow.contacts.get(customer.id)


async def test_explicit_rollback_discards_changes(uow_factory: UnitOfWorkFactory) -> None:
    """명시적 rollback은 변경을 버린다."""
    # given: 고객 연락처 (명시적 롤백)
    customer = make_customer()
    # when: 추가한 뒤 rollback한다
    async with uow_factory() as uow:
        await uow.contacts.add(customer)
        await uow.rollback()

        # then: 같은 단위에서 조회하면 연락처 없음 오류다
        with pytest.raises(ContactNotFoundError):
            await uow.contacts.get(customer.id)


async def test_changes_made_after_commit_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    """commit 이후의 변경은 버려진다."""
    # given: 연락처 두 개
    kept, dropped = make_customer(company="유지"), make_customer(company="폐기")
    # when: 하나는 commit하고 다른 하나는 commit 없이 추가한다
    async with uow_factory() as uow:
        await uow.contacts.add(kept)
        await uow.commit()
        await uow.contacts.add(dropped)

    # then: 새 작업 단위에는 commit한 것만 있다
    async with uow_factory() as later_uow:
        assert await later_uow.contacts.get(kept.id) == kept
        with pytest.raises(ContactNotFoundError):
            await later_uow.contacts.get(dropped.id)


async def _name_and_history_count(
    uow_factory: UnitOfWorkFactory, code: DealCode
) -> tuple[str, int]:
    async with uow_factory() as uow:
        deal = await uow.deals.get(code)
        return deal.details.name, len(await uow.deal_history.list(code))


async def _seed_deal(uow_factory: UnitOfWorkFactory) -> DealCode:
    customer = make_customer()
    deal = make_deal(code="20261016-A001", customer_id=customer.id)
    async with uow_factory() as uow:
        await ensure_users(uow.users, OWNER_ID)  # FK: 담당자·이력 변경자
        await uow.contacts.add(customer)
        await uow.deals.add(deal)
        await uow.commit()
    return deal.id


async def _rename_with_history(
    uow_factory: UnitOfWorkFactory, code: DealCode, *, commit: bool
) -> None:
    async with uow_factory() as uow:
        deal = await uow.deals.get(code, for_update=True)
        deal.revise(
            details=make_deal_details(name="바뀐 이름"),
            sync=deal.sync,
            customer_id=deal.customer_id,
            bant=deal.bant,
        )
        deal.touch(later(5))
        await uow.deals.update(deal)
        draft = HistoryDraft(HistoryCategory("other"), "Deal Name", "ERP 구축", "바뀐 이름")
        await uow.deal_history.add_many([DealHistoryEntry(None, code, later(5), OWNER_ID, draft)])
        if commit:
            await uow.commit()


async def test_a_deal_change_and_its_history_are_committed_together(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """Deal 변경과 이력은 함께 commit된다."""
    # given: 저장된 Deal
    code = await _seed_deal(uow_factory)

    # when: 이름을 바꾸고 이력을 남긴 뒤 commit한다
    await _rename_with_history(uow_factory, code, commit=True)

    # then: 새 이름과 이력 1건이 보인다
    assert await _name_and_history_count(uow_factory, code) == ("바뀐 이름", 1)


async def test_a_deal_change_and_its_history_are_discarded_together_without_commit(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """commit하지 않으면 Deal 변경과 이력이 함께 버려진다."""
    # given: 저장된 Deal
    code = await _seed_deal(uow_factory)

    # when: 이름을 바꾸고 이력을 남기되 commit하지 않는다
    await _rename_with_history(uow_factory, code, commit=False)

    # then: 이름은 그대로이고 이력은 0건이다
    assert await _name_and_history_count(uow_factory, code) == ("ERP 구축", 0)


async def _add_type_and_action(
    uow_factory: UnitOfWorkFactory, code: DealCode, *, commit: bool
) -> tuple[ActionTypeId, DealActionId]:
    """새 유형과 그 유형을 쓰는 Action을 한 단위로 만든다(Action 등록 유스케이스와 같은 모양)."""
    action_type = make_action_type("ZZ 단위 유형", created_by=OWNER_ID)
    async with uow_factory() as uow:
        await uow.action_types.add(action_type)
        action = make_deal_action(
            deal_code=code, actor_user_id=OWNER_ID, action_type=action_type.ref
        )
        await uow.deal_actions.add(action)
        if commit:
            await uow.commit()
    return action_type.id, action.id


async def test_a_new_action_type_and_its_action_are_committed_together(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """새 Action 유형과 그 Action은 함께 commit된다."""
    # given: 저장된 Deal
    code = await _seed_deal(uow_factory)

    # when: 새 유형과 Action을 만들고 commit한다
    type_id, action_id = await _add_type_and_action(uow_factory, code, commit=True)

    # then: 유형과 Action이 모두 조회된다
    async with uow_factory() as later_uow:
        assert (await later_uow.action_types.get(type_id)).name == "ZZ 단위 유형"
        stored = await later_uow.deal_actions.get(action_id)
        assert stored.content.action_type.id == type_id


async def test_a_new_action_type_and_its_action_are_both_discarded_without_commit(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """commit하지 않으면 새 Action 유형과 Action이 함께 버려진다."""
    # given: 저장된 Deal
    code = await _seed_deal(uow_factory)

    # when: 새 유형과 Action을 만들되 commit하지 않는다
    type_id, action_id = await _add_type_and_action(uow_factory, code, commit=False)

    # then: 유형과 Action 모두 조회하면 없음 오류다
    async with uow_factory() as later_uow:
        with pytest.raises(ActionTypeNotFoundError):
            await later_uow.action_types.get(type_id)
        with pytest.raises(DealActionNotFoundError):
            await later_uow.deal_actions.get(action_id)
