"""ReportRepository(저장 리포트) 계약 테스트 공용 case(Fake와 SQL 구현 양쪽).

SQL 구현은 같은 DB에 다른 테스트가 만든 행이 있을 수 있으므로, 계약 테스트는 비어 있는 저장소를
가정하지 않는다(자기가 만든 행만 골라 비교한다: `mine`). 만든 사람·최종 수정자는 users FK라
`add`/`prepare`가 사용자 행을 먼저 만든다. SQL 구현 모듈은 사용 시점에 가져온다.
(`report_case.py`는 Reports 조회 엔진 계약이고 이 파일과 무관하다.)
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pytest

from tests.fakes.report_repository import FakeReportRepository
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Collection
    from datetime import datetime

    from sqlalchemy.engine import URL

    from app.domain.saved_report.entities import Report
    from app.domain.user.value_objects import UserId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


class SavedReportCase:
    """한 구현(fake 또는 sql)의 저장 리포트 저장소와 사용자 저장소."""

    def __init__(self, reports: Any, users: Any, session: Any = None) -> None:  # noqa: ANN401
        self.reports = reports
        self.users = users
        self._session = session  # sql 구현만(원시 UPDATE용)

    async def prepare(self, *user_ids: UserId) -> None:
        """리포트가 참조하는 사용자 행을 (없으면) 만든다."""
        await ensure_users(self.users, *user_ids)

    async def add(self, report: Report) -> Report:
        await self.prepare(report.owner_user_id, report.updated_by_user_id)
        await self.reports.add(report)
        return report

    async def mine(self, scope: Any, ids: Collection[Any]) -> list[Any]:  # noqa: ANN401
        """scope로 읽은 목록 중 ids에 있는 리포트만(저장소 순서 유지)."""
        return [r for r in await self.reports.list(scope) if r.id in ids]

    async def corrupt_definition(self, report: Report, raw_json: str) -> None:
        """저장 형식으로 읽을 수 없는 정의 JSON을 직접 써 넣는다(저장소를 거치지 않는다).

        sql은 definition 컬럼을 원시 UPDATE하고(객체이면 CHECK는 통과), fake는 저장된 엔티티의
        정의를 None(읽을 수 없음)으로 만든다.
        """
        if self._session is None:
            self.reports._items[report.id].definition = None
            return
        from sqlalchemy import text  # noqa: PLC0415

        await self._session.execute(
            text("update reports set definition = cast(:d as jsonb) where id = :id"),
            {"d": raw_json, "id": report.id},
        )

    async def corrupt_chart(self, report: Report, raw_json: str) -> None:
        """저장 형식으로 읽을 수 없는 차트 JSON을 직접 써 넣는다(저장소를 거치지 않는다).

        sql은 chart 컬럼을 원시 UPDATE하고(제약이 없어 어떤 JSON이든 들어간다), fake는 저장된
        엔티티를 "차트를 읽을 수 없음"(chart=None, chart_unreadable=True)으로 만든다.
        """
        if self._session is None:
            stored = self.reports._items[report.id]
            stored.chart = None
            stored.chart_unreadable = True
            return
        from sqlalchemy import text  # noqa: PLC0415

        await self._session.execute(
            text("update reports set chart = cast(:d as jsonb) where id = :id"),
            {"d": raw_json, "id": report.id},
        )

    async def resign(self, user_id: UserId, at: datetime) -> None:
        user = await self.users.get(user_id)
        user.resign(at)
        await self.users.update(user)


@asynccontextmanager
async def open_saved_report_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[SavedReportCase]:
    if implementation == "fake":
        yield SavedReportCase(FakeReportRepository(), FakeUserRepository())
        return
    from app.infra.db.report_repository import SqlReportRepository  # noqa: PLC0415
    from app.infra.db.user_repository import SqlUserRepository  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield SavedReportCase(SqlReportRepository(session), SqlUserRepository(session), session)
