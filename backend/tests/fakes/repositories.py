"""Repository Port의 InMemory 구현(Fake). 단위 테스트와 계약 테스트에서 사용한다."""

import copy
from typing import TYPE_CHECKING

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.customer.entities import Customer
from app.domain.customer.errors import CustomerNotFoundError
from app.domain.deal.entities import Deal
from app.domain.deal.errors import DealNotFoundError, DuplicateDealCodeError
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.errors import DealActionNotFoundError
from app.domain.partner.entities import Partner
from app.domain.partner.errors import PartnerNotFoundError
from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.deal_action_repository import DealActionQuery
    from app.domain.customer.value_objects import CustomerId
    from app.domain.deal.value_objects import DealCode, DealId
    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.partner.value_objects import PartnerId


class FakeCustomerRepository(InMemoryStore[Customer]):
    def __init__(self) -> None:
        super().__init__("customer", CustomerNotFoundError)

    async def add(self, customer: Customer) -> None:
        self._insert(customer)

    async def get(self, customer_id: CustomerId, *, include_deleted: bool = False) -> Customer:
        return self._fetch(customer_id, include_deleted=include_deleted)

    async def list(
        self, *, offset: int = 0, limit: int = DEFAULT_LIMIT, include_deleted: bool = False
    ) -> Sequence[Customer]:
        return self._fetch_page(offset, limit, include_deleted=include_deleted)

    async def update(self, customer: Customer) -> None:
        self._replace(customer)


class FakePartnerRepository(InMemoryStore[Partner]):
    def __init__(self) -> None:
        super().__init__("partner", PartnerNotFoundError)

    async def add(self, partner: Partner) -> None:
        self._insert(partner)

    async def get(self, partner_id: PartnerId, *, include_deleted: bool = False) -> Partner:
        return self._fetch(partner_id, include_deleted=include_deleted)

    async def list(
        self, *, offset: int = 0, limit: int = DEFAULT_LIMIT, include_deleted: bool = False
    ) -> Sequence[Partner]:
        return self._fetch_page(offset, limit, include_deleted=include_deleted)

    async def update(self, partner: Partner) -> None:
        self._replace(partner)


class FakeDealRepository(InMemoryStore[Deal]):
    def __init__(self) -> None:
        super().__init__("deal", DealNotFoundError)

    def _ensure_code_is_free(self, deal: Deal) -> None:
        """Deal Code는 삭제된 Deal을 포함한 전체에서 고유하다."""
        for other in self._items.values():
            if other.id != deal.id and other.details.code == deal.details.code:
                raise DuplicateDealCodeError(deal.details.code)

    async def add(self, deal: Deal) -> None:
        self._ensure_code_is_free(deal)
        self._insert(deal)

    async def get(self, deal_id: DealId, *, include_deleted: bool = False) -> Deal:
        return self._fetch(deal_id, include_deleted=include_deleted)

    async def get_by_code(self, code: DealCode, *, include_deleted: bool = False) -> Deal:
        for deal in self._items.values():
            if deal.details.code == code:
                return self._fetch(deal.id, include_deleted=include_deleted)
        raise DealNotFoundError(code)

    async def list(
        self, *, offset: int = 0, limit: int = DEFAULT_LIMIT, include_deleted: bool = False
    ) -> Sequence[Deal]:
        return self._fetch_page(offset, limit, include_deleted=include_deleted)

    async def has_active_for_customer(self, customer_id: CustomerId) -> bool:
        return any(
            d.details.customer_id == customer_id and not d.is_deleted for d in self._items.values()
        )

    async def has_active_for_partner(self, partner_id: PartnerId) -> bool:
        return any(
            d.details.partner_id == partner_id and not d.is_deleted for d in self._items.values()
        )

    async def update(self, deal: Deal) -> None:
        if deal.id in self._items:
            self._ensure_code_is_free(deal)
        self._replace(deal)


def _matches(action: DealAction, query: DealActionQuery) -> bool:
    details = action.details
    keyword = query.keyword.lower() if query.keyword else None
    return (
        not action.is_deleted
        and (query.deal_id is None or details.deal_id == query.deal_id)
        and (query.action_type is None or details.action_type is query.action_type)
        and (query.actor is None or details.actor == query.actor)
        and (query.acted_from is None or details.acted_at >= query.acted_from)
        and (query.acted_to is None or details.acted_at < query.acted_to)
        and (
            keyword is None
            or keyword in details.title.lower()
            or keyword in details.content.lower()
        )
    )


class FakeDealActionRepository(InMemoryStore[DealAction]):
    def __init__(self) -> None:
        super().__init__("deal_action", DealActionNotFoundError)

    async def add(self, action: DealAction) -> None:
        self._insert(action)

    async def get(self, action_id: DealActionId, *, include_deleted: bool = False) -> DealAction:
        return self._fetch(action_id, include_deleted=include_deleted)

    async def search(self, query: DealActionQuery) -> Sequence[DealAction]:
        found = [a for a in self._items.values() if _matches(a, query)]
        found.sort(key=lambda a: (-a.details.acted_at.timestamp(), str(a.id)))
        return [copy.deepcopy(a) for a in found[query.offset : query.offset + query.limit]]

    async def update(self, action: DealAction) -> None:
        self._replace(action)
