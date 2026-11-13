"""Action 수행일(`acted_on`) 규칙. 업무 날짜·시간대는 서버 OS 로컬이다."""

from typing import TYPE_CHECKING

from app.domain.common.business_date import business_date
from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from datetime import date, datetime


def resolve_acted_on(acted_on: date | None, *, now: datetime, deal_registered_at: datetime) -> date:
    """수행일. 없으면 오늘, 오늘 이후나 Deal 등록일 이전은 거절한다(업무 날짜 기준)."""
    today = business_date(now)
    if acted_on is None:
        return today
    if acted_on > today:
        raise InvalidValueError("수행일은 오늘 이후로 지정할 수 없습니다.")
    registered_on = business_date(deal_registered_at)
    if acted_on < registered_on:
        raise InvalidValueError(
            f"수행일은 Deal 등록일({registered_on.isoformat()}) 이전으로 지정할 수 없습니다."
        )
    return acted_on


def ensure_not_before_basis(acted_on: date, basis_acted_on: date) -> None:
    """이전 Next Action을 닫는 수행일은 기준 행의 수행일보다 앞설 수 없다."""
    if acted_on < basis_acted_on:
        raise InvalidValueError(
            f"이전 Next Action의 수행일({basis_acted_on.isoformat()})보다 앞선 날짜로는 "
            "이전 Next Action을 종료할 수 없습니다."
        )
