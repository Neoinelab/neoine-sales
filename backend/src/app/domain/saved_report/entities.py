from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.common.entity import AuditedEntity
from app.domain.report.chart import ChartKind
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.stored import BROKEN_DEFINITION, definition_entities
from app.domain.saved_report.errors import (
    ReportDeleteForbiddenError,
    ReportEditConflictError,
    ReportEditForbiddenError,
    ReportNotFoundError,
    ReportVisibilityForbiddenError,
)
from app.domain.saved_report.layout import DEFAULT_LAYOUT, ReportLayout
from app.domain.saved_report.policy import (
    can_change_report_visibility,
    can_delete_report,
    can_edit_report,
    can_view_report,
)
from app.domain.saved_report.values import ReportContent, ReportId, ReportVisibility

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.principal import Role
    from app.domain.report.raw import RawChart, RawReportDefinition
    from app.domain.report.vocabulary import Entity
    from app.domain.user.value_objects import UserId


@dataclass(eq=False, kw_only=True)
class Report(AuditedEntity[ReportId]):
    """Aggregate Root. 이름은 전체에서 대소문자 무시로 고유하다(저장소가 지킨다).

    definition이 None이면 저장된 정의를 읽을 수 없는 깨진 리포트다(목록·수정·삭제는 가능).
    """

    name: str
    description: str
    visibility: ReportVisibility
    owner_user_id: UserId
    updated_by_user_id: UserId
    definition: RawReportDefinition | None
    generated_sql: str
    revision: int
    chart: RawChart | None = None
    chart_unreadable: bool = False  # 저장된 chart를 읽지 못함(chart는 None)
    layout: ReportLayout = DEFAULT_LAYOUT

    @classmethod
    def create(
        cls, *, entity_id: ReportId, content: ReportContent, owner: UserId, now: datetime
    ) -> Self:
        return cls(
            id=entity_id,
            name=content.name,
            description=content.description,
            visibility=content.visibility,
            owner_user_id=owner,
            updated_by_user_id=owner,
            definition=content.definition,
            generated_sql=content.generated_sql,
            chart=content.chart,
            layout=content.layout or DEFAULT_LAYOUT,
            revision=1,
            created_at=now,
            updated_at=now,
        )

    def ensure_visible_to(self, user_id: UserId, role: Role) -> None:
        if not can_view_report(
            user_id, role, owner_id=self.owner_user_id, visibility=self.visibility
        ):
            raise ReportNotFoundError(self.id)

    def ensure_deletable_by(self, user_id: UserId, role: Role) -> None:
        self.ensure_visible_to(user_id, role)
        if not can_delete_report(user_id, role, owner_id=self.owner_user_id):
            raise ReportDeleteForbiddenError

    def overwrite(
        self,
        content: ReportContent,
        *,
        editor: UserId,
        role: Role,
        expected_revision: int,
        now: datetime,
    ) -> None:
        """판정 순서: 볼 수 있는가(404) -> 고칠 수 있는가·공개 범위(403) -> revision(409)."""
        self.ensure_visible_to(editor, role)
        self._ensure_editable_by(editor, role)
        if content.visibility is not self.visibility and not can_change_report_visibility(
            editor, role, owner_id=self.owner_user_id
        ):
            raise ReportVisibilityForbiddenError
        self._ensure_revision(expected_revision)
        self.name = content.name
        self.description = content.description
        self.visibility = content.visibility
        self.definition = content.definition
        self.generated_sql = content.generated_sql
        self.chart = content.chart
        self.chart_unreadable = False
        if content.layout is not None:
            self.layout = content.layout
        self.updated_by_user_id = editor
        self.revision += 1
        self._touch(now)

    def change_layout(
        self,
        layout: ReportLayout,
        *,
        editor: UserId,
        role: Role,
        expected_revision: int,
        now: datetime,
    ) -> None:
        """배치만 바꾼다. 판정 순서: 볼 수 있는가(404) -> 고칠 수 있는가(403) -> revision(409)."""
        self.ensure_visible_to(editor, role)
        self._ensure_editable_by(editor, role)
        self._ensure_revision(expected_revision)
        self.layout = layout
        self.updated_by_user_id = editor
        self.revision += 1
        self._touch(now)

    def _ensure_editable_by(self, editor: UserId, role: Role) -> None:
        if not can_edit_report(
            editor, role, owner_id=self.owner_user_id, visibility=self.visibility
        ):
            raise ReportEditForbiddenError

    def _ensure_revision(self, expected_revision: int) -> None:
        if expected_revision != self.revision:
            raise ReportEditConflictError

    def copy_as(  # noqa: PLR0913
        self,
        *,
        entity_id: ReportId,
        meta_name: str,
        meta_description: str,
        visibility: ReportVisibility,
        generated_sql: str,
        owner: UserId,
        now: datetime,
        chart: RawChart | None = None,
    ) -> Self:
        """정의는 이 리포트의 것을 그대로 쓰고 나머지는 새로 정한다."""
        content = ReportContent(
            name=meta_name,
            description=meta_description,
            visibility=visibility,
            definition=self.readable_definition(),
            generated_sql=generated_sql,
            chart=chart,
            layout=self.layout,
        )
        return type(self).create(entity_id=entity_id, content=content, owner=owner, now=now)

    def readable_definition(self) -> RawReportDefinition:
        """깨진 저장 정의면 ReportDefinitionError(stored-invalid)."""
        if self.definition is None:
            raise ReportDefinitionError([BROKEN_DEFINITION])
        return self.definition

    def chart_kind(self) -> ChartKind | None:
        """목록에 보일 차트 종류. 차트가 없거나 읽을 수 없으면 None."""
        return None if self.chart is None else ChartKind(str(self.chart.kind))

    def entities(self) -> tuple[Entity, ...]:
        if self.definition is None:
            return ()
        return definition_entities(self.definition)
