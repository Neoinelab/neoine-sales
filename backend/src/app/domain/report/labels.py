"""카탈로그 응답에 쓰는 어휘의 한국어 표시 이름과 연산자 값 모양."""

from enum import StrEnum

from app.domain.report.vocabulary import (
    Aggregate,
    Entity,
    Format,
    Operator,
    RelativePeriod,
)


class OperatorShape(StrEnum):
    """연산자가 받는 값의 모양(프런트가 입력 위젯을 고르는 힌트). between은 형식에 따라
    숫자는 `range`, 날짜는 `date_range`로 해석한다."""

    TEXT = "text"
    LIST = "list"
    NUMBER = "number"
    RANGE = "range"
    DATE = "date"
    RELATIVE = "relative"
    NONE = "none"


ENTITY_LABELS: dict[Entity, str] = {Entity.DEAL: "Deal", Entity.ACTION: "Deal Actions"}

FORMAT_LABELS: dict[Format, str] = {
    Format.YMD: "연-월-일",
    Format.YMD_HM: "연-월-일 시:분",
    Format.YEAR: "연도",
    Format.QUARTER: "분기",
    Format.MONTH: "월",
    Format.WEEKDAY: "요일",
    Format.RELATIVE: "상대 시각",
}

OPERATOR_LABELS: dict[Operator, tuple[str, OperatorShape]] = {
    Operator.CONTAINS: ("포함", OperatorShape.TEXT),
    Operator.EQUALS: ("같음", OperatorShape.TEXT),
    Operator.STARTS_WITH: ("시작", OperatorShape.TEXT),
    Operator.IS_EMPTY: ("비어 있음", OperatorShape.NONE),
    Operator.IS_NOT_EMPTY: ("비어 있지 않음", OperatorShape.NONE),
    Operator.IN: ("다음 중 하나", OperatorShape.LIST),
    Operator.NOT_IN: ("다음이 아님", OperatorShape.LIST),
    Operator.EQ: ("=", OperatorShape.NUMBER),
    Operator.NE: ("≠", OperatorShape.NUMBER),
    Operator.GT: (">", OperatorShape.NUMBER),
    Operator.GTE: ("≥", OperatorShape.NUMBER),
    Operator.LT: ("<", OperatorShape.NUMBER),
    Operator.LTE: ("≤", OperatorShape.NUMBER),
    Operator.BETWEEN: ("범위", OperatorShape.RANGE),
    Operator.BEFORE: ("이전", OperatorShape.DATE),
    Operator.AFTER: ("이후", OperatorShape.DATE),
    Operator.RELATIVE: ("상대 기간", OperatorShape.RELATIVE),
}

AGGREGATE_LABELS: dict[Aggregate, str] = {
    Aggregate.SUM: "합계",
    Aggregate.AVG: "평균",
    Aggregate.MIN: "최소",
    Aggregate.MAX: "최대",
    Aggregate.COUNT: "건수",
    Aggregate.COUNT_DISTINCT: "고유 건수",
}

PERIOD_LABELS: dict[RelativePeriod, str] = {
    RelativePeriod.THIS_YEAR: "올해",
    RelativePeriod.THIS_QUARTER: "이번 분기",
    RelativePeriod.THIS_MONTH: "이번 달",
    RelativePeriod.LAST_N_DAYS: "최근 N일",
    RelativePeriod.BEFORE_TODAY: "오늘 이전",
}
