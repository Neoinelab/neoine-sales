"""Repository Port의 InMemory 구현(Fake). 단위 테스트와 계약 테스트에서 사용한다."""

from typing import TYPE_CHECKING

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.customer.entities import Customer
from app.domain.customer.errors import CustomerNotFoundError
from app.domain.deal.entities import Deal
from app.domain.deal.errors import DealNotFoundError, DuplicateDealCodeError
from app.domain.partner.entities import Partner
from app.domain.partner.errors import PartnerNotFoundError
from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.customer.value_objects import CustomerId
    from app.domain.deal.value_objects import DealCode, DealId
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

    async def update(self, deal: Deal) -> None:
        if deal.id in self._items:
            self._ensure_code_is_free(deal)
        self._replace(deal)
