"""Repository Port의 InMemory 구현(Fake). 단위 테스트와 계약 테스트에서 사용한다."""

import copy
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.customer.entities import Customer
from app.domain.customer.errors import CustomerInUseError, CustomerNotFoundError
from app.domain.deal import errors as deal_errors
from app.domain.deal.entities import Deal
from app.domain.deal.errors import DealNotFoundError, DuplicateDealCodeError
from app.domain.deal.pipeline import StageTotal
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.errors import DealActionNotFoundError
from app.domain.partner.entities import Partner
from app.domain.partner.errors import PartnerInUseError, PartnerNotFoundError
from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from app.application.ports.customer_repository import CustomerQuery
    from app.application.ports.deal_action_repository import DealActionQuery
    from app.application.ports.deal_repository import DealQuery
    from app.application.ports.partner_repository import PartnerQuery
    from app.domain.customer.value_objects import CustomerId
    from app.domain.deal.stage import DealStage
    from app.domain.deal.value_objects import DealCode, DealId
    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.partner.value_objects import PartnerId
    from app.domain.user.value_objects import UserId


def _contact_matches(entity: Customer | Partner, keyword: str | None) -> bool:
    """키워드 대상: 회사명·담당자명·직함·이메일·전화번호(None은 건너뜀). 고객 비고는 제외."""
    if keyword is None:
        return True
    details = entity.details
    email = details.email.value if details.email else None
    phone = details.phone.value if details.phone else None
    fields = (details.company_name, details.contact_name, details.contact_title, email, phone)
    return any(keyword in text.lower() for text in fields if text is not None)


def _search[EntityT: Customer | Partner](
    items: Sequence[EntityT], query: CustomerQuery | PartnerQuery
) -> list[EntityT]:
    keyword = query.keyword.lower() if query.keyword else None
    found = [i for i in items if _contact_matches(i, keyword)]
    found.sort(key=lambda i: (i.created_at, str(i.id)))
    return [copy.deepcopy(i) for i in found[query.offset : query.offset + query.limit]]


class DealReferrers(Protocol):
    async def exists_for_customer(self, customer_id: CustomerId) -> bool: ...
    async def exists_for_partner(self, partner_id: PartnerId) -> bool: ...


