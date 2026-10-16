"""Deal 유스케이스 단위 테스트의 공용 환경: Fake UoW 위에 조립한 유스케이스 묶음과 준비 도우미.

이 모듈은 Deal 유스케이스를 모듈 수준에서 가져온다. 그래서 `conftest.py`의 `env` fixture가 사용
시점에 가져온다(Deal 구현이 없어도 다른 테스트의 수집이 막히지 않는다).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.get_deal import GetDeal
from app.application.deal.list_deal_history import ListDealHistory
from app.application.deal.list_deals import ListDeals
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.update_deal import UpdateDeal
from tests.factories_deal import SALES, make_create_input

if TYPE_CHECKING:
    import builtins

    from app.application.deal.apply_change import ApplyDealChange
    from app.application.deal.deletion_impact import GetDealDeletionImpact
    from app.application.deal.dto import DealView
    from app.application.deal.inputs import Actor
    from app.application.deal.list_facets import ListDealFacets
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.deal_code_source import FakeDealCodeSuffixSource
    from tests.fakes.file_storage import FakeFileStorage
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@dataclass
class DealEnv:
    uow: FakeUnitOfWork
    uow_factory: UnitOfWorkFactory
    clock: FixedClock
    suffix_source: FakeDealCodeSuffixSource
    storage: FakeFileStorage
    register: RegisterDeal
    update: UpdateDeal
    delete: DeleteDeal
    get: GetDeal
    list: ListDeals
    history: ListDealHistory

    # R3 유스케이스는 사용할 때 가져온다(구현 전에도 R2 테스트가 이 환경을 그대로 쓰도록).
    @property
    def apply(self) -> ApplyDealChange:
        from app.application.deal.apply_change import ApplyDealChange  # noqa: PLC0415

        return ApplyDealChange(self.uow_factory, self.clock)

    @property
    def impact(self) -> GetDealDeletionImpact:
        from app.application.deal.deletion_impact import GetDealDeletionImpact  # noqa: PLC0415

        return GetDealDeletionImpact(self.uow_factory)

    @property
    def facets(self) -> ListDealFacets:
        from app.application.deal.list_facets import ListDealFacets  # noqa: PLC0415

        return ListDealFacets(self.uow_factory)

    async def new_deal(self, *, actor: Actor = SALES, **overrides: Any) -> DealView:  # noqa: ANN401
        """RegisterDeal로 Deal을 등록한다(overrides는 DealCreateInput 필드). 시계가 1초 흐른다."""
        self.clock.advance(1)
        return await self.register.execute(make_create_input(**overrides), actor)

    async def changes(self, view: DealView) -> builtins.list[tuple[str, str, str, str]]:
        """등록 이력을 뺀 변경 이력(오래된 순서)."""
        rows = await self.history_rows(view.item.deal.id.value)
        assert rows[0] == ("created", "Deal 등록", "", "Deal 등록")
        return rows[1:]

    async def history_rows(self, code: str) -> builtins.list[tuple[str, str, str, str]]:
        """오래된 순서의 (category, target, before, after)."""
        views = await self.history.execute(code, None)
        return [
            (
                str(v.entry.draft.category),
                v.entry.draft.target,
                v.entry.draft.before,
                v.entry.draft.after,
            )
            for v in reversed(views)
        ]


def build_env(
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    suffix_source: FakeDealCodeSuffixSource,
    storage: FakeFileStorage,
) -> DealEnv:
    shared: Clock = clock
    return DealEnv(
        uow=uow,
        uow_factory=uow_factory,
        clock=clock,
        suffix_source=suffix_source,
        storage=storage,
        register=RegisterDeal(uow_factory, shared, suffix_source),
        update=UpdateDeal(uow_factory, shared),
        delete=DeleteDeal(uow_factory, shared, storage),
        get=GetDeal(uow_factory),
        list=ListDeals(uow_factory),
        history=ListDealHistory(uow_factory),
    )
