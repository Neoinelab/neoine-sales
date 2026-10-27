"""Reports 조회 계약 테스트 공용 case (SQL 전용).

`FakeReportQueryRunner`는 SQL 엔진을 흉내 내지 않으므로(계획 4.7 "Fake 방침") Fake↔SQL 공통
계약은 없고, SQL 구현만 실제 PostgreSQL 임시 DB로 검증한다. case는 `DealCase`(Deal·사용자·Vendor·
코드·Action 준비 도우미와 Deal 저장소 원장)와 `SqlReportQueryRunner`를 가진다.

조회 컨텍스트는 오늘 2026-10-27, 업무 오프셋 +09:00, 경고 기준 14일로 고정한다. 날짜 경계는
OS 시간대에 흔들리지 않게 case를 만드는 fixture가 `Asia/Seoul`로 맞춘다.
"""

import itertools
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pytest

from tests.factories import make_deal
from tests.support.database import rolled_back_session
from tests.support.report_defs import context, resolved
from tests.support.user_ids import OWNER_ID
from tests.unit.repositories.deal_case import DealCase, _sql_case

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.application.ports.report_query_runner import ReportRows
    from app.domain.deal.entities import Deal
    from app.domain.user.value_objects import UserId

PARAMS = [pytest.param("sql", id="sql", marks=pytest.mark.integration)]

KST = timezone(timedelta(hours=9))
TODAY = date(2026, 10, 27)


def kst(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    """업무 시간대(+09:00)의 시각."""
    return datetime(year, month, day, hour, minute, tzinfo=KST)


@dataclass
class ReportCase:
    deals: DealCase
    runner: Any
    session: AsyncSession
    _numbers: Any = field(default_factory=lambda: itertools.count(1), repr=False)

    async def add_deal(  # noqa: PLR0913 - 리포트 축이 모두 독립적인 선택지
        self,
        *,
        name: str = "Deal",
        amount: int = 100,
        day: date = date(2026, 6, 30),
        forecast: str = "pipeline",
        status: str | None = None,
        vendor_id: int | None = None,
        owner: UserId = OWNER_ID,
        created: datetime | None = None,
        **details: Any,  # noqa: ANN401 - make_deal의 상세 필드
    ) -> Deal:
        """Deal 하나를 저장한다. Won은 계약완료 Status와 함께만 있다. code는 20261016-NNNN."""
        number = next(self._numbers)
        deal = make_deal(
            created or kst(2026, 10, 1, 9) + timedelta(seconds=number),
            code=f"20261016-{number:04d}",
            name=name,
            revenue_amount=amount,
            revenue_date=day,
            forecast_key=forecast,
            status_key=status or ("contract_completed" if forecast == "won" else "prospecting"),
            owner_user_id=owner,
            vendor_id=vendor_id,
            **details,
        )
        await self.deals.add(deal)
        return deal

    async def type_id(self, name: str) -> int:
        """저장소(DB 시드)의 Action 유형 id."""
        found = next(t for t in await self.deals.action_types.list() if t.name == name)
        return int(found.id)

    async def run(
        self,
        columns: Sequence[dict[str, Any]],
        conditions: Sequence[dict[str, Any]] = (),
        **top: Any,  # noqa: ANN401 - combine, sort, row_limit
    ) -> ReportRows:
        result: ReportRows = await self.runner.run(
            resolved(columns, conditions, ctx=context(), **top)
        )
        return result

    async def rows(
        self,
        columns: Sequence[dict[str, Any]],
        conditions: Sequence[dict[str, Any]] = (),
        **top: Any,  # noqa: ANN401
    ) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in (await self.run(columns, conditions, **top)).rows]


@asynccontextmanager
async def open_report_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[ReportCase]:
    assert implementation == "sql"
    from app.infra.db.report_runner import SqlReportQueryRunner  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield ReportCase(_sql_case(session), SqlReportQueryRunner(session), session)
