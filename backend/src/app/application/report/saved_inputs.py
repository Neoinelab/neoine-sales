from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.auth.principal import Role
    from app.domain.report.raw import RawReportDefinition
    from app.domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class ReportViewer:
    """요청한 사람. 권한 판정은 도메인이 한다."""

    user_id: UserId
    role: Role


@dataclass(frozen=True, slots=True)
class ReportContentInput:
    name: str
    description: str
    visibility: str
    definition: RawReportDefinition


@dataclass(frozen=True, slots=True)
class ReportMetaInput:
    name: str
    description: str
    visibility: str
