"""FakeUseCases에 섞어 쓰는 Deal 유스케이스 조립(파일 길이를 나누기 위한 mixin).

유스케이스 모듈은 사용 시점에 가져온다. FakeUseCases는 Deal과 무관한 테스트도 쓰므로, 모듈 수준
import는 Deal 구현이 없는 동안 그 테스트의 수집까지 막는다(tests/fakes/contact_use_cases.py와 같은
이유). 메서드 이름은 web의 `UseCaseProvider` 계약이다.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.deal.apply_change import ApplyDealChange
    from app.application.deal.delete_deal import DeleteDeal
    from app.application.deal.deletion_impact import GetDealDeletionImpact
    from app.application.deal.get_deal import GetDeal
    from app.application.deal.list_deal_history import ListDealHistory
    from app.application.deal.list_deals import ListDeals
    from app.application.deal.list_facets import ListDealFacets
    from app.application.deal.register_deal import RegisterDeal
    from app.application.deal.update_deal import UpdateDeal
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.deal_code_source import FakeDealCodeSuffixSource
    from tests.fakes.file_storage import FakeFileStorage


class DealUseCases:
    """`_deal_uow_factory`(UnitOfWorkFactory)와 `clock`을 가진 클래스에 섞는다."""

    clock: Clock
    suffix_source: FakeDealCodeSuffixSource
    file_storage: FakeFileStorage

    def _deal_uow_factory(self) -> UnitOfWorkFactory:
        raise NotImplementedError

    def register_deal(self) -> RegisterDeal:
        from app.application.deal.register_deal import RegisterDeal  # noqa: PLC0415

        return RegisterDeal(self._deal_uow_factory(), self.clock, self.suffix_source)

    def get_deal(self) -> GetDeal:
        from app.application.deal.get_deal import GetDeal  # noqa: PLC0415

        return GetDeal(self._deal_uow_factory(), self.clock)

    def list_deals(self) -> ListDeals:
        from app.application.deal.list_deals import ListDeals  # noqa: PLC0415

        return ListDeals(self._deal_uow_factory(), self.clock)

    def update_deal(self) -> UpdateDeal:
        from app.application.deal.update_deal import UpdateDeal  # noqa: PLC0415

        return UpdateDeal(self._deal_uow_factory(), self.clock)

    def delete_deal(self) -> DeleteDeal:
        from app.application.deal.delete_deal import DeleteDeal  # noqa: PLC0415

        return DeleteDeal(self._deal_uow_factory(), self.clock, self.file_storage)

    def apply_deal_change(self) -> ApplyDealChange:
        from app.application.deal.apply_change import ApplyDealChange  # noqa: PLC0415

        return ApplyDealChange(self._deal_uow_factory(), self.clock)

    def get_deal_deletion_impact(self) -> GetDealDeletionImpact:
        from app.application.deal.deletion_impact import GetDealDeletionImpact  # noqa: PLC0415

        return GetDealDeletionImpact(self._deal_uow_factory())

    def list_deal_facets(self) -> ListDealFacets:
        from app.application.deal.list_facets import ListDealFacets  # noqa: PLC0415

        return ListDealFacets(self._deal_uow_factory())

    def list_deal_history(self) -> ListDealHistory:
        from app.application.deal.list_deal_history import ListDealHistory  # noqa: PLC0415

        return ListDealHistory(self._deal_uow_factory())
