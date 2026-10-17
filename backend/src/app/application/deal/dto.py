from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.ports.deal_repository import DealListItem
    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactId
    from app.domain.deal.history import DealHistoryEntry
    from app.domain.deal.risk import Risk
    from app.domain.deal.sync import CoChange
    from app.domain.user.value_objects import UserRef


@dataclass(frozen=True, slots=True)
class DealView:
    """Deal 한 건과 화면에 필요한 참조(Owner, 고객, 모든 파트너 링크의 연락처)."""

    item: DealListItem
    owner: UserRef
    customer: Contact
    partner_contacts: Mapping[ContactId, Contact]
    risk: Risk | None
    status_days: int


@dataclass(frozen=True, slots=True)
class DealPage:
    items: list[DealView]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class ApplyChangeResult:
    """단일 변경의 결과: 갱신된 Deal, 함께 바뀐 값, 안내 문구."""

    view: DealView
    co_changed: tuple[CoChange, ...]
    notice: str | None


@dataclass(frozen=True, slots=True)
class DealFacets:
    """목록 필터용 Vendor·Solution 값(빈 값 제외, 대소문자 무시 순서)."""

    vendors: Sequence[str]
    solutions: Sequence[str]


@dataclass(frozen=True, slots=True)
class HistoryEntryView:
    """History 항목과 변경자 참조(퇴사자 포함)."""

    entry: DealHistoryEntry
    by: UserRef
