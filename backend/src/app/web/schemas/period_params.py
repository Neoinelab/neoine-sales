"""기간 쿼리 파라미터 공용 정의. Deal 목록과 Dashboard가 Quarter 다중 선택을 함께 쓴다."""

from typing import Annotated, Any

from pydantic import AfterValidator, Field

from app.domain.deal.period import QUARTERS


def _check_quarters(values: list[int]) -> list[int]:
    if any(not 1 <= value <= QUARTERS for value in values):
        raise ValueError(f"분기는 1~{QUARTERS} 중에서 선택하세요.")
    return values


def _document_items(schema: dict[str, Any]) -> None:
    """항목 범위는 목록 단위로 검증하므로(오류 위치가 quarter) 문서에만 항목 제한을 표기한다."""
    schema["items"] = {"type": "integer", "minimum": 1, "maximum": QUARTERS}


QuartersParam = (
    Annotated[
        list[int],
        Field(max_length=QUARTERS, json_schema_extra=_document_items),
        AfterValidator(_check_quarters),
    ]
    | None
)


def quarter_set(quarter: list[int] | None) -> frozenset[int] | None:
    """반복 쿼리 값을 집합으로 바꾼다. 정규화(빈·네 분기 = 조건 없음)는 도메인이 한다."""
    return frozenset(quarter) if quarter else None
