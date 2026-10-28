"""ReportRepository Port의 InMemory 구현(Fake). 저장 리포트 Aggregate.

도메인 모듈(app.domain.saved_report)은 사용 시점에 가져온다. 이 Fake는 FakeUnitOfWork가 항상
만들기 때문에 모듈 수준 import는 리포트와 무관한 테스트의 수집까지 막는다(vendors.py와 같은 이유).

계약(SQL 구현과 같다)
- 이름은 모든 리포트 사이에서 대소문자 무시로 고유하다(만든 사람·공개 범위와 무관, add·update 모두
  DuplicateReportNameError)
- `list(scope)`: see_all이면 전부, 아니면 owner가 viewer이거나 public. updated_at 내림차순, 동률은
  id 내림차순
- `update`는 name·description·visibility·definition·generated_sql·chart·chart_unreadable·layout·
  updated_by·revision·updated_at만 바꾼다(owner·created_at은 저장된 값을 유지).
  없으면 ReportNotFoundError
- `update_layout`은 layout·updated_by·revision·updated_at만 바꾼다(정의·차트·이름은 저장된 값을
  그대로 둔다). 없으면 ReportNotFoundError
- `delete`는 물리 삭제. 없으면 ReportNotFoundError
- get은 복사본을 돌려준다(저장소를 거치지 않은 변경이 저장되지 않는다)
"""

import copy
from typing import TYPE_CHECKING, Any

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.saved_report.entities import Report
    from app.domain.saved_report.values import ReportId, ReportListScope


def _not_found(report_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    from app.domain.saved_report.errors import ReportNotFoundError  # noqa: PLC0415

    return ReportNotFoundError(report_id)


class FakeReportRepository(InMemoryStore["Report"]):
    def __init__(self) -> None:
        super().__init__("report", _not_found)

    def _ensure_unique(self, report: Report) -> None:
        from app.domain.saved_report.errors import DuplicateReportNameError  # noqa: PLC0415

        lowered = report.name.lower()
        for other in self._items.values():
            if other.id != report.id and other.name.lower() == lowered:
                raise DuplicateReportNameError(report.name)

    async def list(self, scope: ReportListScope) -> Sequence[Report]:
        visible = [
            r
            for r in self._items.values()
            if scope.see_all or r.owner_user_id == scope.viewer_id or r.visibility.value == "public"
        ]
        ordered = sorted(visible, key=lambda r: (r.updated_at, r.id), reverse=True)
        return [copy.deepcopy(r) for r in ordered]

    async def get(self, report_id: ReportId, *, for_update: bool = False) -> Report:
        return copy.deepcopy(self._fetch(report_id))

    async def add(self, report: Report) -> None:
        self._ensure_unique(report)
        self._insert(report)

    async def update(self, report: Report) -> None:
        stored = self._fetch(report.id)  # 없으면 ReportNotFoundError
        self._ensure_unique(report)
        stored.name = report.name
        stored.description = report.description
        stored.visibility = report.visibility
        stored.definition = report.definition
        stored.generated_sql = report.generated_sql
        # getattr: 차트 필드가 생기기 전의 엔티티로도 이 Fake가 동작하게 한다(4단계 구현 전 테스트)
        stored.chart = getattr(report, "chart", None)
        stored.chart_unreadable = getattr(report, "chart_unreadable", False)
        if hasattr(report, "layout"):  # 배치 필드가 생기기 전의 엔티티로도 동작하게 한다
            stored.layout = report.layout
        stored.updated_by_user_id = report.updated_by_user_id
        stored.revision = report.revision
        stored.updated_at = report.updated_at
        self._replace(stored)

    async def update_layout(self, report: Report) -> None:
        stored = self._fetch(report.id)  # 없으면 ReportNotFoundError
        stored.layout = report.layout
        stored.updated_by_user_id = report.updated_by_user_id
        stored.revision = report.revision
        stored.updated_at = report.updated_at
        self._replace(stored)

    async def delete(self, report_id: ReportId) -> None:
        self._remove(report_id)
