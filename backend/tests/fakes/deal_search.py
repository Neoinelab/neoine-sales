"""FakeDealRepository의 검색 규칙(SQL 구현과 같은 계약).

- keyword: Deal Name·고객 회사명·**활성** 파트너 회사명·Deal code의 대소문자 무시 부분 일치
  (`%`, `_`, `\\`는 글자 그대로)
- owner_user_id·vendor_id·status_key: 정확 일치
- forecast_keys: 그중 하나와 일치(OR). None이면 조건 없음. forecast_outcome과 AND
- solution: Solution 텍스트의 대소문자 무시 부분 일치(`%`, `_`는 글자 그대로)
- 정렬: 기본 last_updated_at 내림차순, 모든 정렬의 동률은 code 오름차순
- last_updated_at = 가장 최근 활동의 acted_at(없으면 created_at, Deal 수정은 반영하지 않음)

이 모듈은 Deal·연락처 도메인 객체를 속성으로만 읽는다(새 모델 구현이 없어도 가져올 수 있다).
- 연/분기/월: Expected Close가 그 해(분기·월)에 속함(Q1=1~3월 … Q4=10~12월)
- forecast_outcome: Forecast 코드의 outcome이 허용 집합에 듦(open/won/lost, not_lost=open+won).
  outcome은 코드 저장소에서 읽는다(구현의 `ForecastOutcomeFilter.outcomes()`를 베끼지 않는다)
- updated_from/to: last_updated_at의 로컬 업무 날짜가 양끝 포함 범위 안(`updated_in_range`)
- overdue/stale: compute_risk 결과가 해당 집합에 드는 Deal(둘 다면 OR). basis가 없으면 ValueError
"""

import calendar
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from app.domain.deal.risk import Risk, compute_risk

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from app.application.ports.deal_repository import DealQuery
    from app.domain.deal.risk import RiskBasis


def company_of(contacts: Mapping[Any, Any], contact_id: Any) -> str:  # noqa: ANN401
    contact = contacts.get(contact_id)
    return str(contact.details.company) if contact is not None else ""


_ALLOWED_OUTCOMES: dict[str, frozenset[str]] = {
    "open": frozenset({"open"}),
    "won": frozenset({"won"}),
    "lost": frozenset({"lost"}),
    "not_lost": frozenset({"open", "won"}),
}


def outcome_allowed(query: DealQuery, forecast_key: str, outcome_of: Callable[[str], str]) -> bool:
    """query.forecast_outcome이 있으면 그 Forecast 코드의 outcome이 허용 집합에 드는가."""
    wanted = getattr(query, "forecast_outcome", None)
    if wanted is None:
        return True
    return outcome_of(forecast_key) in _ALLOWED_OUTCOMES[str(wanted)]


def _in_quarters(query: DealQuery, day: date) -> bool:
    """범위 안에서 분기 집합으로 한 번 더 거른다(떨어진 분기 Q1·Q3 사이의 Q2 제외)."""
    quarters = getattr(query, "quarters", None)
    return quarters is None or (day.month - 1) // 3 + 1 in quarters


def matches(
    deal: Any,  # noqa: ANN401
    query: DealQuery,
    contacts: Mapping[Any, Any],
    outcome_of: Callable[[str], str] | None = None,
) -> bool:
    details = deal.details
    if outcome_of is not None and not outcome_allowed(query, deal.sync.forecast_key, outcome_of):
        return False
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
    if query.solution and query.solution.lower() not in details.solution.lower():
        return False
    equals: tuple[tuple[Any, Any], ...] = (
        (query.owner_user_id, details.owner_user_id),
        (query.vendor_id, details.vendor_id),
        (query.status_key, deal.sync.status_key),
    )
    keys = query.forecast_keys
    if any(wanted is not None and wanted != actual for wanted, actual in equals) or (
        keys is not None and deal.sync.forecast_key not in keys
    ):
        return False
    start, end = revenue_bounds(query)
    if start is not None and details.revenue_date < start:
        return False
    return (end is None or details.revenue_date <= end) and _in_quarters(
        query, details.revenue_date
    )


def revenue_bounds(query: DealQuery) -> tuple[date | None, date | None]:
    """연/분기 범위(양끝 포함). 연도가 없으면 열린 범위다.

    DealQuery.revenue_window와 독립적으로 계산한다(Fake가 구현을 베끼지 않도록).
    """
    if query.year is None:
        if (
            getattr(query, "quarters", None) is not None
            or getattr(query, "month", None) is not None
        ):
            # 저장소는 연도가 정해진 질의만 받는다
            msg = "quarter만 있는 질의는 연도를 채운 뒤 조회해야 한다"
            raise ValueError(msg)
        return None, None
    month = getattr(query, "month", None)  # 월 필터(P6): 분기와 배타, 그 달 1일~말일
    if month is not None:
        first_month = last_month = month
    else:
        quarters = getattr(query, "quarters", None)
        picked = sorted(quarters) if quarters else [1, 2, 3, 4]
        first_month = (picked[0] - 1) * 3 + 1
        last_month = picked[-1] * 3
    period_start = date(query.year, first_month, 1)
    period_end = date(query.year, last_month, calendar.monthrange(query.year, last_month)[1])
    return period_start, period_end


def updated_in_range(last_updated_at: datetime, query: DealQuery) -> bool:
    """last_updated_at의 로컬 업무 날짜가 updated_from/to(양끝 포함) 안인가.

    DealQuery.updated_window와 독립적으로 날짜 비교로 계산한다.
    """
    day = last_updated_at.astimezone().date()
    updated_from, updated_to = _updated_bounds(query)
    if updated_from is not None and day < updated_from:
        return False
    return not (updated_to is not None and day > updated_to)


def _updated_bounds(query: DealQuery) -> tuple[date | None, date | None]:
    return query.updated_from, query.updated_to


def has_updated_period(query: DealQuery) -> bool:
    return _updated_bounds(query) != (None, None)


def check_risk_basis(query: DealQuery) -> RiskBasis:
    """위험 필터가 있는데 기준이 없으면 프로그래밍 오류(저장소 계약)."""
    if query.risk_basis is None:
        msg = "overdue/stale 필터에는 risk_basis가 필요하다"
        raise ValueError(msg)
    return query.risk_basis


def risk_matches(
    query: DealQuery, *, forecast_key: str, due_date: date | None, last_updated_at: datetime
) -> bool:
    """overdue/stale 필터. 판정은 compute_risk로 독립 계산한다(SQL 경계 변환을 베끼지 않음)."""
    if not query.wants_risk():
        return True
    basis = check_risk_basis(query)
    risk = compute_risk(
        forecast_key=forecast_key,
        due_date=due_date,
        last_updated_at=last_updated_at,
        today=basis.today,
        stale_days=basis.stale_days,
    )
    wanted: set[Risk] = set()
    if query.overdue:
        wanted |= {Risk.OVERDUE, Risk.OVERDUE_STALE}
    if query.stale:
        wanted |= {Risk.STALE, Risk.OVERDUE_STALE}
    return risk in wanted
