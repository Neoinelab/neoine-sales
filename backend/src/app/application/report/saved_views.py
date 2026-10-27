from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.report.vocabulary import Entity
    from app.domain.saved_report.entities import Report


@dataclass(frozen=True, slots=True)
class ReportItemView:
    report: Report
    entities: tuple[Entity, ...]
