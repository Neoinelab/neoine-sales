"""ReportQueryRunner Port의 SQLAlchemy 구현: 읽기 전용 가드 안에서 SQL을 실행한다."""

import time
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,  # noqa: TC002 - 시그니처 검사(inspect)가 런타임에 해석한다
)

from app.application.ports.report_query_runner import ReportRows
from app.domain.report.vocabulary import STATEMENT_TIMEOUT_SECONDS
from app.infra.db.read_only import read_only_guard
from app.infra.db.report_render import convert_row, display_sql
from app.infra.db.report_select import build_select, build_totals_select

if TYPE_CHECKING:
    from app.domain.report.resolve import ResolvedReport

_MS_PER_SECOND = 1000
REPORT_STATEMENT_TIMEOUT_MS = STATEMENT_TIMEOUT_SECONDS * _MS_PER_SECOND


class SqlReportQueryRunner:
    def __init__(
        self, session: AsyncSession, timeout_ms: int = REPORT_STATEMENT_TIMEOUT_MS
    ) -> None:
        self._session = session
        self._timeout_ms = timeout_ms

    async def run(self, report: ResolvedReport) -> ReportRows:
        """정의를 SQL로 바꿔 읽기 전용으로 실행한다. 시간 초과면 ReportQueryTimeoutError."""
        value_types = [column.value_type() for column in report.definition.columns]
        data = build_select(report)
        totals = build_totals_select(report)
        started = time.perf_counter()
        async with read_only_guard(self._session, self._timeout_ms):
            found = (await self._session.execute(data)).all()
            totals_row = (await self._session.execute(totals)).one() if totals is not None else None
        elapsed_ms = int((time.perf_counter() - started) * _MS_PER_SECOND)
        total_count = int(found[0][-1]) if found else 0
        return ReportRows(
            rows=tuple(convert_row(row[:-1], value_types) for row in found),
            total_count=total_count,
            sql=display_sql(data),
            elapsed_ms=elapsed_ms,
            totals=convert_row(totals_row, value_types) if totals_row is not None else None,
        )
