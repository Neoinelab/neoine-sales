from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.saved_report.entities import Report
    from app.domain.saved_report.values import ReportId, ReportListScope


class ReportRepository(Protocol):
    """저장 리포트 저장소 계약. 이름은 전체에서 대소문자 무시로 고유하다."""

    async def list(self, scope: ReportListScope) -> Sequence[Report]:
        """see_all이면 전부, 아니면 만든 사람이 viewer이거나 공개.

        updated_at 내림차순, 동률은 id 내림차순.
        """
        ...

    async def get(self, report_id: ReportId, *, for_update: bool = False) -> Report:
        """없으면 ReportNotFoundError. for_update면 트랜잭션이 끝날 때까지 행을 잠근다.

        저장된 정의를 읽을 수 없으면 실패하지 않고 definition=None인 엔티티를 돌려준다.
        """
        ...

    async def add(self, report: Report) -> None:
        """소문자 이름이 어떤 리포트와든 겹치면 DuplicateReportNameError."""
        ...

    async def update(self, report: Report) -> None:
        """변경 가능한 내용만 맞춘다.

        name·description·visibility·definition·generated_sql·chart·layout·updated_by·revision·updated_at.

        만든 사람·생성 시각은 유지한다. 없으면 ReportNotFoundError,
        이름이 겹치면 DuplicateReportNameError.
        """
        ...

    async def update_layout(self, report: Report) -> None:
        """layout·updated_by·revision·updated_at만 맞춘다(정의·차트 JSON은 다시 쓰지 않는다).

        없으면 ReportNotFoundError.
        """
        ...

    async def delete(self, report_id: ReportId) -> None:
        """물리 삭제한다. 없으면 ReportNotFoundError."""
        ...
