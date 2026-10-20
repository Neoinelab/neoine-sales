"""FakeDealRepository의 검색 규칙(SQL 구현과 같은 계약).

- keyword: Deal Name·고객 회사명·**활성** 파트너 회사명·Deal code의 대소문자 무시 부분 일치
  (`%`, `_`, `\\`는 글자 그대로)
- owner_user_id·vendor_id·solution_id·status_key·forecast_key: 정확 일치, revenue_from/to: 양끝 포함
- 정렬: 기본 last_updated_at 내림차순, 모든 정렬의 동률은 code 오름차순
- last_updated_at = 가장 최근 활동의 acted_at(없으면 created_at, Deal 수정은 반영하지 않음)

이 모듈은 Deal·연락처 도메인 객체를 속성으로만 읽는다(새 모델 구현이 없어도 가져올 수 있다).
- 연/분기: Expected Close가 그 해(분기)에 속함, revenue_from/to와 교집합(Q1=1~3월 … Q4=10~12월)
- BANT: 구분별로 그 Label이 선택된 Deal만, 여러 구분이면 AND
"""

import calendar
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from app.application.ports.deal_repository import DealQuery


def company_of(contacts: Mapping[Any, Any], contact_id: Any) -> str:  # noqa: ANN401
    contact = contacts.get(contact_id)
    return str(contact.details.company) if contact is not None else ""


def matches(
    deal: Any,  # noqa: ANN401
    query: DealQuery,
    contacts: Mapping[Any, Any],
) -> bool:
    details = deal.details
    if query.keyword:
        needle = query.keyword.lower()
        active = deal.active_partner_id()
        texts = (
            details.name,
            company_of(contacts, deal.customer_id),
            company_of(contacts, active) if active is not None else "",
            deal.id.value,
        )
        if not any(needle in text.lower() for text in texts):
            return False
    equals: tuple[tuple[Any, Any], ...] = (
        (query.owner_user_id, details.owner_user_id),
        (query.vendor_id, details.vendor_id),
        (query.solution_id, details.solution_id),
        (query.status_key, deal.sync.status_key),
        (query.forecast_key, deal.sync.forecast_key),
    )
    if any(wanted is not None and wanted != actual for wanted, actual in equals):
        return False
    start, end = revenue_bounds(query)
    if start is not None and details.revenue_date < start:
        return False
    if end is not None and details.revenue_date > end:
        return False
    return all(
        deal.bant.get(category) == label_id for category, label_id in query.bant_label_ids.items()
    )


def revenue_bounds(query: DealQuery) -> tuple[date | None, date | None]:
    """연/분기 범위와 revenue_from/to의 교집합(양끝 포함). 시작이 끝보다 늦으면 0건이다.

    DealQuery.revenue_window와 독립적으로 계산한다(Fake가 구현을 베끼지 않도록).
    """
    start, end = query.revenue_from, query.revenue_to
    if query.year is None:
        if query.quarter is not None:  # 저장소는 연도가 정해진 질의만 받는다
            msg = "quarter만 있는 질의는 연도를 채운 뒤 조회해야 한다"
            raise ValueError(msg)
        return start, end
    first_month = 1 if query.quarter is None else (query.quarter - 1) * 3 + 1
    last_month = 12 if query.quarter is None else query.quarter * 3
    period_start = date(query.year, first_month, 1)
    period_end = date(query.year, last_month, calendar.monthrange(query.year, last_month)[1])
    return (
        period_start if start is None else max(start, period_start),
        period_end if end is None else min(end, period_end),
    )


def sort_key(sort: str, status_order: Callable[[str], int]) -> Callable[[Any, Any], Any]:
    """(deal, last_updated_at) -> 정렬 키. 동률 처리(code 오름차순)는 호출부가 한다."""

    def key(deal: Any, last_updated: Any) -> Any:  # noqa: ANN401
        details = deal.details
        if sort == "name":
            return details.name.lower()
        if sort == "revenue_amount":
            return details.revenue_amount.value
        if sort == "revenue_date":
            return details.revenue_date
        if sort == "status":
            return status_order(deal.sync.status_key)
        return last_updated

    return key
