"""FakeDealRepository의 목록 정렬 키(SQL 구현과 같은 계약).

- 텍스트 열(owner·customer·partner·vendor)은 소문자 문자열의 코드 포인트 순
- owner: 담당자 표시 이름, 없으면 login_id. 퇴사자도 같다
- partner: **활성** 파트너 회사명, vendor: Vendor 이름. 없으면 키가 None이고 호출부가 방향과
  무관하게 맨 뒤에 둔다
- status·forecast: 코드의 현재 순서
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tests.fakes.deal_search import company_of

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


@dataclass
class SortLookups:
    """정렬 키 계산에 필요한 참조 저장소의 내용."""

    status_order: Callable[[str], int]
    forecast_order: Callable[[str], int]
    contacts: Mapping[Any, Any] = field(default_factory=dict)
    users: Mapping[Any, Any] = field(default_factory=dict)
    vendors: Mapping[Any, Any] = field(default_factory=dict)


def _owner(deal: Any, lookups: SortLookups) -> str:  # noqa: ANN401
    user = lookups.users.get(deal.details.owner_user_id)
    if user is None:
        return ""
    return str(user.display_name or user.login_id.value).lower()


def _partner(deal: Any, lookups: SortLookups) -> str | None:  # noqa: ANN401
    active = deal.active_partner_id()
    return None if active is None else company_of(lookups.contacts, active).lower()


def _vendor(deal: Any, lookups: SortLookups) -> str | None:  # noqa: ANN401
    vendor_id = deal.details.vendor_id
    vendor = lookups.vendors.get(vendor_id) if vendor_id is not None else None
    return None if vendor is None else str(vendor.name).lower()


def sort_key(sort: str, lookups: SortLookups) -> Callable[[Any, Any], Any]:
    """(deal, last_updated_at) -> 정렬 키(None이면 맨 뒤). 동률은 호출부가 code 순으로 한다."""
    by_deal: dict[str, Callable[[Any], Any]] = {
        "name": lambda d: d.details.name.lower(),
        "revenue_amount": lambda d: d.details.revenue_amount.value,
        "revenue_date": lambda d: d.details.revenue_date,
        "status": lambda d: lookups.status_order(d.sync.status_key),
        "owner": lambda d: _owner(d, lookups),
        "customer": lambda d: company_of(lookups.contacts, d.customer_id).lower(),
        "partner": lambda d: _partner(d, lookups),
        "vendor": lambda d: _vendor(d, lookups),
        "forecast": lambda d: lookups.forecast_order(d.sync.forecast_key),
    }
    extract = by_deal.get(sort)

    def key(deal: Any, last_updated: Any) -> Any:  # noqa: ANN401
        return last_updated if extract is None else extract(deal)

    return key