class FakeCustomerRepository(InMemoryStore[Customer]):
    def __init__(self) -> None:
        super().__init__("customer", CustomerNotFoundError)
        self._referrers: list[DealReferrers] = []

    async def add(self, customer: Customer) -> None:
        self._insert(customer)

    async def get(self, customer_id: CustomerId) -> Customer:
        return self._fetch(customer_id)

    async def list(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[Customer]:
        return self._fetch_page(offset, limit)

    async def search(self, query: CustomerQuery) -> Sequence[Customer]:
        return _search(list(self._items.values()), query)

    async def update(self, customer: Customer) -> None:
        self._replace(customer)

    def restrict_delete_by(self, *referrers: DealReferrers) -> None:
        """참조하는 Deal 저장소가 있으면 delete가 CustomerInUseError가 된다(FK RESTRICT 모사)."""
        self._referrers.extend(referrers)

    async def delete(self, customer_id: CustomerId) -> None:
        self._fetch(customer_id)
        for referrer in self._referrers:
            if await referrer.exists_for_customer(customer_id):
                raise CustomerInUseError(customer_id)
        self._remove(customer_id)


class FakePartnerRepository(InMemoryStore[Partner]):
    def __init__(self) -> None:
        super().__init__("partner", PartnerNotFoundError)
        self._referrers: list[DealReferrers] = []

    async def add(self, partner: Partner) -> None:
        self._insert(partner)

    async def get(self, partner_id: PartnerId) -> Partner:
        return self._fetch(partner_id)

    async def list(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[Partner]:
        return self._fetch_page(offset, limit)

    async def search(self, query: PartnerQuery) -> Sequence[Partner]:
        return _search(list(self._items.values()), query)

    async def update(self, partner: Partner) -> None:
        self._replace(partner)

    def restrict_delete_by(self, *referrers: DealReferrers) -> None:
        """참조하는 Deal 저장소가 있으면 delete가 PartnerInUseError가 된다(FK RESTRICT 모사)."""
        self._referrers.extend(referrers)

    async def delete(self, partner_id: PartnerId) -> None:
        self._fetch(partner_id)
        for referrer in self._referrers:
            if await referrer.exists_for_partner(partner_id):
                raise PartnerInUseError(partner_id)
        self._remove(partner_id)


class DealDependents(Protocol):
    async def exists_for_deal(self, deal_id: DealId) -> bool: ...


def _deal_matches(deal: Deal, query: DealQuery, owner_names: Callable[[UserId], list[str]]) -> bool:
    details = deal.details
    keyword = query.keyword.lower() if query.keyword else None
    searchable = (
        details.code.value,
        details.name,
        details.vendor,
        details.solution,
        *owner_names(details.owner_user_id),
    )
    return (
        (query.stage is None or deal.stage is query.stage)
        and (keyword is None or any(keyword in text.lower() for text in searchable))
        and (query.customer_id is None or details.customer_id == query.customer_id)
        and (query.partner_id is None or details.partner_id == query.partner_id)
        and (query.owner_user_id is None or details.owner_user_id == query.owner_user_id)
        and (query.vendor is None or details.vendor == query.vendor)
        and (query.revenue_from is None or details.revenue_date >= query.revenue_from)
        and (query.revenue_to is None or details.revenue_date < query.revenue_to)
    )


class FakeDealRepository(InMemoryStore[Deal]):
    def __init__(self) -> None:
        super().__init__("deal", DealNotFoundError)
        self.for_update_gets: list[DealId] = []  # 잠금 조회(for_update=True)로 읽은 Deal id 기록
        self._dependents: list[DealDependents] = []  # FK RESTRICT를 모사할 자식 저장소들
        self._owner_names: Callable[[UserId], list[str]] = lambda _: []

    def attach_user_names(self, names_of: Callable[[UserId], list[str]]) -> None:
        """키워드 검색이 담당자 이름(users 조인)을 보도록 사용자 이름 조회를 연결한다."""
        self._owner_names = names_of

    def restrict_delete_by(self, *dependents: DealDependents) -> None:
        """자식 저장소(활동·단계 이력)에 행이 있으면 delete가 DealInUseError가 된다(FK RESTRICT)."""
        self._dependents.extend(dependents)

    def _ensure_code_is_free(self, deal: Deal) -> None:
        """Deal Code는 존재하는 Deal 전체에서 고유하다."""
        for other in self._items.values():
            if other.id != deal.id and other.details.code == deal.details.code:
                raise DuplicateDealCodeError(deal.details.code)

    async def add(self, deal: Deal) -> None:
        self._ensure_code_is_free(deal)
        self._insert(deal)

    async def get(self, deal_id: DealId, *, for_update: bool = False) -> Deal:
        if for_update:
            self.for_update_gets.append(deal_id)  # 행 잠금 자체는 Fake에 없고 호출만 기록한다
        return self._fetch(deal_id)

    async def get_by_code(self, code: DealCode) -> Deal:
        for deal in self._items.values():
            if deal.details.code == code:
                return self._fetch(deal.id)
        raise DealNotFoundError(code)

    async def list(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[Deal]:
        return self._fetch_page(offset, limit)

    async def search(self, query: DealQuery) -> Sequence[Deal]:
        found = [d for d in self._items.values() if _deal_matches(d, query, self._owner_names)]
        found.sort(key=lambda d: (d.created_at, str(d.id)))
        return [copy.deepcopy(d) for d in found[query.offset : query.offset + query.limit]]

    async def summarize_pipeline(
        self, *, owner_user_id: UserId | None = None
    ) -> Sequence[StageTotal]:
        grouped: dict[tuple[DealStage, str], tuple[int, Decimal]] = {}
        for deal in self._items.values():
            if owner_user_id is not None and deal.details.owner_user_id != owner_user_id:
                continue
            key = (deal.stage, deal.details.revenue.currency)
            count, amount = grouped.get(key, (0, Decimal(0)))
            grouped[key] = (count + 1, amount + deal.details.revenue.amount)
        return [StageTotal(stage, cur, n, amt) for (stage, cur), (n, amt) in grouped.items()]

    async def exists_for_customer(self, customer_id: CustomerId) -> bool:
        return any(d.details.customer_id == customer_id for d in self._items.values())

    async def exists_for_partner(self, partner_id: PartnerId) -> bool:
        return any(d.details.partner_id == partner_id for d in self._items.values())

    async def update(self, deal: Deal) -> None:
        if deal.id in self._items:
            self._ensure_code_is_free(deal)
        self._replace(deal)

    async def delete(self, deal_id: DealId) -> None:
        """물리 삭제. 없으면 DealNotFoundError."""
        self._fetch(deal_id)
        for dependents in self._dependents:
            if await dependents.exists_for_deal(deal_id):
                raise deal_errors.DealInUseError(deal_id)
        del self._items[deal_id]


def _matches(action: DealAction, query: DealActionQuery) -> bool:
    details = action.details
    keyword = query.keyword.lower() if query.keyword else None
    searchable = (details.action, details.next_action or "", details.memo)
    due = details.due_date
    return (
        (query.deal_id is None or details.deal_id == query.deal_id)
        and (query.action_type is None or details.action_type is query.action_type)
        and (query.actor_user_id is None or details.actor_user_id == query.actor_user_id)
        and (query.acted_from is None or details.acted_at >= query.acted_from)
        and (query.acted_to is None or details.acted_at < query.acted_to)
        and (query.due_from is None or (due is not None and due >= query.due_from))
        and (query.due_to is None or (due is not None and due <= query.due_to))
        and (keyword is None or any(keyword in text.lower() for text in searchable))
    )


def _sorted(found: list[DealAction], sort: str) -> list[DealAction]:
    """기본은 acted_at 내림차순. due_date 정렬은 NULL이 항상 마지막이고 동률은 acted_at 내림차순."""
    found.sort(key=lambda a: (-a.details.acted_at.timestamp(), str(a.id)))
    if sort == "acted_at_desc":
        return found
    dated = [a for a in found if a.details.due_date is not None]
    undated = [a for a in found if a.details.due_date is None]
    # 안정 정렬(reverse=True도 동률의 기존 순서를 유지한다)
    dated.sort(key=lambda a: a.details.due_date or date.min, reverse=sort == "due_date_desc")
    return [*dated, *undated]


class FakeDealActionRepository(InMemoryStore[DealAction]):
    def __init__(self) -> None:
        super().__init__("deal_action", DealActionNotFoundError)

    async def add(self, action: DealAction) -> None:
        self._insert(action)

    async def get(self, action_id: DealActionId) -> DealAction:
        return self._fetch(action_id)

    async def search(self, query: DealActionQuery) -> Sequence[DealAction]:
        found = _sorted([a for a in self._items.values() if _matches(a, query)], str(query.sort))
        return [copy.deepcopy(a) for a in found[query.offset : query.offset + query.limit]]

    async def update(self, action: DealAction) -> None:
        self._replace(action)

    async def delete(self, action_id: DealActionId) -> None:
        """물리 삭제. 없으면 DealActionNotFoundError."""
        self._fetch(action_id)
        del self._items[action_id]

    async def exists_for_deal(self, deal_id: DealId) -> bool:
        """행이 있으면 True (FK 판정과 같다)."""
        return any(a.details.deal_id == deal_id for a in self._items.values())
