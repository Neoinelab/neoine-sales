"""Deal 조회 유스케이스 조립 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.deal.deal_years import GetDealYears
from app.application.deal.deletion_impact import GetDealDeletionImpact
from app.application.deal.get_deal import GetDeal
from app.application.deal.list_deal_history import ListDealHistory
from app.application.deal.list_deals import ListDeals
from app.application.deal.updated_periods import ListUpdatedPeriods

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class DealReadUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock

    def get_deal(self) -> GetDeal:
        return GetDeal(self._uow, self._clock)

    def list_deals(self) -> ListDeals:
        return ListDeals(self._uow, self._clock)

    def list_updated_periods(self) -> ListUpdatedPeriods:
        return ListUpdatedPeriods(self._clock)

    def list_deal_history(self) -> ListDealHistory:
        return ListDealHistory(self._uow)

    def get_deal_deletion_impact(self) -> GetDealDeletionImpact:
        return GetDealDeletionImpact(self._uow)

    def get_deal_years(self) -> GetDealYears:
        return GetDealYears(self._uow)
