from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.register_deal import RegisterDeal
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.get_deal_action import GetDealAction
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.search_deal_actions import SearchDealActions
from app.application.deal_action.update_deal_action import UpdateDealAction
from app.application.ports.deal_action_repository import DealActionQuery
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.value_objects import DealId
from app.domain.deal_action.errors import DealActionNotFoundError
from app.domain.deal_action.value_objects import ActionType, DealActionId
from tests.factories import (
    NOW,
    make_customer_input,
    make_deal_action_input,
    make_deal_input,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
async def deal_id(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> DealId:
    customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
    deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))
    return deal.id


class TestRegisterDealAction:
    async def test_stores_the_action_under_the_deal(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        deal_id: DealId,
    ) -> None:
        action = await RegisterDealAction(uow_factory, clock).execute(
            deal_id, make_deal_action_input(title="  제안서 전달 ")
        )

        stored = await uow.deal_actions.get(action.id)
        assert stored.details.deal_id == deal_id
        assert stored.details.title == "제안서 전달"
        assert stored.created_at == clock.now()

    async def test_unknown_deal_raises_not_found_and_stores_nothing(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        with pytest.raises(DealNotFoundError):
            await RegisterDealAction(uow_factory, clock).execute(
                DealId(uuid4()), make_deal_action_input()
            )

        assert await uow.deal_actions.search(DealActionQuery()) == []

    async def test_deleted_deal_cannot_receive_actions(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> None:
        await DeleteDeal(uow_factory, clock).execute(deal_id)

        with pytest.raises(DealNotFoundError):
            await RegisterDealAction(uow_factory, clock).execute(deal_id, make_deal_action_input())

    async def test_invalid_input_raises_before_any_write(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        deal_id: DealId,
    ) -> None:
        commits = uow.commits

        with pytest.raises(InvalidValueError):
            await RegisterDealAction(uow_factory, clock).execute(
                deal_id, make_deal_action_input(title=" ")
            )

        assert uow.commits == commits


class TestGetUpdateDelete:
    async def test_get_returns_the_action(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> None:
        created = await RegisterDealAction(uow_factory, clock).execute(
            deal_id, make_deal_action_input()
        )

        assert (await GetDealAction(uow_factory).execute(created.id)) == created

    async def test_get_unknown_action_raises_not_found(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with pytest.raises(DealActionNotFoundError):
            await GetDealAction(uow_factory).execute(DealActionId(uuid4()))

    async def test_update_replaces_values_and_keeps_the_deal(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> None:
        created = await RegisterDealAction(uow_factory, clock).execute(
            deal_id, make_deal_action_input()
        )
        clock.advance(60)

        updated = await UpdateDealAction(uow_factory, clock).execute(
            created.id,
            make_deal_action_input(action_type=ActionType.PROPOSAL, title="제안", content=""),
        )

        assert updated.details.deal_id == deal_id
        assert updated.details.action_type is ActionType.PROPOSAL
        assert updated.updated_at == clock.now()
        assert (await GetDealAction(uow_factory).execute(created.id)).details.title == "제안"

    async def test_delete_hides_the_action(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> None:
        created = await RegisterDealAction(uow_factory, clock).execute(
            deal_id, make_deal_action_input()
        )

        await DeleteDealAction(uow_factory, clock).execute(created.id)

        with pytest.raises(DealActionNotFoundError):
            await GetDealAction(uow_factory).execute(created.id)
        with pytest.raises(DealActionNotFoundError):
            await DeleteDealAction(uow_factory, clock).execute(created.id)


class TestSearchDealActions:
    @pytest.fixture
    async def seeded(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId
    ) -> list[str]:
        register = RegisterDealAction(uow_factory, clock)
        rows = [
            (ActionType.CALL, "첫 통화", "예산 문의 100%", "김영업", 0),
            (ActionType.MEETING, "킥오프 미팅", "요구사항 정리", "박영업", 1),
            (ActionType.EMAIL, "제안서 발송", "견적 첨부", "박영업", 2),
            (ActionType.MEETING, "최종 미팅", "계약 조건 협의", "김영업", 3),
        ]
        for action_type, title, content, actor, day in rows:
            await register.execute(
                deal_id,
                make_deal_action_input(
                    action_type=action_type,
                    title=title,
                    content=content,
                    actor=actor,
                    acted_at=NOW + timedelta(days=day),
                ),
            )
        return [row[1] for row in rows]

    async def _titles(self, uow_factory: UnitOfWorkFactory, **criteria: object) -> list[str]:
        found = await SearchDealActions(uow_factory).execute(DealActionQuery(**criteria))  # type: ignore[arg-type]
        return [a.details.title for a in found]

    async def test_default_order_is_latest_activity_first(
        self, uow_factory: UnitOfWorkFactory, seeded: list[str]
    ) -> None:
        assert await self._titles(uow_factory) == list(reversed(seeded))

    async def test_filters_combine_with_and(
        self, uow_factory: UnitOfWorkFactory, seeded: list[str]
    ) -> None:
        assert await self._titles(uow_factory, action_type=ActionType.MEETING) == [
            "최종 미팅",
            "킥오프 미팅",
        ]
        assert await self._titles(uow_factory, action_type=ActionType.MEETING, actor="박영업") == [
            "킥오프 미팅"
        ]

    async def test_keyword_matches_title_or_content_ignoring_case(
        self, uow_factory: UnitOfWorkFactory, seeded: list[str]
    ) -> None:
        assert await self._titles(uow_factory, keyword="견적") == ["제안서 발송"]
        assert await self._titles(uow_factory, keyword="킥오프") == ["킥오프 미팅"]

    async def test_keyword_treats_wildcards_literally(
        self, uow_factory: UnitOfWorkFactory, seeded: list[str]
    ) -> None:
        assert await self._titles(uow_factory, keyword="100%") == ["첫 통화"]
        assert await self._titles(uow_factory, keyword="%") == ["첫 통화"]
        assert await self._titles(uow_factory, keyword="_") == []

    async def test_period_is_inclusive_from_and_exclusive_to(
        self, uow_factory: UnitOfWorkFactory, seeded: list[str]
    ) -> None:
        titles = await self._titles(
            uow_factory, acted_from=NOW + timedelta(days=1), acted_to=NOW + timedelta(days=3)
        )

        assert titles == ["제안서 발송", "킥오프 미팅"]

    async def test_paging(self, uow_factory: UnitOfWorkFactory, seeded: list[str]) -> None:
        assert await self._titles(uow_factory, offset=1, limit=2) == ["제안서 발송", "킥오프 미팅"]

    async def test_filter_by_deal_requires_an_existing_deal(
        self, uow_factory: UnitOfWorkFactory, seeded: list[str], deal_id: DealId
    ) -> None:
        assert len(await self._titles(uow_factory, deal_id=deal_id)) == len(seeded)
        with pytest.raises(DealNotFoundError):
            await self._titles(uow_factory, deal_id=DealId(uuid4()))

    async def test_history_of_a_deleted_deal_stays_searchable(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, seeded: list[str], deal_id: DealId
    ) -> None:
        await DeleteDeal(uow_factory, clock).execute(deal_id)

        assert len(await self._titles(uow_factory, deal_id=deal_id)) == len(seeded)

    async def test_deleted_actions_are_excluded(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, seeded: list[str]
    ) -> None:
        found = await SearchDealActions(uow_factory).execute(DealActionQuery(keyword="견적"))
        await DeleteDealAction(uow_factory, clock).execute(found[0].id)

        assert await self._titles(uow_factory, keyword="견적") == []

    @pytest.mark.parametrize(
        "criteria",
        [
            {"limit": 0},
            {"offset": -1},
            {"acted_from": NOW, "acted_to": NOW},
            {"acted_from": NOW.replace(tzinfo=None)},
            {"keyword": "가" * 101},
        ],
    )
    async def test_invalid_criteria_raise_invalid_value(
        self, uow_factory: UnitOfWorkFactory, criteria: dict[str, object]
    ) -> None:
        with pytest.raises(InvalidValueError):
            await self._titles(uow_factory, **criteria)
