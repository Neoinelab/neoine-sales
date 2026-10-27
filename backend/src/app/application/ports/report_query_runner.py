from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.report.resolve import ResolvedReport

type ReportCell = str | int | float | date | datetime | None


@dataclass(frozen=True, slots=True)
class ReportRows:
    """실행 결과. 행의 값 순서는 정의의 컬럼 순서와 같다."""

    rows: tuple[tuple[ReportCell, ...], ...]
    total_count: int  # 행 수 제한 전의 전체 행(그룹핑이면 그룹) 수
    sql: str  # 사람에게 보여 주는 표시용 문자열(실행에 쓰지 않는다)
    elapsed_ms: int
    # 그룹핑하고 집계 컬럼이 하나 이상일 때만, 그룹 없이 전체 범위를 한 번 더 집계한 한 행
    # (컬럼 순서, 그룹 컬럼은 None). 그 밖은 None
    totals: tuple[ReportCell, ...] | None = None


class ReportQueryTimeoutError(Exception):
    """문장 시간 제한 초과. 웹이 503 report-timeout으로 바꾼다(원인 문구는 노출하지 않는다)."""


class ReportQueryRunner(Protocol):
    async def run(self, report: ResolvedReport) -> ReportRows:
        """검증·해석이 끝난 정의를 읽기 전용으로 실행한다. 시간 초과면 ReportQueryTimeoutError."""
        ...
