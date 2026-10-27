"""ReportRepository Port(저장 리포트)의 SQLAlchemy 구현.

이름 고유성(전체에서, 대소문자 무시)은 DB 유니크 인덱스가 보장하고 위반은 도메인 오류로 바꾼다.
정의는 JSON으로 저장하고 읽을 때 원시 정의로 되돌린다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import or_, select

from app.domain.common.errors import AlreadyExistsError
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.stored import definition_from_json, definition_to_json
from app.domain.report.stored_chart import chart_from_json, chart_to_json
from app.domain.saved_report.entities import Report
from app.domain.saved_report.errors import DuplicateReportNameError, ReportNotFoundError
from app.domain.saved_report.values import ReportId, ReportVisibility
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.models_report import ReportRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.report.raw import RawChart, RawReportDefinition
    from app.domain.saved_report.values import ReportListScope


def _stored_definition(row: ReportRow) -> RawReportDefinition | None:
    """읽을 수 없는 저장 정의는 None(깨진 리포트)으로 둔다. 목록·삭제는 가능해야 한다."""
    try:
        return definition_from_json(row.definition)
    except ReportDefinitionError:
        return None


def _stored_chart(row: ReportRow) -> tuple[RawChart | None, bool]:
    """(차트, 읽기 불가 여부). 깨진 차트는 (None, True)로 두어 열기·삭제·덮어쓰기가 가능하다."""
    if row.chart is None:
        return None, False
    try:
        return chart_from_json(row.chart), False
    except ReportDefinitionError:
        return None, True


def _entity(row: ReportRow) -> Report:
    chart, unreadable = _stored_chart(row)
    return Report(
        id=ReportId(row.id),
        name=row.name,
        description=row.description,
        visibility=ReportVisibility(row.visibility),
        owner_user_id=UserId(row.owner_user_id),
        updated_by_user_id=UserId(row.updated_by_user_id),
        definition=_stored_definition(row),
        generated_sql=row.generated_sql,
        revision=row.revision,
        chart=chart,
        chart_unreadable=unreadable,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _write_errors(report: Report) -> ConstraintErrors:
    return {
        "uq_reports_name_lower": lambda: DuplicateReportNameError(report.name),
        "pk_reports": lambda: AlreadyExistsError("리포트", report.id),
    }


class SqlReportRepository(SqlRepository[ReportRow]):
    row_type = ReportRow

    async def list(self, scope: ReportListScope) -> Sequence[Report]:
        statement = select(ReportRow).order_by(ReportRow.updated_at.desc(), ReportRow.id.desc())
        if not scope.see_all:
            statement = statement.where(
                or_(
                    ReportRow.owner_user_id == scope.viewer_id,
                    ReportRow.visibility == ReportVisibility.PUBLIC.value,
                )
            )
        rows = (
            await self._session.scalars(statement.execution_options(populate_existing=True))
        ).all()
        return [_entity(row) for row in rows]

    async def get(self, report_id: ReportId, *, for_update: bool = False) -> Report:
        return _entity(await self._row(report_id, for_update=for_update))

    async def add(self, report: Report) -> None:
        row = ReportRow(
            id=report.id,
            owner_user_id=report.owner_user_id,
            created_at=report.created_at,
            **_content(report),
        )
        await self._insert(row, _write_errors(report))

    async def update(self, report: Report) -> None:
        row = await self._row(report.id)

        async def work() -> None:
            for name, value in _content(report).items():
                setattr(row, name, value)

        await self._atomic(
            _write_errors(report), work, not_found=lambda: ReportNotFoundError(report.id)
        )

    async def delete(self, report_id: ReportId) -> None:
        await self._remove(await self._row(report_id), {})

    async def _row(self, report_id: int, *, for_update: bool = False) -> ReportRow:
        statement = select(ReportRow).where(ReportRow.id == report_id)
        if for_update:
            statement = statement.with_for_update()
        row = (
            await self._session.scalars(statement.execution_options(populate_existing=True))
        ).one_or_none()
        if row is None:
            raise ReportNotFoundError(report_id)
        return row


def _content(report: Report) -> dict[str, object]:
    """변경 가능한 열. 만든 사람·생성 시각은 포함하지 않는다."""
    return {
        "name": report.name,
        "description": report.description,
        "visibility": report.visibility.value,
        "updated_by_user_id": report.updated_by_user_id,
        "definition": definition_to_json(report.readable_definition()),
        "generated_sql": report.generated_sql,
        "chart": None if report.chart is None else chart_to_json(report.chart),
        "revision": report.revision,
        "updated_at": report.updated_at,
    }
