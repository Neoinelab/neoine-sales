from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class ReportIssue:
    """정의의 위반 하나: 위치(예: `("columns", 2, "aggregate")`), 오류 코드, 한국어 문구."""

    location: tuple[str | int, ...]
    code: str
    message: str


class ReportDefinitionError(InvalidValueError):
    """리포트 정의가 규칙을 어김. 위반을 모두 모아 담고, 문구는 첫 위반의 것이다."""

    def __init__(self, issues: Sequence[ReportIssue]) -> None:
        if not issues:
            raise ValueError("위반이 하나 이상 있어야 합니다.")
        super().__init__(issues[0].message)
        self.issues: tuple[ReportIssue, ...] = tuple(issues)


class IssueLog:
    """검증 중 위반을 모으는 도우미. `scope`로 위치 접두사를 고정한 기록기를 얻는다."""

    def __init__(self) -> None:
        self.items: list[ReportIssue] = []

    def add(self, location: tuple[str | int, ...], code: str, message: str) -> None:
        self.items.append(ReportIssue(location, code, message))

    def scope(self, *prefix: str | int) -> IssueScope:
        return IssueScope(self, prefix)


class IssueScope:
    """한 컬럼·조건 안의 위반 기록기. 위치는 `접두사 + (세부 항목,)`이다."""

    def __init__(self, log: IssueLog, prefix: tuple[str | int, ...]) -> None:
        self._log = log
        self._prefix = prefix
        self._start = len(log.items)

    def add(self, code: str, message: str, *detail: str) -> None:
        """세부 항목(예: "aggregate")을 지정하면 그 위치에, 없으면 이 컬럼·조건 위치에 기록한다."""
        self._log.add((*self._prefix, *detail), code, message)

    @property
    def failed(self) -> bool:
        """이 기록기를 만든 뒤 위반이 하나라도 기록됐는가."""
        return len(self._log.items) > self._start
