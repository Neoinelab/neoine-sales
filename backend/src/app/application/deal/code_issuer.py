"""Deal code를 발급하며 Deal을 저장한다. 같은 날 code가 겹치면 다시 뽑는다(전체 10회까지)."""

from typing import TYPE_CHECKING

from app.domain.common.business_date import business_date
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealCodeIssueError, DuplicateDealCodeError

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from app.application.ports.deal_code_source import DealCodeSuffixSource
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.deal.entities import Deal

MAX_ATTEMPTS = 10


async def add_with_issued_code(
    uow: UnitOfWork,
    source: DealCodeSuffixSource,
    now: datetime,
    build: Callable[[DealCode], Deal],
) -> Deal:
    """새 code로 `build`가 만든 Deal을 저장해 돌려준다. 10번 모두 겹치면 DealCodeIssueError.

    이미 있는 code는 저장하기 전에 확인하고, 확인과 저장 사이의 경쟁은 저장소의
    DuplicateDealCodeError로 잡아 같은 방식으로 다시 뽑는다.
    """
    day = business_date(now)
    for _ in range(MAX_ATTEMPTS):
        code = DealCode.issue(day, source.next_suffix())
        if await uow.deals.exists(code):
            continue
        deal = build(code)
        try:
            await uow.deals.add(deal)
        except DuplicateDealCodeError:
            continue
        return deal
    raise DealCodeIssueError
