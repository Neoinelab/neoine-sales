"""저장 리포트 값 객체: 이름·설명 규칙, 공개 범위, 저장할 내용, 목록 범위."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NewType, Self

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

if TYPE_CHECKING:
    from app.domain.report.raw import RawChart, RawReportDefinition
    from app.domain.user.value_objects import UserId

ReportId = NewType("ReportId", int)

REPORT_NAME_MAX = 100
REPORT_DESCRIPTION_MAX = 1000


class ReportVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"

    @classmethod
    def parse(cls, raw: object) -> Self:
        """문자열이 정확히 일치할 때만 받는다(대소문자·공백 구분)."""
        if type(raw) is str:
            for member in cls:
                if member.value == raw:
                    return member
        raise InvalidValueError("공개 범위는 public 또는 private입니다.")


def normalize_report_name(raw: str) -> str:
    reject_nul(raw, "리포트 이름")
    name = raw.strip()
    if not name:
        raise InvalidValueError("리포트 이름을 입력하세요.")
    if len(name) > REPORT_NAME_MAX:
        raise InvalidValueError(f"리포트 이름은 {REPORT_NAME_MAX}자 이내로 입력하세요.")
    return name


def normalize_report_description(raw: str) -> str:
    reject_nul(raw, "설명")
    text = raw.strip()
    if len(text) > REPORT_DESCRIPTION_MAX:
        raise InvalidValueError("설명은 1,000자 이내로 입력하세요.")
    return text


@dataclass(frozen=True, slots=True)
class ReportContent:
    """저장할 내용. 이름·설명은 정규화된 값, definition은 검증을 통과한 원시 정의."""

    name: str
    description: str
    visibility: ReportVisibility
    definition: RawReportDefinition
    generated_sql: str
    chart: RawChart | None = None  # 검증·정규화를 통과한 차트


@dataclass(frozen=True, slots=True)
class ReportListScope:
    viewer_id: UserId
    see_all: bool  # True면 비공개 포함 전부(admin)
